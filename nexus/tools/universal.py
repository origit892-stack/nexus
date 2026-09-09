from __future__ import annotations

import json
import os
import re
import shlex
import signal
import subprocess
import time
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx
from bs4 import BeautifulSoup


HOME = Path.home()
STATE = HOME / ".nexus"
PROCESS_DIR = STATE / "processes"
SCREENSHOT_DIR = STATE / "screenshots"

PROCESS_DIR.mkdir(parents=True, exist_ok=True)
SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)


class UniversalTools:

    def __init__(self, workspace, role):
        self.workspace = Path(workspace).resolve()
        self.role = role

    # =========================================================
    # WEB
    # =========================================================

    def web_fetch(self, url, max_chars=30000):
        parsed = urlparse(url)

        if parsed.scheme not in {"http", "https"}:
            return "WEB_BLOCKED=INVALID_SCHEME"

        try:
            r = httpx.get(
                url,
                timeout=30,
                follow_redirects=True,
                headers={
                    "User-Agent": "Mozilla/5.0 NexusAgent/1.0"
                },
            )

            r.raise_for_status()

            content_type = r.headers.get(
                "content-type",
                ""
            )

            if "text/html" in content_type:
                soup = BeautifulSoup(
                    r.text,
                    "lxml",
                )

                for tag in soup([
                    "script",
                    "style",
                    "noscript",
                ]):
                    tag.decompose()

                text = "\n".join(
                    x.strip()
                    for x in soup.stripped_strings
                )

            else:
                text = r.text

            return (
                f"URL={r.url}\n"
                f"STATUS={r.status_code}\n"
                f"CONTENT_TYPE={content_type}\n\n"
                f"{text[:int(max_chars)]}"
            )

        except Exception as e:
            return (
                "WEB_FETCH_ERROR="
                f"{type(e).__name__}: {e}"
            )

    def web_search(self, query, max_results=10):
        try:
            from ddgs import DDGS

            rows = []

            with DDGS() as ddgs:
                for item in ddgs.text(
                    query,
                    max_results=int(max_results),
                ):
                    rows.append({
                        "title": item.get("title"),
                        "url": item.get("href"),
                        "snippet": item.get("body"),
                    })

            return json.dumps(
                rows,
                indent=2,
                ensure_ascii=False,
            )

        except Exception as e:
            return (
                "WEB_SEARCH_ERROR="
                f"{type(e).__name__}: {e}"
            )

    # =========================================================
    # BROWSER / MACOS
    # =========================================================

    def browser_open(self, url):
        if self.role not in {
            "director",
            "researcher",
            "browser",
        }:
            return (
                f"BROWSER_PERMISSION_BLOCK={self.role}"
            )

        parsed = urlparse(url)

        if parsed.scheme not in {
            "http",
            "https",
        }:
            return "BROWSER_BLOCKED=INVALID_URL"

        r = subprocess.run(
            ["open", url],
            capture_output=True,
            text=True,
        )

        return (
            f"EXIT_CODE={r.returncode}\n"
            f"{r.stdout}\n{r.stderr}"
        )

    def screenshot(self):
        name = (
            time.strftime("%Y%m%d_%H%M%S")
            + "_"
            + uuid.uuid4().hex[:6]
            + ".png"
        )

        path = SCREENSHOT_DIR / name

        r = subprocess.run(
            [
                "screencapture",
                "-x",
                str(path),
            ],
            capture_output=True,
            text=True,
        )

        if r.returncode != 0:
            return (
                "SCREENSHOT_FAIL\n"
                + r.stderr
            )

        return (
            "SCREENSHOT=PASS\n"
            f"PATH={path}"
        )

    def computer_type(self, text):
        if self.role != "computer":
            return (
                "COMPUTER_CONTROL_BLOCKED="
                f"ROLE={self.role}"
            )

        safe = (
            text
            .replace("\\", "\\\\")
            .replace('"', '\\"')
        )

        script = (
            'tell application "System Events" '
            f'to keystroke "{safe}"'
        )

        r = subprocess.run(
            ["osascript", "-e", script],
            capture_output=True,
            text=True,
        )

        return (
            f"EXIT_CODE={r.returncode}\n"
            f"{r.stdout}\n{r.stderr}"
        )

    def computer_key(self, key):
        if self.role != "computer":
            return (
                "COMPUTER_CONTROL_BLOCKED="
                f"ROLE={self.role}"
            )

        allowed = {
            "return": 36,
            "escape": 53,
            "tab": 48,
            "space": 49,
            "delete": 51,
        }

        if key.lower() not in allowed:
            return (
                "COMPUTER_KEY_BLOCKED="
                f"{key}"
            )

        code = allowed[key.lower()]

        r = subprocess.run(
            [
                "osascript",
                "-e",
                (
                    'tell application "System Events" '
                    f"to key code {code}"
                ),
            ],
            capture_output=True,
            text=True,
        )

        return (
            f"EXIT_CODE={r.returncode}\n"
            f"{r.stdout}\n{r.stderr}"
        )

    # =========================================================
    # PROCESS MANAGER
    # =========================================================

    def process_start(
        self,
        command,
        cwd=None,
    ):
        if self.role not in {
            "coder",
            "devops",
            "computer",
        }:
            return (
                "PROCESS_START_BLOCKED="
                f"ROLE={self.role}"
            )

        work = Path(
            cwd or self.workspace
        ).expanduser().resolve()

        run_id = uuid.uuid4().hex[:12]

        stdout_path = (
            PROCESS_DIR
            / f"{run_id}.stdout.log"
        )

        stderr_path = (
            PROCESS_DIR
            / f"{run_id}.stderr.log"
        )

        out = stdout_path.open("w")
        err = stderr_path.open("w")

        proc = subprocess.Popen(
            command,
            shell=True,
            cwd=str(work),
            stdout=out,
            stderr=err,
            executable="/bin/bash",
            start_new_session=True,
        )

        meta = {
            "id": run_id,
            "pid": proc.pid,
            "command": command,
            "cwd": str(work),
            "stdout": str(stdout_path),
            "stderr": str(stderr_path),
            "started": time.time(),
        }

        (
            PROCESS_DIR
            / f"{run_id}.json"
        ).write_text(
            json.dumps(
                meta,
                indent=2,
            )
        )

        return json.dumps(
            meta,
            indent=2,
        )

    def process_status(self, process_id):
        meta_path = (
            PROCESS_DIR
            / f"{process_id}.json"
        )

        if not meta_path.exists():
            return (
                f"PROCESS_NOT_FOUND={process_id}"
            )

        meta = json.loads(
            meta_path.read_text()
        )

        pid = int(meta["pid"])

        try:
            os.kill(pid, 0)
            running = True
        except OSError:
            running = False

        stdout = Path(
            meta["stdout"]
        )

        stderr = Path(
            meta["stderr"]
        )

        return json.dumps(
            {
                **meta,
                "running": running,
                "stdout_tail": (
                    stdout.read_text(
                        errors="replace"
                    )[-10000:]
                    if stdout.exists()
                    else ""
                ),
                "stderr_tail": (
                    stderr.read_text(
                        errors="replace"
                    )[-10000:]
                    if stderr.exists()
                    else ""
                ),
            },
            indent=2,
        )

    def process_stop(self, process_id):
        if self.role not in {
            "devops",
            "computer",
            "coder",
        }:
            return (
                "PROCESS_STOP_BLOCKED="
                f"ROLE={self.role}"
            )

        meta_path = (
            PROCESS_DIR
            / f"{process_id}.json"
        )

        if not meta_path.exists():
            return (
                f"PROCESS_NOT_FOUND={process_id}"
            )

        meta = json.loads(
            meta_path.read_text()
        )

        pid = int(meta["pid"])

        try:
            os.killpg(
                pid,
                signal.SIGTERM,
            )

            return (
                f"PROCESS_STOP=PASS\nPID={pid}"
            )

        except Exception as e:
            return (
                "PROCESS_STOP_ERROR="
                f"{type(e).__name__}: {e}"
            )

    # =========================================================
    # SSH
    # =========================================================

    def ssh_run(
        self,
        host,
        command,
        user=None,
    ):
        if self.role != "devops":
            return (
                "SSH_BLOCKED="
                f"ROLE={self.role}"
            )

        target = (
            f"{user}@{host}"
            if user
            else host
        )

        r = subprocess.run(
            [
                "ssh",
                "-o",
                "BatchMode=yes",
                "-o",
                "ConnectTimeout=10",
                target,
                command,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        return (
            f"EXIT_CODE={r.returncode}\n"
            f"{r.stdout}\n"
            f"STDERR:\n{r.stderr}"
        )

    # =========================================================
    # ADVANCED CLI DISCOVERY
    # =========================================================

    def cli_which(self, name):
        import shutil

        path = shutil.which(name)

        if not path:
            return (
                f"CLI_NOT_FOUND={name}"
            )

        return (
            f"CLI_FOUND={name}\n"
            f"PATH={path}"
        )

    def cli_version(self, name):
        import shutil

        path = shutil.which(name)

        if not path:
            return (
                f"CLI_NOT_FOUND={name}"
            )

        candidates = [
            [path, "--version"],
            [path, "-V"],
            [path, "version"],
        ]

        for cmd in candidates:
            try:
                r = subprocess.run(
                    cmd,
                    capture_output=True,
                    text=True,
                    timeout=10,
                )

                if r.returncode == 0:
                    return (
                        r.stdout
                        or r.stderr
                    )[:5000]

            except Exception:
                pass

        return (
            f"CLI_VERSION_UNKNOWN={name}"
        )


def universal_schemas():
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": (
                    "Search the public web."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {
                            "type": "string"
                        },
                        "max_results": {
                            "type": "integer"
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
                "name": "web_fetch",
                "description": (
                    "Fetch and extract text "
                    "from a web URL."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string"
                        },
                        "max_chars": {
                            "type": "integer"
                        },
                    },
                    "required": [
                        "url"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "browser_open",
                "description": (
                    "Open a URL in the default "
                    "desktop browser."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "url"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "screenshot",
                "description": (
                    "Capture the current macOS screen."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {},
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "computer_type",
                "description": (
                    "Type text using macOS "
                    "Accessibility automation."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "text"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "computer_key",
                "description": (
                    "Press an approved keyboard key."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "key"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "process_start",
                "description": (
                    "Start and track a long-running "
                    "CLI process."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {
                            "type": "string"
                        },
                        "cwd": {
                            "type": "string"
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
                "name": "process_status",
                "description": (
                    "Inspect a tracked process."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_id": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "process_id"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "process_stop",
                "description": (
                    "Stop a tracked process."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "process_id": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "process_id"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "ssh_run",
                "description": (
                    "Run a command on an explicitly "
                    "configured SSH target."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "host": {
                            "type": "string"
                        },
                        "command": {
                            "type": "string"
                        },
                        "user": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "host",
                        "command"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "cli_which",
                "description": (
                    "Locate a CLI executable."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "name"
                    ],
                },
            },
        },

        {
            "type": "function",
            "function": {
                "name": "cli_version",
                "description": (
                    "Detect CLI version."
                ),
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string"
                        },
                    },
                    "required": [
                        "name"
                    ],
                },
            },
        },
    ]
