from __future__ import annotations

from pathlib import Path
import subprocess

import nexus.runtime.launcher_upgrade as lu


def test_homebrew_install_present(
    monkeypatch,
):
    monkeypatch.setattr(
        lu,
        "_brew_available",
        lambda: True,
    )

    def runner(
        args: list[str],
    ):
        assert args == [
            "brew",
            "list",
            "--versions",
            "nexus-agent",
        ]

        return subprocess.CompletedProcess(
            args,
            0,
            "nexus-agent 1.7.2\n",
            "",
        )

    assert lu.homebrew_install_present(
        runner=runner
    )


def test_homebrew_absent_is_not_detected(
    monkeypatch,
):
    monkeypatch.setattr(
        lu,
        "_brew_available",
        lambda: False,
    )

    assert (
        lu.homebrew_install_present()
        is False
    )


def test_path_is_within_handles_nested_runtime(
    tmp_path,
):
    root = (
        tmp_path
        / "homebrew"
        / "var"
        / "nexus-agent"
    )

    package = (
        root
        / "venv"
        / "lib"
        / "python3.14"
        / "site-packages"
        / "nexus"
        / "runtime"
        / "launcher_upgrade.py"
    )

    package.parent.mkdir(
        parents=True
    )

    package.write_text(
        "# test\n"
    )

    assert lu.path_is_within(
        package,
        root,
    )


def test_developer_runtime_is_not_claimed_by_formula_prefix(
    tmp_path,
):
    formula = (
        tmp_path
        / "homebrew"
        / "opt"
        / "nexus-agent"
    )

    developer = (
        tmp_path
        / "Users"
        / "dev"
        / "project"
        / ".venv"
        / "lib"
        / "nexus"
    )

    developer.mkdir(
        parents=True
    )

    assert not lu.path_is_within(
        developer,
        formula,
    )
