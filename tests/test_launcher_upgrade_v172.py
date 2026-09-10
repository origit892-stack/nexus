from __future__ import annotations

from pathlib import Path
import os
import subprocess

import pytest

from nexus.runtime.launcher_upgrade import (
    LauncherUpgradeError,
    environment_launcher,
    inspect_launcher,
    repair_launcher,
)


def fake_runner_for_versions(
    versions: dict[str, str],
):
    def run(
        args: list[str],
    ):
        executable = str(
            Path(
                args[0]
            )
        )

        version = versions.get(
            executable
        )

        if version is None:
            try:
                resolved = str(
                    Path(
                        executable
                    ).resolve()
                )
            except OSError:
                resolved = executable

            version = versions.get(
                resolved
            )

        if version is None:
            return subprocess.CompletedProcess(
                args,
                1,
                "",
                "missing",
            )

        return subprocess.CompletedProcess(
            args,
            0,
            "Nexus "
            + version
            + "\n",
            "",
        )

    return run


def test_environment_launcher_uses_prefix_not_resolved_python(
    tmp_path,
):
    prefix = (
        tmp_path
        / "custom-env"
    )

    expected = (
        prefix
        / "bin"
        / "nexus"
    )

    assert (
        environment_launcher(
            prefix
        )
        == expected
    )


def test_matching_launcher_is_noop(
    tmp_path,
):
    env = tmp_path / "env"
    bin_dir = env / "bin"
    bin_dir.mkdir(
        parents=True
    )

    expected = (
        bin_dir
        / "nexus"
    )

    expected.write_text(
        "#!/bin/sh\n"
    )

    expected.chmod(
        0o755
    )

    path_dir = (
        tmp_path
        / "path"
    )

    path_dir.mkdir()

    command = (
        path_dir
        / "nexus"
    )

    command.symlink_to(
        expected
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.2",
            str(expected): "1.7.2",
        }
    )

    result = repair_launcher(
        expected_executable=expected,
        expected_version="1.7.2",
        path_env=str(
            path_dir
        ),
        runner=runner,
    )

    assert result.changed is False
    assert result.backup is None
    assert (
        command.resolve()
        == expected.resolve()
    )


def test_stale_symlink_is_backed_up_and_repaired(
    tmp_path,
):
    path_dir = (
        tmp_path
        / "bin"
    )

    path_dir.mkdir()

    old = (
        tmp_path
        / "old"
        / "nexus"
    )

    old.parent.mkdir()

    old.write_text(
        "#!/bin/sh\n"
    )

    old.chmod(
        0o755
    )

    new = (
        tmp_path
        / "new"
        / "nexus"
    )

    new.parent.mkdir()

    new.write_text(
        "#!/bin/sh\n"
    )

    new.chmod(
        0o755
    )

    command = (
        path_dir
        / "nexus"
    )

    command.symlink_to(
        old
    )

    backup_root = (
        tmp_path
        / "backups"
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.2",
            str(new): "1.7.2",
        }
    )

    result = repair_launcher(
        expected_executable=new,
        expected_version="1.7.2",
        path_env=str(
            path_dir
        ),
        backup_root=backup_root,
        runner=runner,
    )

    assert result.changed is True

    assert (
        command.resolve()
        == new.resolve()
    )

    assert result.backup is not None
    assert result.backup.is_file()

    backup_text = (
        result.backup.read_text()
    )

    assert "TYPE=SYMLINK" in backup_text
    assert str(old) in backup_text


def test_missing_path_launcher_is_created(
    tmp_path,
):
    path_dir = (
        tmp_path
        / "bin"
    )

    path_dir.mkdir()

    expected = (
        tmp_path
        / "runtime"
        / "nexus"
    )

    expected.parent.mkdir()

    expected.write_text(
        "#!/bin/sh\n"
    )

    expected.chmod(
        0o755
    )

    command = (
        path_dir
        / "nexus"
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.2",
            str(expected): "1.7.2",
        }
    )

    result = repair_launcher(
        expected_executable=expected,
        expected_version="1.7.2",
        path_env=str(
            path_dir
        ),
        runner=runner,
    )

    assert result.changed is True
    assert command.is_symlink()

    assert (
        command.resolve()
        == expected.resolve()
    )


def test_regular_user_owned_launcher_is_backed_up(
    tmp_path,
):
    path_dir = (
        tmp_path
        / "bin"
    )

    path_dir.mkdir()

    command = (
        path_dir
        / "nexus"
    )

    command.write_text(
        "#!/bin/sh\n"
        "echo old\n"
    )

    command.chmod(
        0o755
    )

    expected = (
        tmp_path
        / "new"
        / "nexus"
    )

    expected.parent.mkdir()

    expected.write_text(
        "#!/bin/sh\n"
    )

    expected.chmod(
        0o755
    )

    backup_root = (
        tmp_path
        / "backup"
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.2",
            str(expected): "1.7.2",
        }
    )

    result = repair_launcher(
        expected_executable=expected,
        expected_version="1.7.2",
        path_env=str(
            path_dir
        ),
        backup_root=backup_root,
        runner=runner,
    )

    assert result.changed is True
    assert result.backup is not None

    assert (
        "echo old"
        in result.backup.read_text()
    )

    assert command.is_symlink()

    assert (
        command.resolve()
        == expected.resolve()
    )


def test_expected_launcher_must_exist(
    tmp_path,
):
    with pytest.raises(
        LauncherUpgradeError,
        match="EXPECTED_LAUNCHER_MISSING",
    ):
        repair_launcher(
            expected_executable=(
                tmp_path
                / "missing"
            ),
            expected_version="1.7.2",
            path_env=str(
                tmp_path
            ),
        )


def test_inspection_detects_version_mismatch(
    tmp_path,
):
    path_dir = (
        tmp_path
        / "bin"
    )

    path_dir.mkdir()

    expected = (
        tmp_path
        / "expected"
        / "nexus"
    )

    expected.parent.mkdir()

    expected.write_text(
        "#!/bin/sh\n"
    )

    expected.chmod(
        0o755
    )

    command = (
        path_dir
        / "nexus"
    )

    command.symlink_to(
        expected
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.1",
            str(expected): "1.7.1",
        }
    )

    state = inspect_launcher(
        expected_executable=expected,
        expected_version="1.7.2",
        path_env=str(
            path_dir
        ),
        runner=runner,
    )

    assert state.path_matches is True
    assert state.version_matches is False
    assert state.passed is False


def test_repair_verifies_result_version(
    tmp_path,
):
    path_dir = (
        tmp_path
        / "bin"
    )

    path_dir.mkdir()

    old = (
        tmp_path
        / "old"
        / "nexus"
    )

    old.parent.mkdir()
    old.write_text(
        "#!/bin/sh\n"
    )
    old.chmod(
        0o755
    )

    expected = (
        tmp_path
        / "new"
        / "nexus"
    )

    expected.parent.mkdir()
    expected.write_text(
        "#!/bin/sh\n"
    )
    expected.chmod(
        0o755
    )

    command = (
        path_dir
        / "nexus"
    )

    command.symlink_to(
        old
    )

    runner = fake_runner_for_versions(
        {
            str(command): "1.7.1",
            str(expected): "1.7.1",
        }
    )

    with pytest.raises(
        LauncherUpgradeError,
        match=(
            "LAUNCHER_REPAIR_VERIFICATION_FAILED"
        ),
    ):
        repair_launcher(
            expected_executable=expected,
            expected_version="1.7.2",
            path_env=str(
                path_dir
            ),
            runner=runner,
        )
