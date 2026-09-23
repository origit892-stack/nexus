import pytest

import nexus.runtime.understanding as understanding
from nexus.runtime.prompt_milestones import master_prompt_hash


class DummyModel:
    pass


class DummyTokenizer:
    pass


def test_invalid_json_first_repair_reaches_second_repair(
    monkeypatch,
):
    outputs = iter(
        (
            (
                '{"master_prompt_sha256":"wrong",'
                '"milestones":[]}'
            ),
            "not json",
            (
                '{"master_prompt_sha256":"'
                + master_prompt_hash(
                    "Build feature."
                )
                + '","milestones":['
                '{"id":"M1",'
                '"title":"Build",'
                '"objective":"Build feature",'
                '"requirements":["Build feature"],'
                '"restrictions":[],'
                '"dependencies":[],'
                '"evidence_required":[],'
                '"completion_definition":["Feature exists"],'
                '"mutation_policy":"MUTATING"}],'
                '"global_restrictions":[],'
                '"final_completion_definition":'
                '["Feature exists"]}'
            ),
        )
    )

    def fake_load(_):
        return (
            DummyModel(),
            DummyTokenizer(),
            0.0,
        )

    def fake_generate(**kwargs):
        return (
            next(outputs),
            {},
        )

    monkeypatch.setattr(
        understanding,
        "_load_model_cached",
        fake_load,
    )

    monkeypatch.setattr(
        understanding,
        "_generate",
        fake_generate,
    )

    monkeypatch.setattr(
        understanding,
        "load_understanding_config",
        lambda: {
            "local_path": "dummy",
            "repair_max_tokens": 128,
        },
    )

    progress = []

    plan, metrics = (
        understanding.compile_master_prompt(
            "Build feature.",
            progress=progress.append,
        )
    )

    assert len(plan.milestones) == 1
    assert (
        plan.milestones[0].mutation_policy
        == "MUTATING"
    )
    assert metrics["repairs_used"] == 2

    assert (
        "MILESTONE COMPILER: SCHEMA REPAIR 1"
        in progress
    )

    assert (
        "MILESTONE COMPILER: SCHEMA REPAIR 2"
        in progress
    )


def test_two_invalid_json_repairs_fail_cleanly(
    monkeypatch,
):
    outputs = iter(
        (
            "not json",
            "still not json",
            "also not json",
        )
    )

    monkeypatch.setattr(
        understanding,
        "_load_model_cached",
        lambda _: (
            DummyModel(),
            DummyTokenizer(),
            0.0,
        ),
    )

    monkeypatch.setattr(
        understanding,
        "_generate",
        lambda **kwargs: (
            next(outputs),
            {},
        ),
    )

    monkeypatch.setattr(
        understanding,
        "load_understanding_config",
        lambda: {
            "local_path": "dummy",
            "repair_max_tokens": 128,
        },
    )

    with pytest.raises(
        ValueError,
        match=(
            "INVALID_MILESTONE_PLAN_"
            "AFTER_REPAIRS"
        ),
    ):
        understanding.compile_master_prompt(
            "Build feature."
        )
