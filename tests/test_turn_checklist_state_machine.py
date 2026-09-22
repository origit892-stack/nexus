from nexus.runtime.prompt_milestones import (
    Milestone,
    MilestonePlan,
    master_prompt_hash,
    turn_checklist_execution_prompt,
)
from nexus.sessions.milestone_state import (
    state_from_plan,
)


def _milestone(mid):
    return Milestone(
        id=mid,
        title=mid,
        objective=mid,
        requirements=(mid,),
        restrictions=(),
        dependencies=(),
        evidence_required=(),
        completion_definition=("done",),
    )


def _plan():
    master = "MASTER"

    return MilestonePlan(
        master_prompt_sha256=master_prompt_hash(
            master
        ),
        master_prompt=master,
        milestones=(
            _milestone("M1"),
            _milestone("M2"),
            _milestone("M3"),
        ),
        global_restrictions=(),
        final_completion_definition=(
            "verified",
        ),
    )


def test_initial_checklist_is_pending():
    state = state_from_plan(
        _plan()
    )

    assert [
        item["status"]
        for item in state["milestones"]
    ] == [
        "PENDING",
        "PENDING",
        "PENDING",
    ]

    assert state["master_status"] != "PASS"


def test_every_milestone_has_unique_direct_prompt():
    plan = _plan()

    prompts = [
        turn_checklist_execution_prompt(
            plan=plan,
            index=index,
        )
        for index in range(3)
    ]

    assert len(set(prompts)) == 3

    for index, prompt in enumerate(
        prompts,
        start=1,
    ):
        assert prompt.startswith(
            "NEXUS_MILESTONE_EXECUTION_V1"
        )

        assert (
            "MILESTONE_POSITION="
            + str(index)
            + " of 3"
        ) in prompt

        assert (
            "Do not declare the master turn complete."
            in prompt
        )
