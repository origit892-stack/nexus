from nexus.runtime.prompt_milestones import (
    Milestone,
    MilestonePlan,
    reconcile_milestone_mutation_policies,
)


def _m(
    objective,
    policy="READ_ONLY",
):
    return Milestone(
        id="M1",
        title="Test",
        objective=objective,
        requirements=(),
        restrictions=(),
        dependencies=(),
        evidence_required=(),
        completion_definition=(),
        mutation_policy=policy,
    )


def _reconcile(milestone):
    plan = MilestonePlan(
        master_prompt_sha256="x",
        master_prompt="x",
        milestones=(milestone,),
        global_restrictions=(
            "Never modify Nexus",
            "Respect READ-ONLY milestones",
        ),
        final_completion_definition=(),
    )

    return (
        reconcile_milestone_mutation_policies(
            plan
        ).milestones[0]
    )


def test_pure_inspection_remains_read_only():
    assert (
        _reconcile(
            _m(
                "Inspect workspace and report findings"
            )
        ).mutation_policy
        == "READ_ONLY"
    )


def test_implementation_escalates():
    assert (
        _reconcile(
            _m(
                "Implement the package"
            )
        ).mutation_policy
        == "MUTATING"
    )


def test_cli_process_execution_escalates():
    assert (
        _reconcile(
            _m(
                "Exercise the CLI across separate processes"
            )
        ).mutation_policy
        == "MUTATING"
    )


def test_test_execution_escalates():
    assert (
        _reconcile(
            _m(
                "Inspect project and run full tests"
            )
        ).mutation_policy
        == "MUTATING"
    )


def test_global_boundaries_do_not_change_inspection():
    assert (
        _reconcile(
            _m(
                "Inspect workspace"
            )
        ).mutation_policy
        == "READ_ONLY"
    )


def test_existing_mutating_is_never_downgraded():
    assert (
        _reconcile(
            _m(
                "Inspect workspace",
                "MUTATING",
            )
        ).mutation_policy
        == "MUTATING"
    )


def test_unsure_without_execution_stays_fail_closed():
    assert (
        _reconcile(
            _m(
                "Ambiguous analysis",
                "UNSURE",
            )
        ).mutation_policy
        == "UNSURE"
    )
