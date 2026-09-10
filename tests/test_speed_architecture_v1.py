from pathlib import Path

from nexus.runtime.fast_router import (
    COMPLEX,
    EDIT_AND_VERIFY,
    FAST_LOOKUP,
    classify_task,
)
from nexus.runtime.project_context_cache import (
    ProjectContextCache,
)
from nexus.runtime.speed_governor import (
    SpeedGovernor,
    canonical_tool_signature,
)

import pytest


@pytest.fixture(autouse=True)
def _strict_speed_mode(monkeypatch):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )



def test_signature_is_stable():
    first = canonical_tool_signature(
        "search_files",
        {
            "path": "/tmp/x",
            "query": "tree",
        },
    )

    second = canonical_tool_signature(
        "search_files",
        {
            "query": "tree",
            "path": "/tmp/x",
        },
    )

    assert first == second


def test_duplicate_read_is_suppressed():
    governor = SpeedGovernor()

    first = governor.before_tool(
        iteration=1,
        name="search_files",
        arguments={
            "query": "tree",
        },
    )

    second = governor.before_tool(
        iteration=2,
        name="search_files",
        arguments={
            "query": "tree",
        },
    )

    assert first["allow"] is True
    assert second["allow"] is False
    assert (
        second["reason"]
        == "DUPLICATE_READ_ONLY_CALL"
    )


def test_discovery_budget():
    governor = SpeedGovernor(
        discovery_budget=2,
    )

    assert governor.before_tool(
        iteration=1,
        name="read_file",
        arguments={"path": "a"},
    )["allow"]

    assert governor.before_tool(
        iteration=2,
        name="read_file",
        arguments={"path": "b"},
    )["allow"]

    result = governor.before_tool(
        iteration=3,
        name="read_file",
        arguments={"path": "c"},
    )

    assert result["allow"] is False
    assert (
        result["reason"]
        == "DISCOVERY_BUDGET_EXCEEDED"
    )


def test_progress_allows_longer_work():
    governor = SpeedGovernor(
        discovery_budget=2,
    )

    governor.record_progress(
        "write_file"
    )

    for index in range(5):
        result = governor.before_tool(
            iteration=index + 1,
            name="read_file",
            arguments={
                "path": str(index),
            },
        )

        assert result["allow"]


def test_context_cache_reuses_content(
    tmp_path: Path,
):
    path = tmp_path / "AGENTS.md"
    path.write_text("hello")

    cache = ProjectContextCache(
        tmp_path
    )

    first = cache.read(
        "AGENTS.md"
    )

    second = cache.read(
        "AGENTS.md"
    )

    assert first is second

    path.write_text("changed")

    third = cache.read(
        "AGENTS.md"
    )

    assert third is not first
    assert third.content == "changed"


def test_fast_router():
    assert (
        classify_task(
            "find all tree assets"
        )
        == FAST_LOOKUP
    )

    assert (
        classify_task(
            "implement the forest generator"
        )
        == EDIT_AND_VERIFY
    )

    assert (
        classify_task(
            "investigate the architecture"
        )
        == COMPLEX
    )
