import pytest

import nexus.runtime.execution_completion as ec


class FakeLedger:
    def snapshot(self):
        return [
            {
                "tool": "read_file",
                "arguments": {
                    "path": "README.md",
                },
                "output": "# Test",
                "verified": True,
            }
        ]


def _config():
    return {
        "local_path":
            "/tmp/test-model",

        "finalizer_max_tokens":
            128,
    }


def _generate(**kwargs):
    return (
        (
            '{"verdict":"PASS",'
            '"summary":"complete",'
            '"unmet_conditions":[],'
            '"next_focus":[]}'
        ),
        {},
    )


def _run(monkeypatch, loader):
    monkeypatch.setattr(
        ec,
        "load_understanding_config",
        _config,
    )

    monkeypatch.setattr(
        ec,
        "_load_model_cached",
        loader,
    )

    monkeypatch.setattr(
        ec,
        "_generate_final_answer",
        _generate,
    )

    return (
        ec.evaluate_execution_completion(
            task="inspect README",
            plan={
                "authorized_now": [
                    "inspect README",
                ],

                "evidence_plan": [
                    "README contents",
                ],

                "evaluation_plan": [],

                "selection_strategy": [],

                "stop_conditions": [
                    "report README",
                ],
            },
            proposed_final=(
                "README verified."
            ),
            evidence_ledger=FakeLedger(),
        )
    )


def test_legacy_two_value_loader_result(
    monkeypatch,
):
    decision = _run(
        monkeypatch,
        lambda model_path: (
            object(),
            object(),
        ),
    )

    assert decision.allow


def test_current_three_value_loader_result(
    monkeypatch,
):
    metadata = {
        "backend": "mlx",
    }

    decision = _run(
        monkeypatch,
        lambda model_path: (
            object(),
            object(),
            metadata,
        ),
    )

    assert decision.allow


def test_future_extra_loader_metadata_is_tolerated(
    monkeypatch,
):
    decision = _run(
        monkeypatch,
        lambda model_path: (
            object(),
            object(),
            {
                "backend": "mlx",
            },
            {
                "extra": True,
            },
        ),
    )

    assert decision.allow


def test_invalid_one_value_loader_result_fails_closed(
    monkeypatch,
):
    with pytest.raises(
        ec.ExecutionCompletionError,
    ):
        _run(
            monkeypatch,
            lambda model_path: (
                object(),
            ),
        )


def test_invalid_non_sequence_loader_result_fails_closed(
    monkeypatch,
):
    with pytest.raises(
        ec.ExecutionCompletionError,
    ):
        _run(
            monkeypatch,
            lambda model_path:
                object(),
        )
