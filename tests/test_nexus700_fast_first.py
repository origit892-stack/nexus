from nexus.runtime.fast_first import (
    classify_fast_first,
    deterministic_fast_completion,
    fast_lookup_contract,
)


def test_simple_read_only_lookup_is_fast():
    decision = classify_fast_first(
        "Read-only task. Find pyproject.toml "
        "under this workspace and read "
        "docs/agents/README.md. "
        "Do not modify files."
    )

    assert decision.eligible
    assert decision.route == "FAST_LOOKUP"
    assert decision.read_only
    assert decision.skip_understanding_model
    assert decision.skip_planner_model
    assert decision.skip_completion_model
    assert decision.deterministic_completion
    assert decision.max_tool_calls <= 4


def test_mutation_is_not_fast_lookup():
    decision = classify_fast_first(
        "Find README.md and edit its heading."
    )

    assert not decision.eligible


def test_complex_debug_is_not_fast_lookup():
    decision = classify_fast_first(
        "Investigate why the agent is slow "
        "and optimize the architecture."
    )

    assert not decision.eligible


def test_fast_contract_is_read_only():
    contract = fast_lookup_contract(
        "Find README.md."
    )

    forbidden = " ".join(
        contract["forbidden_now"]
    ).lower()

    assert "modify" in forbidden
    assert "delete" in forbidden
    assert "memory" in forbidden


def test_fast_completion_requires_evidence():
    allowed, reason = (
        deterministic_fast_completion(
            task="Find README.md",
            evidence_entries=[],
        )
    )

    assert not allowed
    assert reason == "no_evidence"


def test_fast_completion_accepts_verified_evidence():
    allowed, reason = (
        deterministic_fast_completion(
            task="Find README.md",
            evidence_entries=[
                {
                    "verified": True,
                    "positive": True,
                }
            ],
        )
    )

    assert allowed
    assert (
        reason
        == "verified_fast_lookup_evidence"
    )
