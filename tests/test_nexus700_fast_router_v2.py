from pathlib import Path
import subprocess

from nexus.runtime.fast_lookup_engine import (
    execute_fast_lookup,
)


def _write(
    root: Path,
    relative: str,
    content: str,
):
    path = (
        root
        / relative
    )

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    path.write_text(
        content,
        encoding="utf-8",
    )

    return path


def test_exact_file_heading(
    tmp_path,
):
    _write(
        tmp_path,
        "docs/README.md",
        "# Hello\nbody\n",
    )

    result = execute_fast_lookup(
        task=(
            "Read docs/README.md "
            "and report its first "
            "Markdown heading."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "# Hello" in result.answer
    assert (
        result.capability
        == "filesystem_lookup"
    )


def test_exact_file_read(
    tmp_path,
):
    _write(
        tmp_path,
        "config/example.txt",
        "alpha\nbeta\n",
    )

    result = execute_fast_lookup(
        task=(
            "Read config/example.txt "
            "and show its contents."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "alpha" in result.answer
    assert "beta" in result.answer


def test_exact_file_existence(
    tmp_path,
):
    _write(
        tmp_path,
        "src/main.py",
        "print('x')\n",
    )

    result = execute_fast_lookup(
        task=(
            "Check whether "
            "src/main.py exists."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "exists" in result.answer


def test_missing_exact_file(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Check whether "
            "docs/missing.md exists."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "not found" in result.answer


def test_recursive_filename_search(
    tmp_path,
):
    _write(
        tmp_path,
        "a/b/pyproject.toml",
        "[project]\n",
    )

    result = execute_fast_lookup(
        task=(
            "Find pyproject.toml "
            "anywhere under the workspace."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert (
        "a/b/pyproject.toml"
        in result.answer
    )


def test_recursive_filename_absence(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Determine whether "
            "pyproject.toml exists "
            "anywhere under the workspace."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert (
        "no pyproject.toml found"
        in result.answer.lower()
    )


def test_literal_grep(
    tmp_path,
):
    _write(
        tmp_path,
        "src/a.py",
        "hello = 'needle'\n",
    )

    _write(
        tmp_path,
        "src/b.py",
        "nothing = True\n",
    )

    result = execute_fast_lookup(
        task=(
            'Search for "needle" '
            "in src/."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "src/a.py" in result.answer
    assert "needle" in result.answer
    assert (
        result.capability
        == "literal_grep"
    )


def test_literal_grep_negative(
    tmp_path,
):
    _write(
        tmp_path,
        "src/a.py",
        "hello = 'world'\n",
    )

    result = execute_fast_lookup(
        task=(
            'Search for "needle" '
            "in src/."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert (
        "no literal matches"
        in result.answer.lower()
    )


def test_directory_listing(
    tmp_path,
):
    _write(
        tmp_path,
        "src/a.py",
        "x=1\n",
    )

    _write(
        tmp_path,
        "src/b.py",
        "x=2\n",
    )

    result = execute_fast_lookup(
        task=(
            "List files in src/."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "a.py" in result.answer
    assert "b.py" in result.answer
    assert (
        result.capability
        == "directory_listing"
    )


def test_path_escape_falls_back(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Read ../secret.md "
            "and show its contents."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_write_request_falls_back(
    tmp_path,
):
    result = execute_fast_lookup(
        task=(
            "Create src/new.py "
            "with hello world."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_reasoning_request_falls_back(
    tmp_path,
):
    _write(
        tmp_path,
        "README.md",
        "# Project\n",
    )

    result = execute_fast_lookup(
        task=(
            "Explain the architecture "
            "and recommend how to redesign it."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_git_status(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    _write(
        tmp_path,
        "a.txt",
        "hello\n",
    )

    result = execute_fast_lookup(
        task=(
            "Show git status."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert (
        result.capability
        == "git_status"
    )


def test_git_branch(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "checkout",
            "-q",
            "-b",
            "test-branch",
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task=(
            "What is the current "
            "git branch?"
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert "test-branch" in result.answer


def test_git_head_after_commit(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "config",
            "user.email",
            "test@example.com",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "config",
            "user.name",
            "Test",
        ],
        check=True,
    )

    _write(
        tmp_path,
        "a.txt",
        "hello\n",
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "add",
            "a.txt",
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "commit",
            "-qm",
            "initial",
        ],
        check=True,
    )

    expected = subprocess.check_output(
        [
            "git",
            "-C",
            str(tmp_path),
            "rev-parse",
            "HEAD",
        ],
        text=True,
    ).strip()

    result = execute_fast_lookup(
        task=(
            "Report the current "
            "git HEAD commit hash."
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert expected in result.answer


def test_zero_model_contract(
    tmp_path,
):
    _write(
        tmp_path,
        "README.md",
        "# Fast\n",
    )

    result = execute_fast_lookup(
        task=(
            "Read README.md "
            "and report its heading."
        ),
        workspace=tmp_path,
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


def test_git_commit_request_never_fast_routes(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task=(
            "Git commit all changes "
            "with message test."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_git_reset_request_never_fast_routes(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task=(
            "Git reset --hard HEAD."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_git_checkout_request_never_fast_routes(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task=(
            "Git checkout main."
        ),
        workspace=tmp_path,
    )

    assert not result.handled


def test_git_push_request_never_fast_routes(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task="Git push origin main.",
        workspace=tmp_path,
    )

    assert not result.handled


def test_git_status_remains_fast_route(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task="Show git status.",
        workspace=tmp_path,
    )

    assert result.handled

    assert (
        result.capability
        == "git_status"
    )


def test_git_branch_remains_fast_route(
    tmp_path,
):
    subprocess.run(
        [
            "git",
            "init",
            "-q",
            str(tmp_path),
        ],
        check=True,
    )

    subprocess.run(
        [
            "git",
            "-C",
            str(tmp_path),
            "checkout",
            "-qb",
            "router-test",
        ],
        check=True,
    )

    result = execute_fast_lookup(
        task=(
            "What is the current "
            "git branch?"
        ),
        workspace=tmp_path,
    )

    assert result.handled
    assert (
        result.capability
        == "git_branch"
    )

    assert (
        "router-test"
        in result.answer
    )
