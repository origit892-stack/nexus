from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


DEFAULT_CONTEXT_FILES = (
    "AGENTS.md",
    "docs/director/CURRENT-TASK.md",
    "docs/director/GAME-VISION.md",
    "docs/director/WORLD-BIBLE.md",
    "default.project.json",
)


@dataclass(frozen=True)
class CachedContext:
    path: str
    digest: str
    content: str


class ProjectContextCache:
    def __init__(
        self,
        root: Path,
    ) -> None:
        self.root = root.resolve()

        self._cache: dict[
            Path,
            CachedContext,
        ] = {}

    def _digest(
        self,
        content: str,
    ) -> str:
        return hashlib.sha256(
            content.encode("utf-8")
        ).hexdigest()

    def read(
        self,
        relative_path: str,
    ) -> CachedContext | None:
        path = (
            self.root
            / relative_path
        ).resolve()

        if not path.is_file():
            return None

        content = path.read_text(
            errors="replace"
        )

        digest = self._digest(
            content
        )

        cached = self._cache.get(
            path
        )

        if (
            cached is not None
            and cached.digest == digest
        ):
            return cached

        value = CachedContext(
            path=str(path),
            digest=digest,
            content=content,
        )

        self._cache[path] = value

        return value

    def warm_default_context(
        self,
    ) -> list[CachedContext]:
        result = []

        for relative_path in (
            DEFAULT_CONTEXT_FILES
        ):
            value = self.read(
                relative_path
            )

            if value is not None:
                result.append(
                    value
                )

        return result
