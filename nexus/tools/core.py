import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from ..acceptance import (
    Criterion,
    Evidence,
    verify,
)


READ_ONLY_ROLES = {
    "director",
    "architect",
    "qa",
    "researcher",
    "security",
}


WRITE_COMMANDS = re.compile(
    r"(^|[;&|]\s*)"
    r"(rm|mv|cp|touch|mkdir|rmdir|ln|chmod|chown|truncate)\b"
    r"|\bpip(?:3)?\s+install\b"
    r"|\bnpm\s+(install|i|update|uninstall)\b"
    r"|\bbrew\s+(install|uninstall|upgrade)\b"
    r"|\bgit\s+(reset|clean|checkout|restore|commit|add|rm|mv|merge|rebase)\b"
    r"|\bsed\s+-i\b"
    r"|>>"
    r"|(?<![0-9])>(?![&0-9])",
    re.I,
)


class Tools:
    def __init__(
        self,
        workspace,
        role,
        run_id,
    ):
        self.workspace = (
            Path(workspace)
            .expanduser()
            .resolve()
        )

        self.role = role
        self.run_id = run_id

        self.checkpoints = (
            self.workspace
            / ".nexus"
            / "checkpoints"
        )

        self.checkpoints.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.has_checkpoint = False

    def _inside(
        self,
        p,
    ):
        try:
            p.relative_to(
                self.workspace
            )

            return True

        except ValueError:
            return False

    def path(
        self,
        raw,
    ):
        p = Path(
            raw
        ).expanduser()

        if not p.is_absolute():
            p = (
                self.workspace
                / p
            )

        p = p.resolve()

        if not self._inside(p):
            raise RuntimeError(
                f"WORKSPACE_SANDBOX_BLOCK={p}"
            )

        return p

    def read_file(
        self,
        path,
        start_line=1,
        max_lines=400,
    ):
        try:
            p = self.path(
                path
            )

        except Exception as e:
            return str(e)

        if not p.is_file():
            return (
                f"FILE_NOT_FOUND={p}"
            )

        lines = p.read_text(
            errors="replace"
        ).splitlines()

        start = max(
            0,
            int(start_line) - 1,
        )

        end = min(
            len(lines),
            start + int(max_lines),
        )

        return "\n".join(
            f"{i+1}: {lines[i]}"
            for i in range(
                start,
                end,
            )
        )

    def list_files(
        self,
        path=".",
        max_entries=300,
    ):
        try:
            p = self.path(
                path
            )

        except Exception as e:
            return str(e)

        if not p.exists():
            return (
                f"PATH_NOT_FOUND={p}"
            )

        if p.is_file():
            return str(p)

        out = []

        for child in sorted(
            p.iterdir()
        ):
            out.append(
                (
                    "DIR "
                    if child.is_dir()
                    else "FILE "
                )
                + str(child)
            )

            if len(out) >= int(
                max_entries
            ):
                out.append(
                    "TRUNCATED=YES"
                )

                break

        return "\n".join(
            out
        )

    def search_files(
        self,
        query,
        path=".",
    ):
        try:
            p = self.path(
                path
            )

        except Exception as e:
            return str(e)

        if not shutil.which(
            "rg"
        ):
            return (
                "RG_NOT_INSTALLED"
            )

        r = subprocess.run(
            [
                "rg",
                "-n",
                "--hidden",
                "--glob",
                "!.git/**",
                query,
                str(p),
            ],
            text=True,
            capture_output=True,
            timeout=60,
        )

        return (
            r.stdout
            + (
                "\nSTDERR:\n"
                + r.stderr
                if r.stderr
                else ""
            )
        )[-40000:]

    def checkpoint(
        self,
        label="automatic",
    ):
        if self.has_checkpoint:
            return (
                "CHECKPOINT=ALREADY_PRESENT"
            )

        ts = time.strftime(
            "%Y%m%d_%H%M%S"
        )

        safe = re.sub(
            r"[^A-Za-z0-9_.-]+",
            "_",
            label,
        )

        dest = (
            self.checkpoints
            / f"{ts}_{self.run_id}_{safe}"
        )

        dest.mkdir(
            parents=True,
            exist_ok=False,
        )

        def run(cmd):
            r = subprocess.run(
                cmd,
                shell=True,
                cwd=str(
                    self.workspace
                ),
                text=True,
                capture_output=True,
                executable="/bin/bash",
            )

            return (
                f"EXIT_CODE={r.returncode}\n"
                + r.stdout
                + "\n"
                + r.stderr
            )

        (
            dest
            / "git_status.txt"
        ).write_text(
            run(
                "git status --short --branch"
            )
        )

        (
            dest
            / "git_diff.patch"
        ).write_text(
            run(
                "git diff"
            )
        )

        self.has_checkpoint = True

        return (
            "CHECKPOINT=PASS\n"
            f"PATH={dest}"
        )

    def shell(
        self,
        command,
        timeout=900,
    ):
        if ".." in command:
            return (
                "SAFETY_BLOCK=PARENT_TRAVERSAL"
            )

        mutating = bool(
            WRITE_COMMANDS.search(
                command
            )
        )

        if (
            self.role
            in READ_ONLY_ROLES
            and mutating
        ):
            return (
                "SAFETY_BLOCK="
                f"ROLE_READ_ONLY={self.role}"
            )

        prefix = ""

        if mutating:
            prefix = (
                self.checkpoint(
                    "auto_before_write"
                )
                + "\n"
            )

        try:
            r = subprocess.run(
                command,
                shell=True,
                cwd=str(
                    self.workspace
                ),
                text=True,
                capture_output=True,
                timeout=int(
                    timeout
                ),
                executable="/bin/bash",
            )

            return (
                prefix
                + f"EXIT_CODE={r.returncode}\n"
                + r.stdout
                + (
                    "\nSTDERR:\n"
                    + r.stderr
                    if r.stderr
                    else ""
                )
            )[-50000:]

        except subprocess.TimeoutExpired:
            return (
                prefix
                + f"TIMEOUT={timeout}"
            )

    def write_file(
        self,
        path,
        content,
    ):
        if self.role != "coder":
            return (
                "SAFETY_BLOCK="
                f"ROLE_WRITE_FORBIDDEN={self.role}"
            )

        try:
            p = self.path(
                path
            )

        except Exception as e:
            return str(e)

        checkpoint = (
            self.checkpoint(
                "auto_before_write"
            )
        )

        p.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        p.write_text(
            content
        )

        return (
            checkpoint
            + "\n"
            + f"WROTE={p}"
        )

    def replace_text(
        self,
        path,
        old,
        new,
        count=1,
    ):
        if self.role != "coder":
            return (
                "SAFETY_BLOCK="
                f"ROLE_WRITE_FORBIDDEN={self.role}"
            )

        try:
            p = self.path(
                path
            )

        except Exception as e:
            return str(e)

        if not p.is_file():
            return (
                f"FILE_NOT_FOUND={p}"
            )

        text = p.read_text()

        if old not in text:
            return (
                "OLD_TEXT_NOT_FOUND"
            )

        checkpoint = (
            self.checkpoint(
                "auto_before_write"
            )
        )

        p.write_text(
            text.replace(
                old,
                new,
                int(count),
            )
        )

        return (
            checkpoint
            + "\n"
            + f"PATCHED={p}"
        )

    def acceptance_verify(
        self,
        name,
        requires_real_implementation=False,
        requires_execution=False,
        description="",
        command=None,
        exit_code=None,
        artifacts=None,
        evidence_text="",
    ):
        result = verify(
            Criterion(
                name,
                bool(
                    requires_real_implementation
                ),
                bool(
                    requires_execution
                ),
            ),
            Evidence(
                description,
                command,
                exit_code,
                artifacts or [],
                evidence_text,
            ),
        )

        return json.dumps(
            {
                "criterion": name,
                "passed": result.passed,
                "reason": result.reason,
                "artifact_hashes": (
                    result.artifact_hashes
                ),
            },
            indent=2,
        )

    def schemas(
        self,
    ):
        schemas = [
            {
                "type": "function",
                "function": {
                    "name": "read_file",
                    "description": (
                        "Read a workspace file."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                            },
                            "start_line": {
                                "type": "integer",
                            },
                            "max_lines": {
                                "type": "integer",
                            },
                        },
                        "required": [
                            "path"
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "list_files",
                    "description": (
                        "List workspace files."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                            },
                            "max_entries": {
                                "type": "integer",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_files",
                    "description": (
                        "Search workspace files."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "query": {
                                "type": "string",
                            },
                            "path": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "query"
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "shell",
                    "description": (
                        "Run a shell command inside "
                        "the workspace."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "command": {
                                "type": "string",
                            },
                            "timeout": {
                                "type": "integer",
                            },
                        },
                        "required": [
                            "command"
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "acceptance_verify",
                    "description": (
                        "Verify acceptance evidence. "
                        "Stub/mock/placeholder evidence "
                        "is rejected when real "
                        "implementation is required."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                            },
                            "requires_real_implementation": {
                                "type": "boolean",
                            },
                            "requires_execution": {
                                "type": "boolean",
                            },
                            "description": {
                                "type": "string",
                            },
                            "command": {
                                "type": "string",
                            },
                            "exit_code": {
                                "type": "integer",
                            },
                            "artifacts": {
                                "type": "array",
                                "items": {
                                    "type": "string",
                                },
                            },
                            "evidence_text": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "name"
                        ],
                    },
                },
            },
        ]

        if self.role == "coder":
            schemas.extend(
                [
                    {
                        "type": "function",
                        "function": {
                            "name": "write_file",
                            "description": (
                                "Write a workspace file "
                                "with automatic checkpoint."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                    },
                                    "content": {
                                        "type": "string",
                                    },
                                },
                                "required": [
                                    "path",
                                    "content",
                                ],
                            },
                        },
                    },
                    {
                        "type": "function",
                        "function": {
                            "name": "replace_text",
                            "description": (
                                "Patch exact text with "
                                "automatic checkpoint."
                            ),
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "path": {
                                        "type": "string",
                                    },
                                    "old": {
                                        "type": "string",
                                    },
                                    "new": {
                                        "type": "string",
                                    },
                                    "count": {
                                        "type": "integer",
                                    },
                                },
                                "required": [
                                    "path",
                                    "old",
                                    "new",
                                ],
                            },
                        },
                    },
                ]
            )

        return schemas

    def execute(
        self,
        name,
        args,
    ):
        fn = getattr(
            self,
            name,
            None,
        )

        if fn is None:
            return (
                f"UNKNOWN_TOOL={name}"
            )

        try:
            return fn(
                **args
            )

        except Exception as e:
            return (
                "TOOL_EXCEPTION="
                f"{type(e).__name__}: {e}"
            )
