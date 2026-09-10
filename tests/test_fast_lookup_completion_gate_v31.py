from pathlib import Path

from nexus.runtime.speed_governor import (
    SpeedGovernor,
)

import pytest


@pytest.fixture(autouse=True)
def _strict_speed_mode(monkeypatch):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )



def allowed_after(*tools):
    governor = SpeedGovernor()

    for tool in tools:
        governor.record_discovery_success(
            tool_name=tool
        )

    return governor.completion_allowed(
        route_name="FAST_LOOKUP"
    )


def test_one_root_listing_is_not_enough():
    allowed, reason = allowed_after(
        "list_files"
    )

    assert not allowed
    assert reason == (
        "INSUFFICIENT_DISCOVERY_EVIDENCE"
    )


def test_two_generic_listings_are_not_enough():
    allowed, reason = allowed_after(
        "list_files",
        "list_files",
    )

    assert not allowed
    assert reason == (
        "NO_TARGETED_DISCOVERY_EVIDENCE"
    )


def test_listing_plus_search_is_enough_floor():
    allowed, reason = allowed_after(
        "list_files",
        "search_files",
    )

    assert allowed
    assert reason is None


def test_search_plus_read_is_enough_floor():
    allowed, reason = allowed_after(
        "search_files",
        "read_file",
    )

    assert allowed
    assert reason is None


def test_complex_route_is_not_gated():
    governor = SpeedGovernor()

    allowed, reason = (
        governor.completion_allowed(
            route_name="COMPLEX"
        )
    )

    assert allowed
    assert reason is None


def test_gate_is_before_final_answer():
    source = Path(
        "nexus/agent.py"
    ).read_text()

    gate = source.index(
        "completion_allowed, completion_reason"
    )

    final = source.index(
        "guard_final_answer(",
        gate,
    )

    assert gate < final
