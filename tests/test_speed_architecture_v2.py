from nexus.runtime.fast_router import (
    classify_task,
)
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



def test_fast_lookup_budget_is_small():
    route = classify_task(
        "find all tree assets"
    )

    assert route.name == "FAST_LOOKUP"
    assert route.discovery_budget == 8
    assert route.action_iteration == 5


def test_duplicate_is_blocked_immediately():
    governor = SpeedGovernor(
        discovery_budget=10,
    )

    first = governor.before_tool(
        iteration=1,
        name="search_files",
        arguments={
            "query": "tree",
            "path": "/tmp/game",
        },
    )

    second = governor.before_tool(
        iteration=2,
        name="search_files",
        arguments={
            "path": "/tmp/game",
            "query": "tree",
        },
    )

    assert first["allow"]
    assert not second["allow"]

    assert (
        second["reason"]
        == "DUPLICATE_READ_ONLY_CALL"
    )


def test_discovery_budget_blocks_only_reads():
    governor = SpeedGovernor(
        discovery_budget=1,
    )

    first = governor.before_tool(
        iteration=1,
        name="read_file",
        arguments={"path": "a"},
    )

    second = governor.before_tool(
        iteration=2,
        name="read_file",
        arguments={"path": "b"},
    )

    write = governor.before_tool(
        iteration=3,
        name="write_file",
        arguments={
            "path": "x",
            "content": "x",
        },
    )

    assert first["allow"]
    assert not second["allow"]
    assert write["allow"]


def test_progress_unlocks_discovery():
    governor = SpeedGovernor(
        discovery_budget=1,
    )

    governor.record_progress(
        "write_file"
    )

    for index in range(6):
        result = governor.before_tool(
            iteration=index + 1,
            name="read_file",
            arguments={
                "path": str(index),
            },
        )

        assert result["allow"]


def test_speed_report_tracks_cache():
    governor = SpeedGovernor()

    governor.record_tool_timing(
        name="read_file",
        duration=0.0,
        cached=True,
    )

    governor.record_tool_timing(
        name="search_files",
        duration=0.125,
        cached=False,
    )

    report = governor.report()

    assert report["cache_hits"] == 1
    assert report["tool_calls"] == 2
    assert report["tool_seconds"] >= 0.125
