from __future__ import annotations

import json
import os
import subprocess
import uuid

from dataclasses import (
    asdict,
    dataclass,
)
from datetime import (
    datetime,
    timezone,
)
from pathlib import Path


def utc_now():
    return datetime.now(
        timezone.utc
    ).isoformat()


@dataclass
class Project:
    id: str
    name: str
    path: str
    created_at: str
    last_opened_at: str | None = None

    @property
    def resolved_path(self):
        return Path(
            self.path
        ).expanduser().resolve()


class ProjectRegistry:
    def __init__(
        self,
        registry_path=None,
    ):
        self.registry_path = (
            Path(
                registry_path
            ).expanduser().resolve()
            if registry_path
            else (
                Path.home()
                / ".nexus"
                / "projects.json"
            )
        )

        self.registry_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

    def _load(self):
        if not self.registry_path.exists():
            return {
                "version": 1,
                "active_project_id": None,
                "projects": [],
            }

        try:
            data = json.loads(
                self.registry_path.read_text()
            )

        except Exception:
            data = {}

        return {
            "version": int(
                data.get(
                    "version",
                    1,
                )
            ),
            "active_project_id": data.get(
                "active_project_id"
            ),
            "projects": list(
                data.get(
                    "projects",
                    [],
                )
            ),
        }

    def _save(
        self,
        data,
    ):
        temp = self.registry_path.with_suffix(
            ".tmp"
        )

        temp.write_text(
            json.dumps(
                data,
                ensure_ascii=False,
                indent=2,
            )
        )

        temp.replace(
            self.registry_path
        )

    def list(self):
        """Return registered projects, unique by canonical path."""
        data = self._load()

        result = []
        seen_paths = set()

        for raw in data["projects"]:
            try:
                project = Project(**raw)
                canonical = str(
                    project.resolved_path
                )
            except (TypeError, KeyError, ValueError, OSError):
                continue

            if canonical in seen_paths:
                continue

            seen_paths.add(canonical)
            project.path = canonical
            result.append(project)

        return result

    def get(
        self,
        project_id_or_name,
    ):
        key = str(
            project_id_or_name
        ).strip().lower()

        for project in self.list():
            if (
                project.id.lower()
                == key
                or project.name.lower()
                == key
            ):
                return project

        return None

    def active(self):
        data = self._load()

        active_id = data.get(
            "active_project_id"
        )

        if not active_id:
            return None

        return self.get(
            active_id
        )

    def add(
        self,
        path,
        name=None,
    ):
        resolved = Path(
            path
        ).expanduser().resolve()

        if not resolved.exists():
            raise FileNotFoundError(
                str(resolved)
            )

        if not resolved.is_dir():
            raise NotADirectoryError(
                str(resolved)
            )

        for existing in self.list():
            if (
                existing.resolved_path
                == resolved
            ):
                self.use(
                    existing.id
                )
                return existing

        project = Project(
            id=(
                resolved.name
                .lower()
                .replace(
                    " ",
                    "-",
                )
                + "-"
                + uuid.uuid4().hex[:6]
            ),
            name=(
                str(name).strip()
                if name
                else resolved.name
            ),
            path=str(
                resolved
            ),
            created_at=utc_now(),
            last_opened_at=utc_now(),
        )

        data = self._load()

        data[
            "projects"
        ].append(
            asdict(project)
        )

        data[
            "active_project_id"
        ] = project.id

        self._save(
            data
        )

        (
            resolved
            / ".nexus"
            / "sessions"
        ).mkdir(
            parents=True,
            exist_ok=True,
        )

        return project

    def remove(
        self,
        project_id_or_name,
    ):
        project = self.get(
            project_id_or_name
        )

        if not project:
            return False

        data = self._load()

        data[
            "projects"
        ] = [
            p
            for p in data[
                "projects"
            ]
            if p.get(
                "id"
            )
            != project.id
        ]

        if (
            data.get(
                "active_project_id"
            )
            == project.id
        ):
            data[
                "active_project_id"
            ] = (
                data["projects"][0]["id"]
                if data["projects"]
                else None
            )

        self._save(
            data
        )

        return True

    def use(
        self,
        project_id_or_name,
    ):
        project = self.get(
            project_id_or_name
        )

        if not project:
            raise KeyError(
                project_id_or_name
            )

        data = self._load()

        data[
            "active_project_id"
        ] = project.id

        for raw in data[
            "projects"
        ]:
            if raw.get(
                "id"
            ) == project.id:
                raw[
                    "last_opened_at"
                ] = utc_now()

        self._save(
            data
        )

        return self.get(
            project.id
        )

    def choose_folder_macos(
        self,
    ):
        script = (
            'POSIX path of '
            '(choose folder with prompt '
            '"Choose a Nexus project folder")'
        )

        result = subprocess.run(
            [
                "osascript",
                "-e",
                script,
            ],
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            return None

        value = result.stdout.strip()

        return (
            value
            if value
            else None
        )
