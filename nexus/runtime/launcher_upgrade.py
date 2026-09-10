from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable
import os
import shutil
import subprocess
import sys
import time


FORMULA = "origit892-stack/nexus/nexus-agent"
FORMULA_SHORT = "nexus-agent"


class LauncherUpgradeError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class LauncherState:
    command_path: Path | None
    resolved_path: Path | None
    expected_path: Path
    command_version: str | None
    expected_version: str | None
    path_matches: bool
    version_matches: bool

    @property
    def passed(
        self,
    ) -> bool:
        return (
            self.path_matches
            and self.version_matches
        )


@dataclass(frozen=True)
class LauncherRepairResult:
    changed: bool
    launcher: Path
    expected: Path
    backup: Path | None
    state: LauncherState


@dataclass(frozen=True)
class UpgradeResult:
    method: str
    changed: bool
    version: str
    expected_launcher: Path
    active_launcher: Path
    launcher_repaired: bool
    backup: Path | None


RunCommand = Callable[
    [list[str]],
    subprocess.CompletedProcess[str],
]


def _default_run(
    args: list[str],
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _normalize_version_output(
    text: str,
) -> str:
    value = text.strip()

    if value.casefold().startswith(
        "nexus "
    ):
        value = value.split(
            None,
            1,
        )[1]

    return value.strip()


def environment_launcher(
    prefix: str | Path | None = None,
) -> Path:
    """
    Return the console script belonging to the active
    Python environment.

    IMPORTANT:
    Do not derive this from resolved sys.executable.
    On macOS a venv Python can resolve into the Homebrew
    Python framework while the console scripts remain under
    sys.prefix/bin.
    """
    root = Path(
        prefix
        if prefix is not None
        else sys.prefix
    ).expanduser()

    return (
        root
        / "bin"
        / "nexus"
    )


def resolve_path_command(
    *,
    path_env: str | None = None,
) -> Path | None:
    found = shutil.which(
        "nexus",
        path=path_env,
    )

    if not found:
        return None

    return Path(
        found
    ).expanduser()


def _run_version(
    executable: Path,
    *,
    runner: RunCommand = _default_run,
) -> str | None:
    result = runner(
        [
            str(executable),
            "--version",
        ]
    )

    if result.returncode != 0:
        return None

    value = _normalize_version_output(
        result.stdout
    )

    return value or None


def inspect_launcher(
    *,
    expected_executable: str | Path,
    expected_version: str | None = None,
    path_env: str | None = None,
    runner: RunCommand = _default_run,
) -> LauncherState:
    expected = Path(
        expected_executable
    ).expanduser()

    command = resolve_path_command(
        path_env=path_env,
    )

    resolved = None

    if command is not None:
        try:
            resolved = command.resolve(
                strict=False
            )
        except OSError:
            resolved = None

    try:
        expected_resolved = expected.resolve(
            strict=False
        )
    except OSError:
        expected_resolved = expected

    path_matches = (
        resolved is not None
        and resolved == expected_resolved
    )

    command_version = None

    if command is not None:
        command_version = _run_version(
            command,
            runner=runner,
        )

    version_matches = (
        True
        if expected_version is None
        else (
            command_version
            == expected_version
        )
    )

    return LauncherState(
        command_path=command,
        resolved_path=resolved,
        expected_path=expected_resolved,
        command_version=command_version,
        expected_version=expected_version,
        path_matches=path_matches,
        version_matches=version_matches,
    )


def _first_writable_path_directory(
    path_env: str | None,
) -> Path | None:
    value = (
        path_env
        if path_env is not None
        else os.environ.get(
            "PATH",
            "",
        )
    )

    for raw in value.split(
        os.pathsep
    ):
        if not raw:
            continue

        directory = Path(
            raw
        ).expanduser()

        if (
            directory.is_dir()
            and os.access(
                directory,
                os.W_OK,
            )
        ):
            return directory

    return None


def _backup_launcher(
    launcher: Path,
    *,
    backup_root: Path,
) -> Path:
    backup_root.mkdir(
        parents=True,
        exist_ok=True,
    )

    stamp = time.strftime(
        "%Y%m%d_%H%M%S"
    )

    backup = (
        backup_root
        / (
            "nexus_launcher_"
            + stamp
        )
    )

    serial = 0

    while (
        backup.exists()
        or backup.is_symlink()
    ):
        serial += 1
        backup = (
            backup_root
            / (
                "nexus_launcher_"
                + stamp
                + "_"
                + str(serial)
            )
        )

    if launcher.is_symlink():
        target = os.readlink(
            launcher
        )

        backup.write_text(
            "TYPE=SYMLINK\n"
            + "PATH="
            + str(launcher)
            + "\nTARGET="
            + target
            + "\n"
        )

    elif launcher.exists():
        shutil.copy2(
            launcher,
            backup,
        )

    else:
        raise LauncherUpgradeError(
            "LAUNCHER_BACKUP_SOURCE_MISSING="
            + str(launcher)
        )

    return backup


def _safe_to_replace(
    launcher: Path,
) -> tuple[bool, str | None]:
    parent = launcher.parent

    if not parent.exists():
        return (
            False,
            "LAUNCHER_PARENT_MISSING",
        )

    if not os.access(
        parent,
        os.W_OK,
    ):
        return (
            False,
            "LAUNCHER_PARENT_NOT_WRITABLE",
        )

    if launcher.is_symlink():
        return (
            True,
            None,
        )

    if launcher.exists():
        try:
            owner = launcher.stat().st_uid
        except OSError:
            return (
                False,
                "LAUNCHER_STAT_FAILED",
            )

        if owner != os.getuid():
            return (
                False,
                "LAUNCHER_NOT_USER_OWNED",
            )

        if not os.access(
            launcher,
            os.W_OK,
        ):
            return (
                False,
                "LAUNCHER_FILE_NOT_WRITABLE",
            )

    return (
        True,
        None,
    )


def repair_launcher(
    *,
    expected_executable: str | Path,
    expected_version: str,
    path_env: str | None = None,
    backup_root: str | Path | None = None,
    runner: RunCommand = _default_run,
) -> LauncherRepairResult:
    expected = Path(
        expected_executable
    ).expanduser()

    if not expected.exists():
        raise LauncherUpgradeError(
            "EXPECTED_LAUNCHER_MISSING="
            + str(expected)
        )

    if not os.access(
        expected,
        os.X_OK,
    ):
        raise LauncherUpgradeError(
            "EXPECTED_LAUNCHER_NOT_EXECUTABLE="
            + str(expected)
        )

    initial = inspect_launcher(
        expected_executable=expected,
        expected_version=expected_version,
        path_env=path_env,
        runner=runner,
    )

    if initial.passed:
        assert initial.command_path is not None

        return LauncherRepairResult(
            changed=False,
            launcher=initial.command_path,
            expected=initial.expected_path,
            backup=None,
            state=initial,
        )

    launcher = initial.command_path

    if launcher is None:
        directory = (
            _first_writable_path_directory(
                path_env
            )
        )

        if directory is None:
            raise LauncherUpgradeError(
                "NO_WRITABLE_PATH_DIRECTORY"
            )

        launcher = (
            directory
            / "nexus"
        )

    safe, reason = _safe_to_replace(
        launcher
    )

    if not safe:
        raise LauncherUpgradeError(
            str(reason)
            + "="
            + str(launcher)
        )

    backup_path = None

    if (
        launcher.exists()
        or launcher.is_symlink()
    ):
        root = Path(
            backup_root
            if backup_root is not None
            else (
                Path.home()
                / ".nexus"
                / "backups"
                / "launcher"
            )
        )

        backup_path = _backup_launcher(
            launcher,
            backup_root=root,
        )

    temp_link = (
        launcher.parent
        / (
            ".nexus."
            + str(os.getpid())
            + ".tmp"
        )
    )

    try:
        if (
            temp_link.exists()
            or temp_link.is_symlink()
        ):
            temp_link.unlink()

        temp_link.symlink_to(
            expected
        )

        os.replace(
            temp_link,
            launcher,
        )

    finally:
        if (
            temp_link.exists()
            or temp_link.is_symlink()
        ):
            temp_link.unlink()

    final = inspect_launcher(
        expected_executable=expected,
        expected_version=expected_version,
        path_env=path_env,
        runner=runner,
    )

    if not final.passed:
        raise LauncherUpgradeError(
            "LAUNCHER_REPAIR_VERIFICATION_FAILED"
            + ": command="
            + str(final.command_path)
            + " resolved="
            + str(final.resolved_path)
            + " expected="
            + str(final.expected_path)
            + " version="
            + str(final.command_version)
            + " expected_version="
            + str(final.expected_version)
        )

    return LauncherRepairResult(
        changed=True,
        launcher=launcher,
        expected=final.expected_path,
        backup=backup_path,
        state=final,
    )



def _brew_formula_prefix(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    result = runner(
        [
            "brew",
            "--prefix",
            FORMULA_SHORT,
        ]
    )

    if result.returncode != 0:
        raise LauncherUpgradeError(
            "HOMEBREW_NEXUS_NOT_INSTALLED="
            + result.stderr.strip()
        )

    value = result.stdout.strip()

    if not value:
        raise LauncherUpgradeError(
            "HOMEBREW_FORMULA_PREFIX_EMPTY"
        )

    return Path(
        value
    ).expanduser()


def _brew_root_prefix(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    result = runner(
        [
            "brew",
            "--prefix",
        ]
    )

    if result.returncode != 0:
        raise LauncherUpgradeError(
            "HOMEBREW_PREFIX_FAILED="
            + result.stderr.strip()
        )

    value = result.stdout.strip()

    if not value:
        raise LauncherUpgradeError(
            "HOMEBREW_PREFIX_EMPTY"
        )

    return Path(
        value
    ).expanduser()


def _brew_cellar(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    result = runner(
        [
            "brew",
            "--cellar",
            FORMULA_SHORT,
        ]
    )

    if result.returncode != 0:
        raise LauncherUpgradeError(
            "HOMEBREW_CELLAR_FAILED="
            + result.stderr.strip()
        )

    value = result.stdout.strip()

    if not value:
        raise LauncherUpgradeError(
            "HOMEBREW_CELLAR_EMPTY"
        )

    return Path(
        value
    ).expanduser()


def homebrew_runtime_root(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    return (
        _brew_root_prefix(
            runner=runner,
        )
        / "var"
        / "nexus-agent"
    )


def homebrew_runtime_launcher(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    return (
        homebrew_runtime_root(
            runner=runner,
        )
        / "venv"
        / "bin"
        / "nexus"
    )


def homebrew_formula_launcher(
    *,
    runner: RunCommand = _default_run,
) -> Path:
    return (
        _brew_formula_prefix(
            runner=runner,
        )
        / "bin"
        / "nexus"
    )


def _brew_available() -> bool:
    return (
        shutil.which(
            "brew"
        )
        is not None
    )


def homebrew_install_present(
    *,
    runner: RunCommand = _default_run,
) -> bool:
    if not _brew_available():
        return False

    result = runner(
        [
            "brew",
            "list",
            "--versions",
            FORMULA_SHORT,
        ]
    )

    if result.returncode != 0:
        return False

    return bool(
        result.stdout.strip()
    )


def path_is_within(
    path: Path,
    parent: Path,
) -> bool:
    try:
        resolved_path = path.resolve(
            strict=False
        )

        resolved_parent = parent.resolve(
            strict=False
        )

    except OSError:
        return False

    return (
        resolved_path == resolved_parent
        or resolved_parent
        in resolved_path.parents
    )


def detect_upgrade_method(
    *,
    runner: RunCommand = _default_run,
) -> str:
    """
    Detect the installation owner without assuming that
    the imported Nexus package lives inside the Formula
    prefix.

    The Homebrew Formula intentionally bootstraps its
    Python runtime under:

        $(brew --prefix)/var/nexus-agent/venv

    while the Formula launcher lives under:

        $(brew --prefix nexus-agent)/bin/nexus

    Either topology is a valid Homebrew-owned Nexus
    installation.
    """
    if not homebrew_install_present(
        runner=runner,
    ):
        return "UNSUPPORTED"

    try:
        formula_prefix = (
            _brew_formula_prefix(
                runner=runner,
            )
        )

        cellar = _brew_cellar(
            runner=runner,
        )

        runtime_root = (
            homebrew_runtime_root(
                runner=runner,
            )
        )

        formula_launcher = (
            homebrew_formula_launcher(
                runner=runner,
            )
        )

        runtime_launcher = (
            homebrew_runtime_launcher(
                runner=runner,
            )
        )

    except LauncherUpgradeError:
        return "UNSUPPORTED"

    package_file = Path(
        __file__
    )

    active_command = (
        resolve_path_command()
    )

    package_owned = (
        path_is_within(
            package_file,
            formula_prefix,
        )
        or path_is_within(
            package_file,
            cellar,
        )
        or path_is_within(
            package_file,
            runtime_root,
        )
    )

    command_owned = False

    if active_command is not None:
        try:
            active_resolved = (
                active_command.resolve(
                    strict=False
                )
            )
        except OSError:
            active_resolved = (
                active_command
            )

        candidates = (
            formula_launcher,
            runtime_launcher,
        )

        for candidate in candidates:
            try:
                resolved_candidate = (
                    candidate.resolve(
                        strict=False
                    )
                )
            except OSError:
                resolved_candidate = (
                    candidate
                )

            if (
                active_resolved
                == resolved_candidate
            ):
                command_owned = True
                break

    if (
        package_owned
        or command_owned
    ):
        return "HOMEBREW"

    # Homebrew is installed, but this particular Nexus
    # process is not demonstrably Homebrew-owned.
    # Do not mutate a separate installation implicitly.
    return "UNSUPPORTED"



def upgrade_nexus(
    *,
    path_env: str | None = None,
    runner: RunCommand = _default_run,
    method: str | None = None,
) -> UpgradeResult:
    selected = (
        method
        if method is not None
        else detect_upgrade_method(
            runner=runner,
        )
    )

    if selected != "HOMEBREW":
        raise LauncherUpgradeError(
            "UPGRADE_METHOD_UNSUPPORTED="
            + str(selected)
            + ". Nexus could not prove that the "
            + "current installation is owned by Homebrew."
        )

    before_launcher = (
        homebrew_formula_launcher(
            runner=runner,
        )
    )

    before_version = _run_version(
        before_launcher,
        runner=runner,
    )

    upgrade = runner(
        [
            "brew",
            "upgrade",
            FORMULA,
        ]
    )

    if upgrade.returncode != 0:
        combined = (
            upgrade.stdout
            + "\n"
            + upgrade.stderr
        ).casefold()

        already_current = (
            "already installed"
            in combined
            or "already up-to-date"
            in combined
            or "already up to date"
            in combined
        )

        if not already_current:
            raise LauncherUpgradeError(
                "HOMEBREW_UPGRADE_FAILED="
                + upgrade.stderr.strip()
            )

    after_launcher = (
        homebrew_formula_launcher(
            runner=runner,
        )
    )

    if not after_launcher.exists():
        raise LauncherUpgradeError(
            "UPGRADED_FORMULA_LAUNCHER_MISSING="
            + str(after_launcher)
        )

    after_version = _run_version(
        after_launcher,
        runner=runner,
    )

    if after_version is None:
        raise LauncherUpgradeError(
            "UPGRADED_VERSION_CHECK_FAILED="
            + str(after_launcher)
        )

    # The Formula launcher is the canonical Homebrew
    # entrypoint. It is intentionally allowed to bootstrap
    # and exec the runtime venv under Homebrew var.
    repair = repair_launcher(
        expected_executable=after_launcher,
        expected_version=after_version,
        path_env=path_env,
        runner=runner,
    )

    # Verify the exact PATH-resolved command after repair.
    final_state = inspect_launcher(
        expected_executable=after_launcher,
        expected_version=after_version,
        path_env=path_env,
        runner=runner,
    )

    if not final_state.passed:
        raise LauncherUpgradeError(
            "UPGRADE_COMPLETION_GATE_FAILED"
        )

    return UpgradeResult(
        method="HOMEBREW",
        changed=(
            before_version
            != after_version
        ),
        version=after_version,
        expected_launcher=after_launcher,
        active_launcher=repair.launcher,
        launcher_repaired=repair.changed,
        backup=repair.backup,
    )
