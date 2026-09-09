from __future__ import annotations

import os
import platform
import shutil
import subprocess
import sys
from dataclasses import dataclass


DEFAULT_COLUMNS = 185
DEFAULT_ROWS = 42

MIN_COLUMNS = 100
MIN_ROWS = 28

MAX_COLUMNS = 240
MAX_ROWS = 70


@dataclass(frozen=True)
class TerminalPreparation:
    platform: str
    terminal: str
    requested_columns: int
    requested_rows: int
    attempted: bool
    success: bool
    method: str
    detail: str


def _clamp(
    value: int,
    minimum: int,
    maximum: int,
) -> int:
    return max(
        minimum,
        min(
            maximum,
            int(value),
        ),
    )


def preferred_size() -> tuple[int, int]:
    try:
        columns = int(
            os.environ.get(
                "NEXUS_COLUMNS",
                DEFAULT_COLUMNS,
            )
        )
    except (TypeError, ValueError):
        columns = DEFAULT_COLUMNS

    try:
        rows = int(
            os.environ.get(
                "NEXUS_ROWS",
                DEFAULT_ROWS,
            )
        )
    except (TypeError, ValueError):
        rows = DEFAULT_ROWS

    return (
        _clamp(
            columns,
            MIN_COLUMNS,
            MAX_COLUMNS,
        ),
        _clamp(
            rows,
            MIN_ROWS,
            MAX_ROWS,
        ),
    )


def terminal_name() -> str:
    return (
        os.environ.get(
            "TERM_PROGRAM"
        )
        or os.environ.get(
            "WT_SESSION"
        )
        and "Windows Terminal"
        or os.environ.get(
            "TERM"
        )
        or "unknown"
    )


def ansi_resize_sequence(
    columns: int,
    rows: int,
) -> str:
    return (
        f"\x1b[8;"
        f"{int(rows)};"
        f"{int(columns)}t"
    )


def windows_mode_command(
    columns: int,
    rows: int,
) -> list[str]:
    return [
        "cmd",
        "/d",
        "/s",
        "/c",
        (
            "mode con: "
            f"cols={int(columns)} "
            f"lines={int(rows)}"
        ),
    ]


def _current_size() -> tuple[int, int]:
    size = shutil.get_terminal_size(
        fallback=(
            0,
            0,
        )
    )

    return (
        int(size.columns),
        int(size.lines),
    )


def _write_ansi_resize(
    columns: int,
    rows: int,
) -> bool:
    try:
        stream = sys.stdout

        if not hasattr(
            stream,
            "write",
        ):
            return False

        stream.write(
            ansi_resize_sequence(
                columns,
                rows,
            )
        )

        stream.flush()

        return True

    except Exception:
        return False


def _resize_macos_terminal(
    columns: int,
    rows: int,
) -> tuple[bool, str]:
    term_program = os.environ.get(
        "TERM_PROGRAM",
        "",
    )

    if term_program != "Apple_Terminal":
        ok = _write_ansi_resize(
            columns,
            rows,
        )

        return (
            ok,
            (
                "ansi"
                if ok
                else "unsupported-terminal"
            ),
        )

    script = (
        'tell application "Terminal"\n'
        'if (count of windows) > 0 then\n'
        f'set number of columns of front window to {int(columns)}\n'
        f'set number of rows of front window to {int(rows)}\n'
        'end if\n'
        'end tell'
    )

    try:
        result = subprocess.run(
            [
                "osascript",
                "-e",
                script,
            ],
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
        )

        if result.returncode == 0:
            return (
                True,
                "Apple_Terminal/osascript",
            )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        pass

    ok = _write_ansi_resize(
        columns,
        rows,
    )

    return (
        ok,
        (
            "ansi-fallback"
            if ok
            else "resize-failed"
        ),
    )


def _resize_windows(
    columns: int,
    rows: int,
) -> tuple[bool, str]:
    # Windows Terminal supports VT sequences in normal modern
    # configurations. Try this first because it can resize the
    # host instead of only changing the console buffer.
    if _write_ansi_resize(
        columns,
        rows,
    ):
        return (
            True,
            "windows-ansi",
        )

    try:
        result = subprocess.run(
            windows_mode_command(
                columns,
                rows,
            ),
            check=False,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=3,
            creationflags=(
                getattr(
                    subprocess,
                    "CREATE_NO_WINDOW",
                    0,
                )
            ),
        )

        return (
            result.returncode == 0,
            "windows-mode-con",
        )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        return (
            False,
            "windows-resize-failed",
        )


def _resize_posix(
    columns: int,
    rows: int,
) -> tuple[bool, str]:
    ok = _write_ansi_resize(
        columns,
        rows,
    )

    return (
        ok,
        (
            "ansi"
            if ok
            else "unsupported"
        ),
    )


def request_terminal_size(
    columns: int,
    rows: int,
) -> TerminalPreparation:
    columns = _clamp(
        columns,
        MIN_COLUMNS,
        MAX_COLUMNS,
    )

    rows = _clamp(
        rows,
        MIN_ROWS,
        MAX_ROWS,
    )

    system = platform.system()

    before_columns, before_rows = (
        _current_size()
    )

    # Never make a non-interactive CLI dependent on resize.
    try:
        interactive = bool(
            sys.stdin.isatty()
            and sys.stdout.isatty()
        )
    except Exception:
        interactive = False

    if not interactive:
        return TerminalPreparation(
            platform=system,
            terminal=terminal_name(),
            requested_columns=columns,
            requested_rows=rows,
            attempted=False,
            success=True,
            method="non-interactive-noop",
            detail=(
                f"current="
                f"{before_columns}x{before_rows}"
            ),
        )

    if system == "Darwin":
        success, method = (
            _resize_macos_terminal(
                columns,
                rows,
            )
        )

    elif system == "Windows":
        success, method = (
            _resize_windows(
                columns,
                rows,
            )
        )

    else:
        success, method = (
            _resize_posix(
                columns,
                rows,
            )
        )

    after_columns, after_rows = (
        _current_size()
    )

    return TerminalPreparation(
        platform=system,
        terminal=terminal_name(),
        requested_columns=columns,
        requested_rows=rows,
        attempted=True,
        success=success,
        method=method,
        detail=(
            f"before="
            f"{before_columns}x{before_rows};"
            f"after="
            f"{after_columns}x{after_rows}"
        ),
    )


def prepare_terminal() -> TerminalPreparation:
    columns, rows = preferred_size()

    return request_terminal_size(
        columns,
        rows,
    )
