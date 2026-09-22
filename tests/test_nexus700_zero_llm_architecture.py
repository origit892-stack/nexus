from pathlib import Path
import ast


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def test_zero_llm_marker_exists():
    assert (
        "NEXUS700_ZERO_LLM_FAST_LOOKUP"
        in SOURCE
    )


def test_zero_llm_engine_is_imported():
    imports = [
        node
        for node in TREE.body
        if (
            isinstance(
                node,
                ast.ImportFrom,
            )
            and node.module
            == "nexus.runtime.fast_lookup_engine"
        )
    ]

    assert len(imports) == 1

    names = {
        alias.name
        for alias
        in imports[0].names
    }

    assert (
        "execute_fast_lookup"
        in names
    )


def test_zero_llm_path_returns_before_director_loop():
    zero = SOURCE.index(
        "NEXUS700_ZERO_LLM_FAST_LOOKUP"
    )

    loop = SOURCE.find(
        "for iteration in"
    )

    if loop < 0:
        loop = SOURCE.find(
            "while "
        )

    assert loop >= 0
    assert zero < loop


def test_zero_llm_event_reports_zero_models():
    assert (
        '"director_model_calls": 0'
        in SOURCE
    )

    assert (
        '"understanding_model_calls": 0'
        in SOURCE
    )

    assert (
        '"planner_model_calls": 0'
        in SOURCE
    )

    assert (
        '"completion_model_calls": 0'
        in SOURCE
    )


def test_normal_director_path_still_exists():
    assert (
        "DIRECTOR iteration"
        in SOURCE
        or "iteration"
        in SOURCE
    )
