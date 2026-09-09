from __future__ import annotations


LEVELS = {
    "read": 0,
    "network": 1,
    "write": 2,
    "process": 3,
    "computer": 4,
    "remote": 5,
    "destructive": 6,
}


ROLE_MAX = {
    "director": "network",
    "architect": "read",
    "qa": "read",
    "researcher": "network",
    "security": "network",
    "browser": "network",
    "coder": "process",
    "devops": "remote",
    "computer": "computer",
}


class PermissionEngine:
    def __init__(
        self,
        role,
        workspace_config=None,
        task_grants=None,
    ):
        self.role = role

        self.workspace_config = (
            workspace_config or {}
        )

        self.task_grants = set(
            task_grants or []
        )

    def role_allowed(
        self,
        permission,
    ):
        role_max = ROLE_MAX.get(
            self.role,
            "read",
        )

        return (
            LEVELS.get(
                permission,
                999,
            )
            <= LEVELS.get(
                role_max,
                0,
            )
        )

    def allowed(
        self,
        permission,
        tool_name=None,
    ):
        # Normal role permission.
        if self.role_allowed(
            permission
        ):
            return True

        # V8.2 task-scoped elevation:
        # a specific tool explicitly selected by the capability
        # resolver may exceed the generic role envelope.
        #
        # Example:
        # QA is normally read-only.
        # A web-verification QA task may receive web_fetch.
        # That grants network access to web_fetch only.
        if (
            tool_name
            and tool_name
            in self.task_grants
        ):
            return True

        return False

    def enforce(
        self,
        permission,
        tool_name,
    ):
        if not self.allowed(
            permission,
            tool_name,
        ):
            raise PermissionError(
                "NEXUS_PERMISSION_BLOCK="
                f"role={self.role} "
                f"tool={tool_name} "
                f"permission={permission}"
            )
