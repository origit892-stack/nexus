from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
import re
import subprocess
import time
from typing import Any


MAX_READ_BYTES = 256 * 1024
MAX_GREP_FILES = 4000
MAX_GREP_MATCHES = 80
MAX_LIST_ENTRIES = 200
MAX_FILENAME_MATCHES = 100


@dataclass(frozen=True)
class FastLookupEvidence:
    kind: str
    query: str
    path: str
    found: bool
    value: str | None
    elapsed_ms: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind":
                self.kind,

            "query":
                self.query,

            "path":
                self.path,

            "found":
                self.found,

            "value":
                self.value,

            "elapsed_ms":
                self.elapsed_ms,

            "verified":
                True,
        }


@dataclass(frozen=True)
class FastLookupResult:
    handled: bool
    answer: str
    evidence: tuple[
        FastLookupEvidence,
        ...
    ]
    filesystem_operations: int
    elapsed_ms: float
    route: str = "FAST_LOOKUP"
    capability: str = "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "handled":
                self.handled,

            "answer":
                self.answer,

            "evidence": [
                item.to_dict()
                for item
                in self.evidence
            ],

            "filesystem_operations":
                self.filesystem_operations,

            "elapsed_ms":
                self.elapsed_ms,

            "route":
                self.route,

            "capability":
                self.capability,

            "director_model_calls":
                0,

            "understanding_model_calls":
                0,

            "planner_model_calls":
                0,

            "completion_model_calls":
                0,
        }


_FILE_EXTENSIONS = (
    "toml",
    "md",
    "json",
    "yaml",
    "yml",
    "py",
    "lua",
    "luau",
    "txt",
    "cfg",
    "ini",
    "sh",
    "zsh",
    "js",
    "ts",
    "tsx",
    "jsx",
    "css",
    "html",
    "xml",
    "csv",
)


_FILENAME_RE = re.compile(
    r"""
    (?<![\w.-])
    (
        [A-Za-z0-9_.-]+
        \.
        (?:
    """
    + "|".join(
        _FILE_EXTENSIONS
    )
    + r"""
        )
    )
    (?![\w.-])
    """,
    re.VERBOSE
)


_PATH_RE = re.compile(
    r"""
    (?<![\w.-])
    (
        (?:
            [A-Za-z0-9_.-]+/
        )+
        [A-Za-z0-9_.-]+
        (?:
            \.
            [A-Za-z0-9_.-]+
        )?
    )
    (?![\w.-])
    """,
    re.VERBOSE
)


_QUOTED_RE = re.compile(
    r"""
    (?:
        "([^"\n]{1,300})"
        |
        '([^'\n]{1,300})'
        |
        `([^`\n]{1,300})`
    )
    """,
    re.VERBOSE
)


_UNSAFE_WRITE_WORDS = (
    "write",
    "modify",
    "change",
    "edit",
    "delete",
    "remove",
    "rename",
    "move",
    "copy",
    "create",
    "make",
    "install",
    "update",
    "upgrade",
    "commit",
    "push",
    "checkout",
    "switch",
    "reset",
    "revert",
    "merge",
    "rebase",
    "chmod",
    "chown",
    "kill",
    "start",
    "stop",
    "restart",
    "run command",
    "execute command",
)


_READ_ONLY_HINTS = (
    "read-only",
    "read only",
    "do not modify",
    "don't modify",
    "do not change",
    "inspect",
    "show",
    "find",
    "search",
    "read",
    "report",
    "list",
    "check",
    "determine",
    "what is",
    "what's",
    "which",
    "where",
    "does",
    "exists",
    "exist",
)


_IGNORE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".nexus",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".venv",
    "venv",
    "node_modules",
    "dist",
    "build",
}


def _elapsed_ms(
    started: float,
) -> float:
    return round(
        (
            time.perf_counter()
            - started
        )
        * 1000.0,
        3,
    )


def _safe_workspace(
    workspace: str | Path,
) -> Path:
    root = Path(
        workspace
    ).expanduser().resolve()

    if not root.exists():
        raise FileNotFoundError(
            str(root)
        )

    if not root.is_dir():
        raise NotADirectoryError(
            str(root)
        )

    return root


def _inside(
    root: Path,
    candidate: Path,
) -> bool:
    try:
        candidate.relative_to(
            root
        )
        return True

    except ValueError:
        return False


def _safe_candidate(
    root: Path,
    relative: str,
) -> Path | None:
    raw = relative.strip()

    if not raw:
        return None

    candidate = (
        root
        / raw
    ).expanduser().resolve()

    if not _inside(
        root,
        candidate,
    ):
        return None

    return candidate


def _looks_read_only(
    task: str,
) -> bool:
    lower = task.lower()

    if not any(
        hint in lower
        for hint in _READ_ONLY_HINTS
    ):
        return False

    for word in _UNSAFE_WRITE_WORDS:
        if word not in lower:
            continue

        safe_phrases = (
            "do not " + word,
            "don't " + word,
            "without " + word,
            "no " + word,
        )

        if any(
            phrase in lower
            for phrase in safe_phrases
        ):
            continue

        return False

    return True


def _extract_paths(
    task: str,
) -> list[str]:
    values = []

    for match in _PATH_RE.findall(
        task
    ):
        value = match.strip()

        if value not in values:
            values.append(
                value
            )

    return values


def _extract_filenames(
    task: str,
    paths: list[str],
) -> list[str]:
    values = []

    for match in _FILENAME_RE.findall(
        task
    ):
        value = match.strip()

        if any(
            path == value
            or path.endswith(
                "/" + value
            )
            for path in paths
        ):
            continue

        if value not in values:
            values.append(
                value
            )

    return values


def _quoted_values(
    task: str,
) -> list[str]:
    values = []

    for groups in _QUOTED_RE.findall(
        task
    ):
        value = next(
            (
                item
                for item in groups
                if item
            ),
            "",
        ).strip()

        if (
            value
            and value not in values
        ):
            values.append(
                value
            )

    return values


def _first_heading(
    path: Path,
) -> str | None:
    with path.open(
        "r",
        encoding="utf-8",
        errors="replace",
    ) as handle:
        for line in handle:
            stripped = line.strip()

            if stripped.startswith(
                "#"
            ):
                return stripped

    return None


def _is_probably_binary(
    path: Path,
) -> bool:
    try:
        with path.open(
            "rb"
        ) as handle:
            chunk = handle.read(
                4096
            )

    except OSError:
        return True

    return b"\x00" in chunk


def _read_text_bounded(
    path: Path,
) -> tuple[str, bool]:
    size = path.stat().st_size

    if size > MAX_READ_BYTES:
        with path.open(
            "rb"
        ) as handle:
            raw = handle.read(
                MAX_READ_BYTES
            )

        return (
            raw.decode(
                "utf-8",
                errors="replace",
            ),
            True,
        )

    return (
        path.read_text(
            encoding="utf-8",
            errors="replace",
        ),
        False,
    )


def _iter_workspace_files(
    root: Path,
):
    seen = 0

    for current_root, dirs, files in os.walk(
        root
    ):
        dirs[:] = [
            item
            for item in dirs
            if item not in _IGNORE_DIRS
        ]

        base = Path(
            current_root
        )

        for filename in files:
            seen += 1

            if seen > MAX_GREP_FILES:
                return

            candidate = (
                base
                / filename
            )

            try:
                resolved = candidate.resolve()

            except OSError:
                continue

            if not _inside(
                root,
                resolved,
            ):
                continue

            yield resolved


def _search_exact_name(
    root: Path,
    filename: str,
) -> list[Path]:
    matches = []

    for path in _iter_workspace_files(
        root
    ):
        if path.name != filename:
            continue

        matches.append(
            path
        )

        if (
            len(matches)
            >= MAX_FILENAME_MATCHES
        ):
            break

    matches.sort(
        key=lambda item:
            str(item)
    )

    return matches


def _wants_heading(
    task: str,
) -> bool:
    lower = task.lower()

    return (
        "heading" in lower
        or "markdown heading" in lower
        or "title" in lower
    )


def _wants_file_contents(
    task: str,
) -> bool:
    lower = task.lower()

    phrases = (
        "read ",
        "contents",
        "content of",
        "show ",
        "print ",
        "cat ",
    )

    return any(
        phrase in lower
        for phrase in phrases
    )


def _wants_existence(
    task: str,
) -> bool:
    lower = task.lower()

    phrases = (
        "exist",
        "exists",
        "whether",
        "is there",
        "find ",
        "locate ",
        "where is",
        "where are",
    )

    return any(
        phrase in lower
        for phrase in phrases
    )


def _wants_listing(
    task: str,
) -> bool:
    lower = task.lower()

    phrases = (
        "list files",
        "list directory",
        "list folder",
        "show files",
        "show directory",
        "show folder",
        "what files",
        "which files",
    )

    return any(
        phrase in lower
        for phrase in phrases
    )


def _grep_query(
    task: str,
) -> str | None:
    lower = task.lower()

    if not any(
        word in lower
        for word in (
            "grep",
            "search for",
            "find text",
            "find string",
            "contains",
            "containing",
        )
    ):
        return None

    quoted = _quoted_values(
        task
    )

    if not quoted:
        return None

    return quoted[0]


def _git_capability(
    task: str,
) -> str | None:
    lower = task.lower()

    if "git" not in lower:
        return None

    if any(
        phrase in lower
        for phrase in (
            "git status",
            "working tree",
            "working directory status",
            "uncommitted",
            "modified files",
        )
    ):
        return "git_status"

    if any(
        phrase in lower
        for phrase in (
            "current branch",
            "git branch",
            "which branch",
        )
    ):
        return "git_branch"

    if any(
        phrase in lower
        for phrase in (
            "git head",
            "head commit",
            "current commit",
            "commit hash",
            "commit sha",
        )
    ):
        return "git_head"

    return None


def _run_git(
    root: Path,
    args: list[str],
) -> tuple[int, str, str]:
    process = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            *args,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=3.0,
        check=False,
    )

    return (
        process.returncode,
        process.stdout.strip(),
        process.stderr.strip(),
    )


def _git_result(
    *,
    task: str,
    root: Path,
    capability: str,
    started: float,
) -> FastLookupResult:
    operation_started = (
        time.perf_counter()
    )

    if capability == "git_status":
        rc, stdout, stderr = _run_git(
            root,
            [
                "status",
                "--short",
                "--branch",
            ],
        )

    elif capability == "git_branch":
        rc, stdout, stderr = _run_git(
            root,
            [
                "branch",
                "--show-current",
            ],
        )

    elif capability == "git_head":
        rc, stdout, stderr = _run_git(
            root,
            [
                "rev-parse",
                "HEAD",
            ],
        )

    else:
        return FastLookupResult(
            handled=False,
            answer="",
            evidence=(),
            filesystem_operations=0,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )

    if rc != 0:
        return FastLookupResult(
            handled=False,
            answer="",
            evidence=(),
            filesystem_operations=1,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )

    value = stdout

    if capability == "git_status":
        answer = (
            stdout
            if stdout
            else "Git working tree is clean."
        )

    elif capability == "git_branch":
        answer = (
            "Current Git branch: "
            + (
                stdout
                if stdout
                else "(detached HEAD)"
            )
        )

    else:
        answer = (
            "Current Git HEAD: "
            + stdout
        )

    evidence = (
        FastLookupEvidence(
            kind=capability,
            query=task,
            path=str(root),
            found=True,
            value=value,
            elapsed_ms=_elapsed_ms(
                operation_started
            ),
        ),
    )

    return FastLookupResult(
        handled=True,
        answer=answer,
        evidence=evidence,
        filesystem_operations=1,
        elapsed_ms=_elapsed_ms(
            started
        ),
        capability=capability,
    )


def _directory_listing(
    *,
    task: str,
    root: Path,
    paths: list[str],
    started: float,
) -> FastLookupResult:
    target = root

    if paths:
        candidate = _safe_candidate(
            root,
            paths[0],
        )

        if candidate is None:
            return FastLookupResult(
                handled=False,
                answer="",
                evidence=(),
                filesystem_operations=0,
                elapsed_ms=_elapsed_ms(
                    started
                ),
                capability="fallback",
            )

        target = candidate

    operation_started = (
        time.perf_counter()
    )

    if not target.exists():
        evidence = (
            FastLookupEvidence(
                kind="directory_listing",
                query=task,
                path=str(target),
                found=False,
                value=None,
                elapsed_ms=_elapsed_ms(
                    operation_started
                ),
            ),
        )

        return FastLookupResult(
            handled=True,
            answer=(
                str(
                    target.relative_to(
                        root
                    )
                )
                + ": directory not found."
            ),
            evidence=evidence,
            filesystem_operations=1,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="directory_listing",
        )

    if not target.is_dir():
        return FastLookupResult(
            handled=False,
            answer="",
            evidence=(),
            filesystem_operations=1,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )

    entries = sorted(
        target.iterdir(),
        key=lambda item:
            (
                not item.is_dir(),
                item.name.lower(),
            ),
    )

    truncated = (
        len(entries)
        > MAX_LIST_ENTRIES
    )

    entries = entries[
        :MAX_LIST_ENTRIES
    ]

    relative_entries = []

    for item in entries:
        suffix = (
            "/"
            if item.is_dir()
            else ""
        )

        relative_entries.append(
            item.name
            + suffix
        )

    value = "\n".join(
        relative_entries
    )

    if truncated:
        value += (
            "\n... listing truncated ..."
        )

    display = (
        "."
        if target == root
        else str(
            target.relative_to(
                root
            )
        )
    )

    answer = (
        f"Directory {display}:\n"
        + value
    )

    evidence = (
        FastLookupEvidence(
            kind="directory_listing",
            query=task,
            path=str(target),
            found=True,
            value=value,
            elapsed_ms=_elapsed_ms(
                operation_started
            ),
        ),
    )

    return FastLookupResult(
        handled=True,
        answer=answer,
        evidence=evidence,
        filesystem_operations=1,
        elapsed_ms=_elapsed_ms(
            started
        ),
        capability="directory_listing",
    )


def _literal_grep(
    *,
    task: str,
    root: Path,
    query: str,
    paths: list[str],
    started: float,
) -> FastLookupResult:
    search_root = root

    if paths:
        candidate = _safe_candidate(
            root,
            paths[0],
        )

        if candidate is None:
            return FastLookupResult(
                handled=False,
                answer="",
                evidence=(),
                filesystem_operations=0,
                elapsed_ms=_elapsed_ms(
                    started
                ),
                capability="fallback",
            )

        if candidate.is_file():
            candidates = [
                candidate
            ]

        elif candidate.is_dir():
            search_root = candidate
            candidates = list(
                _iter_workspace_files(
                    search_root
                )
            )

        else:
            candidates = []

    else:
        candidates = list(
            _iter_workspace_files(
                root
            )
        )

    operation_started = (
        time.perf_counter()
    )

    matches = []

    scanned = 0

    for path in candidates:
        scanned += 1

        if (
            len(matches)
            >= MAX_GREP_MATCHES
        ):
            break

        try:
            if _is_probably_binary(
                path
            ):
                continue

            if (
                path.stat().st_size
                > MAX_READ_BYTES
            ):
                continue

            with path.open(
                "r",
                encoding="utf-8",
                errors="replace",
            ) as handle:
                for line_number, line in enumerate(
                    handle,
                    1,
                ):
                    if query not in line:
                        continue

                    relative = (
                        path.relative_to(
                            root
                        )
                    )

                    matches.append(
                        (
                            str(relative),
                            line_number,
                            line.rstrip()[
                                :300
                            ],
                        )
                    )

                    if (
                        len(matches)
                        >= MAX_GREP_MATCHES
                    ):
                        break

        except OSError:
            continue

    if matches:
        lines = [
            (
                f"{path}:{line}: "
                f"{text}"
            )
            for path, line, text
            in matches
        ]

        answer = (
            f'Found "{query}" in '
            f"{len(matches)} location(s):\n"
            + "\n".join(
                lines
            )
        )

        value = "\n".join(
            lines
        )

        found = True

    else:
        answer = (
            f'No literal matches for "{query}" '
            "were found in the bounded "
            "workspace search."
        )

        value = None
        found = False

    evidence = (
        FastLookupEvidence(
            kind="literal_grep",
            query=query,
            path=str(search_root),
            found=found,
            value=value,
            elapsed_ms=_elapsed_ms(
                operation_started
            ),
        ),
    )

    return FastLookupResult(
        handled=True,
        answer=answer,
        evidence=evidence,
        filesystem_operations=max(
            1,
            scanned,
        ),
        elapsed_ms=_elapsed_ms(
            started
        ),
        capability="literal_grep",
    )


def _path_queries(
    *,
    task: str,
    root: Path,
    paths: list[str],
    filenames: list[str],
    started: float,
) -> FastLookupResult:
    evidence = []
    answers = []
    operations = 0
    handled = False

    wants_heading = _wants_heading(
        task
    )

    wants_contents = (
        _wants_file_contents(
            task
        )
    )

    wants_existence = (
        _wants_existence(
            task
        )
    )

    for relative in paths:
        candidate = _safe_candidate(
            root,
            relative,
        )

        if candidate is None:
            return FastLookupResult(
                handled=False,
                answer="",
                evidence=tuple(
                    evidence
                ),
                filesystem_operations=operations,
                elapsed_ms=_elapsed_ms(
                    started
                ),
                capability="fallback",
            )

        operation_started = (
            time.perf_counter()
        )

        exists = candidate.exists()

        operations += 1
        handled = True

        if not exists:
            evidence.append(
                FastLookupEvidence(
                    kind="path_existence",
                    query=relative,
                    path=str(candidate),
                    found=False,
                    value=None,
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                f"{relative}: not found."
            )

            continue

        if candidate.is_dir():
            evidence.append(
                FastLookupEvidence(
                    kind="path_existence",
                    query=relative,
                    path=str(candidate),
                    found=True,
                    value="directory",
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                f"{relative}: directory exists."
            )

            continue

        if wants_heading:
            heading = (
                _first_heading(
                    candidate
                )
                if candidate.suffix.lower()
                == ".md"
                else None
            )

            evidence.append(
                FastLookupEvidence(
                    kind="markdown_heading",
                    query=relative,
                    path=str(candidate),
                    found=True,
                    value=heading,
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            if heading is None:
                answers.append(
                    (
                        f"{relative}: file exists, "
                        "but no Markdown heading "
                        "was found."
                    )
                )

            else:
                answers.append(
                    (
                        f"{relative}: first "
                        "Markdown heading is "
                        f"{heading}"
                    )
                )

            continue

        if wants_contents:
            if _is_probably_binary(
                candidate
            ):
                return FastLookupResult(
                    handled=False,
                    answer="",
                    evidence=tuple(
                        evidence
                    ),
                    filesystem_operations=operations,
                    elapsed_ms=_elapsed_ms(
                        started
                    ),
                    capability="fallback",
                )

            text, truncated = (
                _read_text_bounded(
                    candidate
                )
            )

            suffix = (
                "\n... output truncated ..."
                if truncated
                else ""
            )

            evidence.append(
                FastLookupEvidence(
                    kind="file_read",
                    query=relative,
                    path=str(candidate),
                    found=True,
                    value=(
                        text[
                            :4000
                        ]
                    ),
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                (
                    f"{relative}:\n"
                    + text
                    + suffix
                )
            )

            continue

        if wants_existence:
            evidence.append(
                FastLookupEvidence(
                    kind="path_existence",
                    query=relative,
                    path=str(candidate),
                    found=True,
                    value="file",
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                f"{relative}: exists."
            )

            continue

        return FastLookupResult(
            handled=False,
            answer="",
            evidence=tuple(
                evidence
            ),
            filesystem_operations=operations,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )

    for filename in filenames:
        operation_started = (
            time.perf_counter()
        )

        matches = _search_exact_name(
            root,
            filename,
        )

        operations += 1
        handled = True

        relative_matches = [
            str(
                path.relative_to(
                    root
                )
            )
            for path in matches
        ]

        if matches:
            value = ", ".join(
                relative_matches
            )

            evidence.append(
                FastLookupEvidence(
                    kind="exact_name_search",
                    query=filename,
                    path=str(root),
                    found=True,
                    value=value,
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                (
                    f"{filename}: found "
                    f"{len(matches)} file(s): "
                    + value
                )
            )

        else:
            evidence.append(
                FastLookupEvidence(
                    kind="exact_name_search",
                    query=filename,
                    path=str(root),
                    found=False,
                    value=None,
                    elapsed_ms=_elapsed_ms(
                        operation_started
                    ),
                )
            )

            answers.append(
                (
                    f"{filename}: no "
                    f"{filename} found anywhere "
                    "under the workspace."
                )
            )

    if not handled:
        return FastLookupResult(
            handled=False,
            answer="",
            evidence=tuple(
                evidence
            ),
            filesystem_operations=operations,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )

    return FastLookupResult(
        handled=True,
        answer="\n\n".join(
            answers
        ),
        evidence=tuple(
            evidence
        ),
        filesystem_operations=operations,
        elapsed_ms=_elapsed_ms(
            started
        ),
        capability="filesystem_lookup",
    )


def execute_fast_lookup(
    *,
    task: str,
    workspace: str | Path,
) -> FastLookupResult:
    started = time.perf_counter()

    root = _safe_workspace(
        workspace
    )

    # NEXUS700_GIT_INTROSPECTION_BEFORE_GENERIC_READONLY
    git_capability = (
        _git_capability(
            task
        )
    )

    if git_capability is not None:
        return _git_result(
            task=task,
            root=root,
            capability=git_capability,
            started=started,
        )

    if not _looks_read_only(
        task
    ):
        return FastLookupResult(
            handled=False,
            answer="",
            evidence=(),
            filesystem_operations=0,
            elapsed_ms=_elapsed_ms(
                started
            ),
            capability="fallback",
        )


    paths = _extract_paths(
        task
    )

    filenames = (
        _extract_filenames(
            task,
            paths,
        )
    )

    grep_query = (
        _grep_query(
            task
        )
    )

    if grep_query is not None:
        return _literal_grep(
            task=task,
            root=root,
            query=grep_query,
            paths=paths,
            started=started,
        )

    if _wants_listing(
        task
    ):
        return _directory_listing(
            task=task,
            root=root,
            paths=paths,
            started=started,
        )

    if paths or filenames:
        return _path_queries(
            task=task,
            root=root,
            paths=paths,
            filenames=filenames,
            started=started,
        )

    return FastLookupResult(
        handled=False,
        answer="",
        evidence=(),
        filesystem_operations=0,
        elapsed_ms=_elapsed_ms(
            started
        ),
        capability="fallback",
    )
