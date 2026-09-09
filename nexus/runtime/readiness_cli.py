from __future__ import annotations

from nexus.config import (
    effective_config,
)
from nexus.runtime.readiness import (
    readiness_lines,
    runtime_readiness,
)


def check_runtime(
    workspace,
):
    cfg = effective_config(
        workspace
    )

    readiness = runtime_readiness(
        cfg["model"]
    )

    return (
        readiness,
        readiness_lines(
            readiness
        ),
    )


def require_runtime(
    workspace,
):
    readiness, lines = (
        check_runtime(
            workspace
        )
    )

    if not readiness.ready:
        raise RuntimeError(
            "\n".join(
                lines
            )
        )

    return readiness
