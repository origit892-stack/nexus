import nexus.runtime.execution_completion as completion


class FakeLedger:
    def recent(self, limit=24):
        return []


def test_execution_completion_passes_configured_model_path(
    monkeypatch,
):
    seen = {}

    monkeypatch.setattr(
        completion,
        "load_understanding_config",
        lambda: {
            "local_path": "/tmp/test-model",
            "finalizer_max_tokens": 128,
        },
    )

    def fake_loader(model_path):
        seen["model_path"] = model_path

        return (
            object(),
            object(),
        )

    monkeypatch.setattr(
        completion,
        "_load_model_cached",
        fake_loader,
    )

    monkeypatch.setattr(
        completion,
        "_generate_final_answer",
        lambda **kwargs: (
            (
                '{"verdict":"PASS",'
                '"summary":"complete",'
                '"unmet_conditions":[],'
                '"next_focus":[]}'
            ),
            {},
        ),
    )

    decision = (
        completion.evaluate_execution_completion(
            task="inspect files",
            plan={
                "authorized_now": [
                    "inspect files",
                ],
                "evidence_plan": [],
                "evaluation_plan": [],
                "selection_strategy": [],
                "stop_conditions": [
                    "report findings",
                ],
            },
            proposed_final=(
                "The requested findings were verified."
            ),
            evidence_ledger=FakeLedger(),
            progress=None,
        )
    )

    assert (
        seen["model_path"]
        == "/tmp/test-model"
    )

    assert decision.allow is True
    assert decision.verdict == "PASS"


def test_loader_signature_mismatch_is_not_swallowed(
    monkeypatch,
):
    monkeypatch.setattr(
        completion,
        "load_understanding_config",
        lambda: {
            "local_path": "/tmp/test-model",
            "finalizer_max_tokens": 128,
        },
    )

    def wrong_loader():
        return (
            object(),
            object(),
        )

    monkeypatch.setattr(
        completion,
        "_load_model_cached",
        wrong_loader,
    )

    try:
        completion.evaluate_execution_completion(
            task="inspect files",
            plan={
                "authorized_now": [
                    "inspect files",
                ],
                "stop_conditions": [
                    "report findings",
                ],
            },
            proposed_final="done",
            evidence_ledger=FakeLedger(),
            progress=None,
        )
    except TypeError:
        return

    raise AssertionError(
        "Loader signature mismatch was silently accepted."
    )
