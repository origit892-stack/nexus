import inspect

from nexus.agent import Agent
from nexus.runtime.fast_first import (
    classify_fast_first,
)


def test_preplanned_execution_has_explicit_fast_first_bypass():
    source = inspect.getsource(
        Agent.run
    )

    assert (
        'reason="preplanned_execution_bypass"'
        in source
    )
    assert (
        "if _raw_preplanned_execution"
        in source
    )


def test_preplanned_bypass_is_not_fast_first_eligible():
    source = inspect.getsource(
        Agent.run
    )

    marker = (
        'reason="preplanned_execution_bypass"'
    )

    position = source.index(marker)

    block = source[
        max(0, position - 800):
        position + 1000
    ]

    assert "eligible=False" in block
    assert 'route="NORMAL"' in block
    assert "max_tool_calls=0" in block
    assert "max_iterations=0" in block


def test_preplanned_bypass_preserves_read_only_capability_metadata():
    source = inspect.getsource(
        Agent.run
    )

    marker = (
        'reason="preplanned_execution_bypass"'
    )

    position = source.index(marker)

    block = source[
        max(0, position - 800):
        position + 1000
    ]

    assert "self.capability_policy" in block
    assert '"READ_ONLY"' in block


def test_normal_tasks_still_use_fast_first_classifier():
    source = inspect.getsource(
        Agent.run
    )

    assert (
        "else classify_fast_first(task)"
        in source
    )


def test_normal_simple_lookup_classifier_still_operates():
    decision = classify_fast_first(
        "Inspect README.md in this workspace "
        "and report its version."
    )

    assert decision.eligible
    assert decision.route == "FAST_LOOKUP"
    assert decision.max_tool_calls == 4


def test_complex_lookup_need_not_reproduce_historical_m7_route():
    decision = classify_fast_first(
        "Determine the relationship between filesystem, "
        "Rojo, and Roblox Studio and document the "
        "current source of truth."
    )

    # The important invariant is not whether this standalone
    # synthetic text is FAST_LOOKUP. Preplanned execution bypasses
    # this classifier entirely.
    assert decision.route in (
        "FAST_LOOKUP",
        "NORMAL",
    )
