from nexus.runtime.prompt_milestones import (
    Milestone,
    MilestonePlan,
    master_prompt_hash,
    milestone_plan_from_payload,
    validate_milestone_plan,
)
from nexus.sessions.runner import (
    _milestone_capability_policy,
)


def _milestone(
    policy,
    mid="M1",
):
    return Milestone(
        id=mid,
        title="Test",
        objective="Test",
        requirements=(),
        restrictions=(),
        dependencies=(),
        evidence_required=(),
        completion_definition=(),
        mutation_policy=policy,
    )


def _plan(*items):
    return MilestonePlan(
        master_prompt_sha256="x",
        master_prompt="x",
        milestones=items,
        global_restrictions=(
            "Respect READ-ONLY milestones",
            "Never modify Nexus",
        ),
        final_completion_definition=(),
    )


def test_read_only_policy():
    assert (
        _milestone_capability_policy(
            _plan(
                _milestone("READ_ONLY")
            ),
            milestone_index=0,
        )
        == "READ_ONLY"
    )


def test_mutating_policy():
    assert (
        _milestone_capability_policy(
            _plan(
                _milestone("MUTATING")
            ),
            milestone_index=0,
        )
        == "NORMAL"
    )


def test_unsure_fails_closed():
    assert (
        _milestone_capability_policy(
            _plan(
                _milestone("UNSURE")
            ),
            milestone_index=0,
        )
        == "READ_ONLY"
    )


def test_global_meta_read_only_does_not_poison():
    assert (
        _milestone_capability_policy(
            _plan(
                _milestone("MUTATING")
            ),
            milestone_index=0,
        )
        == "NORMAL"
    )


def test_final_normal_when_mutation_exists():
    assert (
        _milestone_capability_policy(
            _plan(
                _milestone(
                    "READ_ONLY",
                    "M1",
                ),
                _milestone(
                    "MUTATING",
                    "M2",
                ),
            ),
            milestone_index=None,
        )
        == "NORMAL"
    )


def test_policy_roundtrip():
    prompt = "master"

    payload = {
        "master_prompt_sha256":
            master_prompt_hash(prompt),
        "milestones": [
            {
                "id": "M1",
                "title": "Implement",
                "objective": "Create",
                "requirements": [],
                "restrictions": [],
                "dependencies": [],
                "evidence_required": [],
                "completion_definition": [],
                "mutation_policy":
                    "MUTATING",
            },
        ],
        "global_restrictions": [],
        "final_completion_definition": [],
    }

    assert not validate_milestone_plan(
        prompt=prompt,
        payload=payload,
    )

    plan = milestone_plan_from_payload(
        prompt=prompt,
        payload=payload,
    )

    assert (
        plan.milestones[0]
        .mutation_policy
        == "MUTATING"
    )

    assert (
        plan.to_dict()
        ["milestones"][0]
        ["mutation_policy"]
        == "MUTATING"
    )


def test_missing_policy_rejected():
    prompt = "master"

    payload = {
        "master_prompt_sha256":
            master_prompt_hash(prompt),
        "milestones": [
            {
                "id": "M1",
                "title": "Test",
                "objective": "Test",
                "requirements": [],
                "restrictions": [],
                "dependencies": [],
                "evidence_required": [],
                "completion_definition": [],
            },
        ],
        "global_restrictions": [],
        "final_completion_definition": [],
    }

    errors = validate_milestone_plan(
        prompt=prompt,
        payload=payload,
    )

    assert any(
        "missing mutation_policy"
        in error
        for error in errors
    )
