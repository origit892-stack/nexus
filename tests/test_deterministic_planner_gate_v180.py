import nexus.runtime.planner as planner


def understanding():
    return {
        "mutation_policy": "READ_ONLY",
        "recommended_plan": [
            "read requested files",
        ],
    }


def valid_plan():
    return {
        "current_phase": "read requested files",
        "authorized_now": [
            "read requested files",
        ],
        "forbidden_now": [
            "do not modify files",
        ],
        "deferred_actions": [],
        "approval_gates": [],
        "targets": [],
        "search_strategy": [],
        "evidence_plan": [],
        "evaluation_plan": [],
        "selection_strategy": [],
        "first_actions": [
            "read requested files",
        ],
        "stop_conditions": [
            "requested facts reported",
        ],
    }


def test_valid_plan_does_not_call_critic(
    monkeypatch,
):
    called = {
        "critic": False,
    }

    def fail_if_called(**kwargs):
        called["critic"] = True
        raise AssertionError(
            "critic should not run"
        )

    monkeypatch.setattr(
        planner,
        "critique_plan",
        fail_if_called,
    )

    result = planner.approve_or_repair_plan(
        user_request="read files",
        understanding=understanding(),
        plan=valid_plan(),
        project_path=None,
        progress=None,
    )

    assert called["critic"] is False

    critic = result[
        "_nexus_planner_critic"
    ]

    assert critic["verdict"] == "PASS"

    assert (
        critic["source"]
        == "DETERMINISTIC_SEMANTIC_GATE"
    )


def test_semantically_invalid_plan_still_uses_critic(
    monkeypatch,
):
    called = {
        "critic": False,
        "validation_calls": 0,
    }

    real_validate = (
        planner.validate_plan_semantics
    )

    def controlled_validation(
        *,
        understanding,
        plan,
    ):
        called[
            "validation_calls"
        ] += 1

        # Force the initial reconciled plan down the
        # semantic-repair path. After the critic supplies
        # its corrected plan, use the real validator.
        if (
            called["validation_calls"]
            == 1
        ):
            return [
                "forced semantic test error"
            ]

        return real_validate(
            understanding=understanding,
            plan=plan,
        )

    def fake_critic(**kwargs):
        called["critic"] = True

        return {
            "verdict": "FAIL",
            "issues": [
                "forced semantic test error",
            ],
            "summary": (
                "Return a corrected plan."
            ),
            "corrected_plan": valid_plan(),
        }

    monkeypatch.setattr(
        planner,
        "validate_plan_semantics",
        controlled_validation,
    )

    monkeypatch.setattr(
        planner,
        "critique_plan",
        fake_critic,
    )

    result = planner.approve_or_repair_plan(
        user_request="read files",
        understanding=understanding(),
        plan=valid_plan(),
        project_path=None,
        progress=None,
    )

    assert called["critic"] is True

    assert (
        called["validation_calls"]
        >= 2
    )

    assert result[
        "authorized_now"
    ]

    assert (
        result[
            "_nexus_planner_critic"
        ][
            "verdict"
        ]
        == "PASS"
    )



def test_reconciler_can_fix_plan_before_critic(
    monkeypatch,
):
    called = {
        "critic": False,
    }

    def critic_must_not_run(**kwargs):
        called["critic"] = True
        raise AssertionError(
            "Critic should not run after deterministic "
            "reconciliation makes the plan valid."
        )

    monkeypatch.setattr(
        planner,
        "critique_plan",
        critic_must_not_run,
    )

    bad = valid_plan()

    # This looks incomplete before reconciliation, but
    # recommended_plan provides current authorized work.
    bad["authorized_now"] = []
    bad["first_actions"] = []

    result = planner.approve_or_repair_plan(
        user_request="read files",
        understanding=understanding(),
        plan=bad,
        project_path=None,
        progress=None,
    )

    assert called["critic"] is False

    assert result[
        "authorized_now"
    ] == [
        "read requested files"
    ]

    assert result[
        "first_actions"
    ] == [
        "read requested files"
    ]

    assert (
        result[
            "_nexus_planner_critic"
        ][
            "source"
        ]
        == "DETERMINISTIC_SEMANTIC_GATE"
    )
