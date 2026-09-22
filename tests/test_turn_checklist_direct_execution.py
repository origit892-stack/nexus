from nexus.agent import Agent
from nexus.runtime.prompt_milestones import (
    Milestone,
    MilestonePlan,
    is_turn_checklist_execution_prompt,
    master_prompt_hash,
    turn_checklist_execution_prompt,
)


def build_plan():
    master = """Perform a READ-ONLY verification of BunkerGame.

1. Inspect the top-level project structure and identify
source, configuration, documentation, and tooling areas.

Do not modify anything.
"""

    milestone = Milestone(
        id="M1",
        title="Inspect project structure",
        objective=(
            "Inspect the top-level BunkerGame project structure "
            "and identify source, configuration, documentation, "
            "and tooling areas."
        ),
        requirements=(
            "Identify source.",
            "Identify configuration.",
            "Identify documentation.",
            "Identify tooling.",
        ),
        restrictions=(
            "READ_ONLY",
            "Do not modify anything.",
        ),
        dependencies=(),
        evidence_required=(
            "Inspected project paths.",
        ),
        completion_definition=(
            "All required areas identified.",
        ),
    )

    return MilestonePlan(
        master_prompt_sha256=(
            master_prompt_hash(master)
        ),
        master_prompt=master,
        milestones=(milestone,),
        global_restrictions=(
            "READ_ONLY",
            "Do not modify anything.",
        ),
        final_completion_definition=(
            "Audit verified.",
        ),
    )


def test_execution_protocol_prefix_is_strict():
    prompt = turn_checklist_execution_prompt(
        plan=build_plan(),
        index=0,
    )

    assert is_turn_checklist_execution_prompt(
        prompt
    )

    assert not is_turn_checklist_execution_prompt(
        "normal user request"
    )

    assert not is_turn_checklist_execution_prompt(
        "prefix NEXUS_MILESTONE_EXECUTION_V1"
    )


def test_execution_prompt_preserves_m1_semantics():
    prompt = turn_checklist_execution_prompt(
        plan=build_plan(),
        index=0,
    ).lower()

    for required in (
        "inspect the top-level bunkergame project structure",
        "source",
        "configuration",
        "documentation",
        "tooling",
        "read_only",
        "execute only this milestone",
        "do not execute later milestones",
        "do not declare the master turn complete",
    ):
        assert required in prompt

    for forbidden in (
        "database setup",
        "database connection",
        "isolated environment creation",
        "server roles",
        "player permissions",
        "network setup",
    ):
        assert forbidden not in prompt


def test_preplanned_brief_preserves_prompt():
    agent = object.__new__(Agent)

    prompt = turn_checklist_execution_prompt(
        plan=build_plan(),
        index=0,
    )

    brief = agent._preplanned_execution_brief(
        prompt
    )

    assert prompt in brief

    lower = brief.lower()

    assert "current milestone" in lower
    assert "understanding" in lower
    assert "planner" in lower
    assert "master turn complete" in lower
