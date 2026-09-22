import pytest

import nexus.runtime.planner as planner


def test_payload_contract_uses_existing_pass_fail_semantics():
    passed = planner.normalize_planner_critic_payload(
        {
            "verdict": "pass",
            "issues": "",
            "summary": "ok",
        }
    )

    assert passed["verdict"] == "PASS"
    assert passed["issues"] == []

    failed = planner.normalize_planner_critic_payload(
        {
            "verdict": "fail",
            "issues": ["repair needed"],
            "summary": "bad plan",
            "corrected_plan": {},
        }
    )

    assert failed["verdict"] == "FAIL"
    assert failed["corrected_plan"] == {}


def test_payload_rejects_unknown_verdict():
    with pytest.raises(
        planner.PlanningError
    ):
        planner.normalize_planner_critic_payload(
            {
                "verdict": "REPAIR",
                "issues": [],
                "summary": "",
            }
        )


def test_critic_retries_after_malformed_json(
    monkeypatch,
):
    monkeypatch.setattr(
        planner,
        "load_understanding_config",
        lambda: {
            "local_path": "/fake/model",
            "critic_max_tokens": 256,
        },
    )

    monkeypatch.setattr(
        planner,
        "load_project_context",
        lambda project_path: "",
    )

    monkeypatch.setattr(
        planner,
        "_load_model_cached",
        lambda path: (
            object(),
            object(),
            {},
        ),
    )

    outputs = iter(
        [
            (
                "this is not json",
                {"generation": 1},
            ),
            (
                '{"verdict":"PASS",'
                '"issues":[],'
                '"summary":"valid"}',
                {"generation": 2},
            ),
        ]
    )

    monkeypatch.setattr(
        planner,
        "_generate_planner_final",
        lambda **kwargs: next(outputs),
    )

    result = planner.critique_plan(
        user_request="read files",
        understanding={},
        plan={},
        project_path=None,
    )

    assert result["verdict"] == "PASS"
    assert result["_attempt"] == 2
    assert result["_metrics"] == {
        "generation": 2
    }


def test_critic_fails_after_two_bad_outputs(
    monkeypatch,
):
    monkeypatch.setattr(
        planner,
        "load_understanding_config",
        lambda: {
            "local_path": "/fake/model",
            "critic_max_tokens": 256,
        },
    )

    monkeypatch.setattr(
        planner,
        "load_project_context",
        lambda project_path: "",
    )

    monkeypatch.setattr(
        planner,
        "_load_model_cached",
        lambda path: (
            object(),
            object(),
            {},
        ),
    )

    monkeypatch.setattr(
        planner,
        "_generate_planner_final",
        lambda **kwargs: (
            "not json",
            {},
        ),
    )

    with pytest.raises(
        planner.PlanningError,
        match="after 2 attempts",
    ):
        planner.critique_plan(
            user_request="read files",
            understanding={},
            plan={},
            project_path=None,
        )
