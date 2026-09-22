from __future__ import annotations

from pathlib import Path
import ast


SOURCE = Path(
    "nexus/runtime/understanding.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(SOURCE)


def _fn():
    return next(
        node
        for node in TREE.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name
            == "compile_master_prompt"
        )
    )


def _direct_calls():
    result = []

    for node in ast.walk(_fn()):
        if (
            isinstance(node, ast.Call)
            and isinstance(
                node.func,
                ast.Name,
            )
        ):
            result.append(
                node.func.id
            )

    return result


def test_uses_real_config_loader():
    calls = _direct_calls()

    assert (
        calls.count(
            "load_understanding_config"
        )
        == 1
    )

    assert (
        "understanding_config"
        not in calls
    )


def test_uses_real_cached_model_loader():
    calls = _direct_calls()

    assert (
        calls.count(
            "_load_model_cached"
        )
        == 1
    )

    assert (
        "_load_understanding_model"
        not in calls
    )


def test_uses_generation_runtime():
    calls = _direct_calls()

    assert "_generate" in calls


def test_uses_milestone_parser():
    calls = _direct_calls()

    assert (
        "milestone_plan_from_payload"
        in calls
    )
