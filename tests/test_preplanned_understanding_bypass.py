import inspect

from nexus.agent import Agent


def _preplanned_block():
    source = inspect.getsource(
        Agent.run
    )

    marker = (
        "# NEXUS700_PREPLANNED_REASONING_BYPASS_V5"
    )

    start = source.index(marker)

    normal = source.index(
        "else:",
        start,
    )

    return (
        source[start:normal],
        source[normal:],
    )


def test_preplanned_execution_does_not_call_understanding_model():
    block, _ = _preplanned_block()

    assert "understand_task(" not in block
    assert (
        "preplanned_understanding_prompt("
        not in block
    )


def test_preplanned_execution_does_not_call_planner_model():
    block, _ = _preplanned_block()

    assert "plan_task(" not in block


def test_preplanned_execution_uses_canonical_direct_brief():
    block, _ = _preplanned_block()

    assert (
        "self._understanding = None"
        in block
    )
    assert (
        "self._preplanned_execution_brief("
        in block
    )
    assert (
        "self._execution_plan = None"
        in block
    )


def test_normal_understanding_and_planner_paths_remain():
    _, normal = _preplanned_block()

    assert "understand_task(" in normal
    assert "plan_task(" in normal


def test_direct_brief_forbids_recursive_reasoning():
    source = inspect.getsource(
        Agent._preplanned_execution_brief
    )

    assert (
        "Do not perform another Understanding cycle."
        in source
    )
    assert (
        "Do not perform another Planner cycle."
        in source
    )
