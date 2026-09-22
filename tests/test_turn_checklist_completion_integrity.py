from dataclasses import dataclass

from nexus.sessions.runner import (
    _milestone_capability_policy,
    _milestone_result_failure,
)


@dataclass
class Milestone:
    title: str
    objective: str
    requirements: tuple
    restrictions: tuple
    completion_definition: tuple
    mutation_policy: str = "UNSURE"


@dataclass
class Plan:
    global_restrictions: tuple
    milestones: tuple


def test_agent_exception_text_is_failure():
    result = (
        "AGENT_EXCEPTION=RuntimeError: "
        "NEXUS_PLANNING_FAILED: bad output"
    )

    assert (
        _milestone_result_failure(
            result
        )
        == result
    )


def test_normal_result_is_not_failure():
    assert (
        _milestone_result_failure(
            "MILESTONE COMPLETE"
        )
        is None
    )


def test_read_only_requirement_sets_capability():
    plan = Plan(
        global_restrictions=(),
        milestones=(
            Milestone(
                title="Inspect workspace",
                objective=(
                    "Report initial state"
                ),
                requirements=(
                    "Read-only inspection, "
                    "no file modifications",
                ),
                restrictions=(),
                completion_definition=(
                    "Report state without "
                    "modifying files",
                ),
            ),
        ),
    )

    assert (
        _milestone_capability_policy(
            plan,
            milestone_index=0,
        )
        == "READ_ONLY"
    )


def test_mutating_milestone_remains_normal():
    plan = Plan(
        global_restrictions=(),
        milestones=(
            Milestone(
                title="Create file",
                objective="Write unit tests",
                requirements=(
                    "Create tests/test_x.py",
                ),
                restrictions=(
                    "Do not modify outside workspace",
                ),
                completion_definition=(
                    "Test file exists",
                ),
                    mutation_policy="MUTATING",
),
        ),
    )

    assert (
        _milestone_capability_policy(
            plan,
            milestone_index=0,
        )
        == "NORMAL"
    )


def _policy(
    *,
    objective="",
    requirements=(),
    restrictions=(),
    completion=(),
    global_restrictions=(),
    mutation_policy="UNSURE",
):
    plan = Plan(
        global_restrictions=(
            global_restrictions
        ),
        milestones=(
            Milestone(
                title="Test milestone",
                objective=objective,
                requirements=requirements,
                restrictions=restrictions,
                completion_definition=completion,
                mutation_policy=mutation_policy,
            ),
        ),
    )

    return _milestone_capability_policy(
        plan,
        milestone_index=0,
    )


def test_absolute_do_not_modify_is_read_only():
    assert (
        _policy(
            restrictions=(
                "Do not modify any files",
            ),
        )
        == "READ_ONLY"
    )


def test_read_only_requirement_is_read_only():
    assert (
        _policy(
            requirements=(
                "READ-ONLY inspection",
            ),
        )
        == "READ_ONLY"
    )


def test_without_modifying_is_read_only():
    assert (
        _policy(
            completion=(
                "Report state without modifying files",
            ),
        )
        == "READ_ONLY"
    )


def test_outside_workspace_is_scope_not_read_only():
    assert (
        _policy(
            objective="Create test file",
            restrictions=(
                "Do not modify outside workspace",
            ),
                mutation_policy="MUTATING",
)
        == "NORMAL"
    )


def test_outside_named_project_is_scope_not_read_only():
    assert (
        _policy(
            objective="Create calculator.py",
            restrictions=(
                "Do not modify BunkerGame or paths "
                "outside /tmp/sandbox",
            ),
                mutation_policy="MUTATING",
)
        == "NORMAL"
    )


def test_global_outside_boundary_does_not_freeze_mutation():
    assert (
        _policy(
            objective="Write unit tests",
            global_restrictions=(
                "No modifications to BunkerGame "
                "or paths outside /tmp/sandbox",
            ),
                mutation_policy="MUTATING",
)
        == "NORMAL"
    )


def test_explicit_global_read_only_remains_sticky():
    assert (
        _policy(
            objective="Inspect files",
            global_restrictions=(
                "READ_ONLY",
            ),
        )
        == "READ_ONLY"
    )


def test_named_protected_target_does_not_freeze_milestone():
    assert (
        _policy(
            objective="Create file",
            global_restrictions=(
                "No modification to Nexus itself",
            ),
                mutation_policy="MUTATING",
)
        == "NORMAL"
    )


def test_named_project_boundary_does_not_freeze_milestone():
    assert (
        _policy(
            objective="Create file",
            global_restrictions=(
                "Do not modify BunkerGame",
            ),
                mutation_policy="MUTATING",
)
        == "NORMAL"
    )


def test_absolute_file_prohibition_remains_read_only():
    assert (
        _policy(
            restrictions=(
                "Do not modify any files",
            ),
        )
        == "READ_ONLY"
    )



def test_missing_explicit_policy_fails_closed_even_for_mutating_text():
    plan = Plan(
        global_restrictions=(),
        milestones=(
            Milestone(
                title="Create file",
                objective="Write unit tests",
                requirements=(
                    "Create tests/test_x.py",
                ),
                restrictions=(),
                completion_definition=(
                    "Test file exists",
                ),
                mutation_policy="UNSURE",
            ),
        ),
    )

    assert (
        _milestone_capability_policy(
            plan,
            milestone_index=0,
        )
        == "READ_ONLY"
    )
