from __future__ import annotations

import platform
import subprocess
from pathlib import Path


def capture_screenshot(
    path: str,
):
    target = Path(
        path
    ).expanduser().resolve()

    target.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    system = platform.system()

    if system == "Darwin":
        command = [
            "/usr/sbin/screencapture",
            "-x",
            str(target),
        ]

    elif system == "Linux":
        candidates = [
            [
                "gnome-screenshot",
                "-f",
                str(target),
            ],
            [
                "scrot",
                str(target),
            ],
        ]

        command = None

        for candidate in candidates:
            if subprocess.run(
                [
                    "which",
                    candidate[0],
                ],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            ).returncode == 0:
                command = candidate
                break

        if command is None:
            raise RuntimeError(
                "SCREENSHOT_BACKEND_NOT_FOUND"
            )

    else:
        raise RuntimeError(
            "SCREENSHOT_PLATFORM_UNSUPPORTED="
            + system
        )

    result = subprocess.run(
        command,
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            "SCREENSHOT_FAILED="
            + result.stderr.strip()
        )

    if (
        not target.exists()
        or target.stat().st_size == 0
    ):
        raise RuntimeError(
            "SCREENSHOT_ARTIFACT_INVALID"
        )

    return str(
        target
    )
