from __future__ import annotations

from types import SimpleNamespace

import pytest

import nexus.runtime.execution_completion as ec


class FakeLedger:
    def __init__(self):
        self.items = [
            SimpleNamespace(
                tool="list_files",
                args={"path": "/project/assets"},
                output="crate.glb\npipe.glb",
                success=True,
            ),
            SimpleNamespace(
                tool="read_file",
                args={"path": "/project/report.json"},
                output='{"quality":"checked"}',
                success=True,
            ),
        ]

    def successful(self):
        return [
            item
            for item in self.items
            if item.success
        ]

    def summary(self):
        return {
            "tool_calls": 2,
            "successful": 2,
            "failed": 0,
        }


def test_completion_contract_keeps_only_current_phase_fields():
    plan = {
        "current_phase": "inspection",
        "authorized_now": ["inspect"],
        "evidence_plan": ["collect evidence"],
        "evaluation_plan": ["evaluate"],
        "selection_strategy": ["rank"],
        "stop_conditions": ["report ready"],
        "deferred_actions": ["place assets"],
        "forbidden_now": ["delete assets"],
    }

    result = ec.completion_contract(
        plan
    )

    assert result == {
        "current_phase": "inspection",
        "authorized_now": ["inspect"],
        "evidence_plan": ["collect evidence"],
        "evaluation_plan": ["evaluate"],
        "selection_strategy": ["rank"],
        "stop_conditions": ["report ready"],
    }


def test_evidence_payload_is_bounded():
    result = ec.evidence_for_completion(
        FakeLedger(),
        max_items=1,
        max_output_chars=10,
    )

    assert result["summary"][
        "successful"
    ] == 2

    items = result[
        "recent_successful_evidence"
    ]

    assert len(items) == 1
    assert len(items[0]["output"]) < 40


def test_validate_pass():
    decision = ec._validate_payload(
        {
            "verdict": "PASS",
            "summary": "done",
            "unmet_conditions": [],
            "next_focus": [],
        }
    )

    assert decision.allow is True
    assert decision.verdict == "PASS"


def test_continue_requires_unmet_conditions():
    with pytest.raises(
        ec.ExecutionCompletionError,
        match="unmet_conditions",
    ):
        ec._validate_payload(
            {
                "verdict": "CONTINUE",
                "summary": "not done",
                "unmet_conditions": [],
                "next_focus": ["inspect"],
            }
        )


def test_continue_requires_next_focus():
    with pytest.raises(
        ec.ExecutionCompletionError,
        match="next_focus",
    ):
        ec._validate_payload(
            {
                "verdict": "CONTINUE",
                "summary": "not done",
                "unmet_conditions": [
                    "evaluation missing"
                ],
                "next_focus": [],
            }
        )


def test_model_continue_decision(
    monkeypatch,
):
    monkeypatch.setattr(
        ec,
        "_load_model_cached",
        lambda model_path: (
            object(),
            object(),
        ),
    )

    monkeypatch.setattr(
        ec,
        "load_understanding_config",
        lambda: {
            "local_path": "/tmp/test-model",
            "finalizer_max_tokens": 256,
        },
    )

    captured = {}

    def fake_generate(
        *,
        model,
        tokenizer,
        messages,
        max_tokens,
    ):
        captured["messages"] = messages
        captured["max_tokens"] = max_tokens

        return (
            '{"verdict":"CONTINUE",'
            '"summary":"selection missing",'
            '"unmet_conditions":'
            '["No ranked selection is supported"],'
            '"next_focus":'
            '["Compare discovered candidates and rank them"]}',
            {},
        )

    monkeypatch.setattr(
        ec,
        "_generate_final_answer",
        fake_generate,
    )

    decision = (
        ec.evaluate_execution_completion(
            task="inspect and rank assets",
            plan={
                "current_phase": "inspection",
                "authorized_now": [
                    "inspect",
                    "rank",
                ],
                "evidence_plan": [
                    "inventory",
                ],
                "evaluation_plan": [
                    "quality comparison",
                ],
                "selection_strategy": [
                    "rank candidates",
                ],
                "stop_conditions": [
                    "selection ready",
                ],
            },
            proposed_final=(
                "I found some directories."
            ),
            evidence_ledger=FakeLedger(),
        )
    )

    assert decision.allow is False
    assert decision.verdict == "CONTINUE"
    assert decision.unmet_conditions
    assert decision.next_focus

    joined = str(
        captured["messages"]
    )

    assert "rank candidates" in joined
    assert "I found some directories" in joined


def test_model_pass_decision(
    monkeypatch,
):
    monkeypatch.setattr(
        ec,
        "_load_model_cached",
        lambda model_path: (
            object(),
            object(),
        ),
    )

    monkeypatch.setattr(
        ec,
        "load_understanding_config",
        lambda: {
            "local_path": "/tmp/test-model",
            "finalizer_max_tokens": 256,
        },
    )

    monkeypatch.setattr(
        ec,
        "_generate_final_answer",
        lambda **kwargs: (
            '{"verdict":"PASS",'
            '"summary":"contract satisfied",'
            '"unmet_conditions":[],'
            '"next_focus":[]}',
            {},
        ),
    )

    decision = (
        ec.evaluate_execution_completion(
            task="inspect assets",
            plan={
                "current_phase": "inspection",
                "authorized_now": ["inspect"],
                "evidence_plan": ["inventory"],
                "evaluation_plan": [],
                "selection_strategy": [],
                "stop_conditions": [
                    "inventory reported"
                ],
            },
            proposed_final=(
                "Inventory: crate, pipe."
            ),
            evidence_ledger=FakeLedger(),
        )
    )

    assert decision.allow is True


def test_no_plan_preserves_legacy_completion():
    decision = (
        ec.evaluate_execution_completion(
            task="hello",
            plan=None,
            proposed_final="done",
            evidence_ledger=None,
        )
    )

    assert decision.allow is True
