from __future__ import annotations

from nexus.agent import Agent


def _agent_without_init():
    agent = object.__new__(
        Agent
    )

    agent._understanding = None
    agent._execution_plan = None

    return agent


def test_agent_gate_allows_non_mutating_answer():
    agent = (
        _agent_without_init()
    )

    decision = (
        agent
        ._completion_evidence_gate(
            task=(
                "Explain what this code does."
            ),
            result=(
                "It parses a file."
            ),
        )
    )

    assert decision.complete


def test_agent_gate_rejects_file_only_roblox_completion():
    agent = (
        _agent_without_init()
    )

    decision = (
        agent
        ._completion_evidence_gate(
            task=(
                "Move the Roblox meshes "
                "into a straight line in Studio."
            ),
            result=(
                "Created arrange_meshes.lua\n"
                "ARTIFACT=PASS"
            ),
        )
    )

    assert not decision.complete

    assert (
        decision.status
        == "VERIFICATION_PENDING"
    )

    assert "studio" in decision.missing


def test_agent_gate_accepts_verified_roblox_completion():
    agent = (
        _agent_without_init()
    )

    decision = (
        agent
        ._completion_evidence_gate(
            task=(
                "Move the Roblox meshes "
                "into a straight line in Studio."
            ),
            result=(
                "ARTIFACT=PASS\n"
                "INTEGRATION=PASS\n"
                "STUDIO_VERIFICATION=PASS\n"
                "VISUAL_QA=PASS"
            ),
        )
    )

    assert decision.complete
