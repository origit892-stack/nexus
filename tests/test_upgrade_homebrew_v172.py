from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

import nexus.runtime.launcher_upgrade as lu


class FakeHomebrew:
    def __init__(
        self,
        *,
        brew_root: Path,
        formula_prefix: Path,
        cellar: Path,
        version: str,
        upgrade_version: str,
    ):
        self.brew_root = brew_root
        self.formula_prefix = (
            formula_prefix
        )
        self.cellar = cellar
        self.version = version
        self.upgrade_version = (
            upgrade_version
        )
        self.calls: list[
            list[str]
        ] = []

    def __call__(
        self,
        args: list[str],
    ):
        self.calls.append(
            list(args)
        )

        if args == [
            "brew",
            "--prefix",
        ]:
            return subprocess.CompletedProcess(
                args,
                0,
                str(self.brew_root)
                + "\n",
                "",
            )

        if args == [
            "brew",
            "--prefix",
            "nexus-agent",
        ]:
            return subprocess.CompletedProcess(
                args,
                0,
                str(
                    self.formula_prefix
                )
                + "\n",
                "",
            )

        if args == [
            "brew",
            "--cellar",
            "nexus-agent",
        ]:
            return subprocess.CompletedProcess(
                args,
                0,
                str(self.cellar)
                + "\n",
                "",
            )

        if args == [
            "brew",
            "list",
            "--versions",
            "nexus-agent",
        ]:
            return subprocess.CompletedProcess(
                args,
                0,
                "nexus-agent "
                + self.version
                + "\n",
                "",
            )

        if args[:2] == [
            "brew",
            "upgrade",
        ]:
            self.version = (
                self.upgrade_version
            )

            return subprocess.CompletedProcess(
                args,
                0,
                "upgraded\n",
                "",
            )

        if (
            len(args) == 2
            and args[1] == "--version"
        ):
            return subprocess.CompletedProcess(
                args,
                0,
                "Nexus "
                + self.version
                + "\n",
                "",
            )

        return subprocess.CompletedProcess(
            args,
            1,
            "",
            "unexpected call",
        )


def make_formula_topology(
    tmp_path: Path,
):
    brew_root = (
        tmp_path
        / "homebrew"
    )

    formula_prefix = (
        brew_root
        / "opt"
        / "nexus-agent"
    )

    cellar = (
        brew_root
        / "Cellar"
        / "nexus-agent"
    )

    formula_launcher = (
        formula_prefix
        / "bin"
        / "nexus"
    )

    formula_launcher.parent.mkdir(
        parents=True
    )

    formula_launcher.write_text(
        "#!/bin/sh\n"
    )

    formula_launcher.chmod(
        0o755
    )

    runtime_launcher = (
        brew_root
        / "var"
        / "nexus-agent"
        / "venv"
        / "bin"
        / "nexus"
    )

    runtime_launcher.parent.mkdir(
        parents=True
    )

    runtime_launcher.write_text(
        "#!/bin/sh\n"
    )

    runtime_launcher.chmod(
        0o755
    )

    path_dir = (
        tmp_path
        / "path-bin"
    )

    path_dir.mkdir()

    return {
        "brew_root": brew_root,
        "formula_prefix": (
            formula_prefix
        ),
        "cellar": cellar,
        "formula_launcher": (
            formula_launcher
        ),
        "runtime_launcher": (
            runtime_launcher
        ),
        "path_dir": path_dir,
    }


def test_homebrew_runtime_path_matches_real_formula_layout(
    tmp_path,
):
    layout = make_formula_topology(
        tmp_path
    )

    fake = FakeHomebrew(
        brew_root=layout[
            "brew_root"
        ],
        formula_prefix=layout[
            "formula_prefix"
        ],
        cellar=layout[
            "cellar"
        ],
        version="1.7.1",
        upgrade_version="1.7.2",
    )

    assert (
        lu.homebrew_runtime_root(
            runner=fake
        )
        == (
            layout[
                "brew_root"
            ]
            / "var"
            / "nexus-agent"
        )
    )

    assert (
        lu.homebrew_runtime_launcher(
            runner=fake
        )
        == layout[
            "runtime_launcher"
        ]
    )


def test_formula_launcher_matches_brew_prefix(
    tmp_path,
):
    layout = make_formula_topology(
        tmp_path
    )

    fake = FakeHomebrew(
        brew_root=layout[
            "brew_root"
        ],
        formula_prefix=layout[
            "formula_prefix"
        ],
        cellar=layout[
            "cellar"
        ],
        version="1.7.1",
        upgrade_version="1.7.2",
    )

    assert (
        lu.homebrew_formula_launcher(
            runner=fake
        )
        == layout[
            "formula_launcher"
        ]
    )


def test_homebrew_upgrade_repairs_shadowed_launcher(
    tmp_path,
    monkeypatch,
):
    layout = make_formula_topology(
        tmp_path
    )

    stale = (
        tmp_path
        / "developer"
        / "venv"
        / "bin"
        / "nexus"
    )

    stale.parent.mkdir(
        parents=True
    )

    stale.write_text(
        "#!/bin/sh\n"
    )

    stale.chmod(
        0o755
    )

    command = (
        layout[
            "path_dir"
        ]
        / "nexus"
    )

    command.symlink_to(
        stale
    )

    fake = FakeHomebrew(
        brew_root=layout[
            "brew_root"
        ],
        formula_prefix=layout[
            "formula_prefix"
        ],
        cellar=layout[
            "cellar"
        ],
        version="1.7.1",
        upgrade_version="1.7.2",
    )

    monkeypatch.setattr(
        lu.shutil,
        "which",
        lambda name, path=None: (
            str(command)
            if name == "nexus"
            else "/brew/bin/brew"
        ),
    )

    result = lu.upgrade_nexus(
        path_env=str(
            layout[
                "path_dir"
            ]
        ),
        runner=fake,
        method="HOMEBREW",
    )

    assert result.version == "1.7.2"
    assert (
        result.launcher_repaired
        is True
    )

    assert (
        command.resolve()
        == layout[
            "formula_launcher"
        ].resolve()
    )

    assert [
        "brew",
        "upgrade",
        lu.FORMULA,
    ] in fake.calls


def test_homebrew_upgrade_keeps_correct_launcher(
    tmp_path,
    monkeypatch,
):
    layout = make_formula_topology(
        tmp_path
    )

    command = (
        layout[
            "path_dir"
        ]
        / "nexus"
    )

    command.symlink_to(
        layout[
            "formula_launcher"
        ]
    )

    fake = FakeHomebrew(
        brew_root=layout[
            "brew_root"
        ],
        formula_prefix=layout[
            "formula_prefix"
        ],
        cellar=layout[
            "cellar"
        ],
        version="1.7.1",
        upgrade_version="1.7.2",
    )

    monkeypatch.setattr(
        lu.shutil,
        "which",
        lambda name, path=None: (
            str(command)
            if name == "nexus"
            else "/brew/bin/brew"
        ),
    )

    result = lu.upgrade_nexus(
        path_env=str(
            layout[
                "path_dir"
            ]
        ),
        runner=fake,
        method="HOMEBREW",
    )

    assert result.version == "1.7.2"

    assert (
        result.launcher_repaired
        is False
    )


def test_failed_brew_upgrade_cannot_complete(
    tmp_path,
):
    layout = make_formula_topology(
        tmp_path
    )

    def runner(
        args: list[str],
    ):
        if args == [
            "brew",
            "--prefix",
            "nexus-agent",
        ]:
            return subprocess.CompletedProcess(
                args,
                0,
                str(
                    layout[
                        "formula_prefix"
                    ]
                )
                + "\n",
                "",
            )

        if args[:2] == [
            "brew",
            "upgrade",
        ]:
            return subprocess.CompletedProcess(
                args,
                1,
                "",
                "network failure",
            )

        if (
            len(args) == 2
            and args[1] == "--version"
        ):
            return subprocess.CompletedProcess(
                args,
                0,
                "Nexus 1.7.1\n",
                "",
            )

        return subprocess.CompletedProcess(
            args,
            1,
            "",
            "unexpected",
        )

    with pytest.raises(
        lu.LauncherUpgradeError,
        match=(
            "HOMEBREW_UPGRADE_FAILED"
        ),
    ):
        lu.upgrade_nexus(
            path_env=str(
                layout[
                    "path_dir"
                ]
            ),
            runner=runner,
            method="HOMEBREW",
        )


def test_unsupported_owner_never_guesses():
    with pytest.raises(
        lu.LauncherUpgradeError,
        match=(
            "UPGRADE_METHOD_UNSUPPORTED"
        ),
    ):
        lu.upgrade_nexus(
            method="UNSUPPORTED",
        )
