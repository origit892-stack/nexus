from pathlib import Path

from nexus.runtime.fast_lookup_engine import (
    execute_fast_lookup,
)


def test_zero_llm_lookup_finds_absence_and_heading(
    tmp_path,
):
    docs = (
        tmp_path
        / "docs"
        / "agents"
    )

    docs.mkdir(
        parents=True
    )

    (
        docs
        / "README.md"
    ).write_text(
        "# Agent Documentation\n\nBody\n",
        encoding="utf-8",
    )

    result = execute_fast_lookup(
        task=(
            "Read-only verification task. "
            "Determine whether any pyproject.toml "
            "exists anywhere under this workspace. "
            "Then read docs/agents/README.md and "
            "report its exact first Markdown heading."
        ),
        workspace=tmp_path,
    )

    assert result.handled

    assert (
        "no pyproject.toml found anywhere"
        in result.answer.lower()
    )

    assert (
        "# Agent Documentation"
        in result.answer
    )

    assert (
        result.filesystem_operations
        <= 2
    )

    payload = result.to_dict()

    assert (
        payload[
            "director_model_calls"
        ]
        == 0
    )

    assert (
        payload[
            "understanding_model_calls"
        ]
        == 0
    )

    assert (
        payload[
            "planner_model_calls"
        ]
        == 0
    )

    assert (
        payload[
            "completion_model_calls"
        ]
        == 0
    )


def test_zero_llm_lookup_finds_existing_exact_name(
    tmp_path,
):
    nested = (
        tmp_path
        / "a"
        / "b"
    )

    nested.mkdir(
        parents=True
    )

    (
        nested
        / "pyproject.toml"
    ).write_text(
        "[project]\nname='x'\n",
        encoding="utf-8",
    )

    result = execute_fast_lookup(
        task=(
            "Find pyproject.toml "
            "anywhere in the workspace."
        ),
        workspace=tmp_path,
    )

    assert result.handled

    assert (
        "a/b/pyproject.toml"
        in result.answer
    )


def test_zero_llm_lookup_rejects_path_escape(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Read ../secret.md "
            "and report its heading."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_zero_llm_lookup_does_not_modify_files(
    tmp_path,
):
    readme = (
        tmp_path
        / "README.md"
    )

    readme.write_text(
        "# Before\n",
        encoding="utf-8",
    )

    before = (
        readme.read_bytes()
    )

    result = execute_fast_lookup(
        task=(
            "Read README.md "
            "and report its heading."
        ),
        workspace=tmp_path,
    )

    after = (
        readme.read_bytes()
    )

    assert result.handled
    assert before == after


def test_zero_llm_lookup_returns_unhandled_without_targets(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Tell me something interesting."
        ),
        workspace=tmp_path,
    )

    assert not result.handled
