from __future__ import annotations

import subprocess

from pathlib import Path

from .context import (
    build_agent_context,
)


def _clean_list(
    value,
):
    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        str(item).strip()
        for item in value
        if str(item).strip()
    ]


def _safe_git_info(
    project_path,
):
    root = Path(
        project_path
    )

    git_dir = (
        root
        / ".git"
    )

    if not git_dir.exists():
        return {
            "git_branch": None,
            "git_tracked_dirty_count": None,
        }

    branch = None
    dirty_count = None

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "branch",
                "--show-current",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            value = (
                result.stdout
                .strip()
            )

            branch = (
                value
                if value
                else None
            )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        branch = None

    try:
        result = subprocess.run(
            [
                "git",
                "-C",
                str(root),
                "status",
                "--porcelain",
                "--untracked-files=no",
            ],
            check=False,
            capture_output=True,
            text=True,
            timeout=2,
        )

        if result.returncode == 0:
            dirty_count = len(
                [
                    line
                    for line in (
                        result.stdout
                        .splitlines()
                    )
                    if line.strip()
                ]
            )

    except (
        OSError,
        subprocess.SubprocessError,
    ):
        dirty_count = None

    return {
        "git_branch": branch,
        "git_tracked_dirty_count": (
            dirty_count
        ),
    }


def reconcile_session_state(
    session,
    project_path,
):
    root = Path(
        project_path
    ).expanduser().resolve()

    working = (
        session.working_state
        if isinstance(
            session.working_state,
            dict,
        )
        else {}
    )

    resume = (
        session.resume_state
        if isinstance(
            session.resume_state,
            dict,
        )
        else {}
    )

    result = {
        "project_exists": (
            root.exists()
        ),
        "nexus_workspace_exists": (
            root
            / ".nexus"
        ).exists(),
        "pending_count": len(
            _clean_list(
                working.get(
                    "pending_work"
                )
            )
        ),
        "completed_count": len(
            _clean_list(
                working.get(
                    "completed_work"
                )
            )
        ),
        "blocker_count": len(
            _clean_list(
                working.get(
                    "blockers"
                )
            )
        ),
        "active_item": working.get(
            "active_item"
        ),
        "checkpoint": working.get(
            "last_checkpoint"
        ),
        "checkpoint_serial": (
            working.get(
                "checkpoint_serial",
                0,
            )
        ),
        "resume_status": resume.get(
            "last_status"
        ),
    }

    result.update(
        _safe_git_info(
            root
        )
    )

    return result


def build_resume_instruction(
    session,
    project_path=None,
):
    working = (
        session.working_state
        if isinstance(
            session.working_state,
            dict,
        )
        else {}
    )

    resume = (
        session.resume_state
        if isinstance(
            session.resume_state,
            dict,
        )
        else {}
    )

    context = build_agent_context(
        session
    )

    objective = (
        working.get(
            "objective"
        )
        or session.objective
    )

    active_item = working.get(
        "active_item"
    )

    plan = _clean_list(
        working.get(
            "current_plan"
        )
    )

    completed = _clean_list(
        working.get(
            "completed_work"
        )
    )

    pending = _clean_list(
        working.get(
            "pending_work"
        )
    )

    blockers = _clean_list(
        working.get(
            "blockers"
        )
    )

    checkpoint = working.get(
        "last_checkpoint"
    )

    facts = _clean_list(
        context.get(
            "durable_facts"
        )
    )

    summary = context.get(
        "summary"
    )

    priority = (
        active_item
        or next(
            (
                item
                for item in pending
                if item
                not in completed
            ),
            None,
        )
    )

    lines = [
        (
            "Resume this existing Nexus session. "
            "Continue from the current real project state; "
            "do not restart the task from scratch."
        ),
        "",
        f"OBJECTIVE: {objective}",
    ]

    if priority:
        lines.extend(
            [
                "",
                f"PRIORITY ITEM: {priority}",
            ]
        )

    if plan:
        lines.extend(
            [
                "",
                "CURRENT PLAN:",
                *[
                    f"- {item}"
                    for item in plan
                ],
            ]
        )

    if completed:
        lines.extend(
            [
                "",
                "COMPLETED WORK:",
                *[
                    f"- {item}"
                    for item in completed
                ],
            ]
        )

    if pending:
        lines.extend(
            [
                "",
                "PENDING WORK:",
                *[
                    f"- {item}"
                    for item in pending
                ],
            ]
        )

    if blockers:
        lines.extend(
            [
                "",
                "BLOCKERS:",
                *[
                    f"- {item}"
                    for item in blockers
                ],
            ]
        )

    if checkpoint:
        lines.extend(
            [
                "",
                f"LAST CHECKPOINT: {checkpoint}",
            ]
        )

    if resume.get(
        "last_status"
    ):
        lines.extend(
            [
                "",
                (
                    "LAST SESSION STATUS: "
                    f"{resume.get('last_status')}"
                ),
            ]
        )

    if summary:
        lines.extend(
            [
                "",
                "COMPACTED CONTEXT:",
                summary,
            ]
        )

    if facts:
        lines.extend(
            [
                "",
                "DURABLE FACTS:",
                *[
                    f"- {fact}"
                    for fact in facts
                ],
            ]
        )

    recent = context.get(
        "recent_history",
        []
    )

    if recent:
        lines.extend(
            [
                "",
                "RECENT HISTORY:",
            ]
        )

        for entry in recent:
            if not isinstance(
                entry,
                dict,
            ):
                continue

            kind = str(
                entry.get(
                    "type",
                    "event",
                )
            ).upper()

            text = str(
                entry.get(
                    "text",
                    "",
                )
            ).strip()

            if text:
                lines.append(
                    f"{kind}: {text}"
                )

    if project_path is not None:
        reconciliation = (
            reconcile_session_state(
                session,
                project_path,
            )
        )

        lines.extend(
            [
                "",
                "CURRENT PROJECT RECONCILIATION:",
                (
                    "- project_exists: "
                    f"{reconciliation['project_exists']}"
                ),
                (
                    "- nexus_workspace_exists: "
                    f"{reconciliation['nexus_workspace_exists']}"
                ),
                (
                    "- pending_count: "
                    f"{reconciliation['pending_count']}"
                ),
                (
                    "- completed_count: "
                    f"{reconciliation['completed_count']}"
                ),
                (
                    "- blocker_count: "
                    f"{reconciliation['blocker_count']}"
                ),
            ]
        )

        if reconciliation[
            "git_branch"
        ] is not None:
            lines.append(
                (
                    "- git_branch: "
                    f"{reconciliation['git_branch']}"
                )
            )

        if reconciliation[
            "git_tracked_dirty_count"
        ] is not None:
            lines.append(
                (
                    "- git_tracked_dirty_count: "
                    f"{reconciliation['git_tracked_dirty_count']}"
                )
            )

    lines.extend(
        [
            "",
            (
                "Before making changes, inspect the current project "
                "state and reconcile it with this session state."
            ),
            (
                "Do not repeat work already listed as completed "
                "unless current project evidence shows it is incomplete."
            ),
            (
                "Resolve relevant blockers before advancing when possible."
            ),
        ]
    )

    if priority:
        lines.append(
            (
                "Continue with the priority item above."
            )
        )
    else:
        lines.append(
            (
                "If there is no active or pending item, inspect the "
                "current state and determine the next useful step."
            )
        )

    lines.extend(
        [
            "",
            "RESUME STATE CONTRACT:",
            (
                "When you actually complete or otherwise change "
                "a durable pending work item during this resumed "
                "turn, that is a durable session-state change."
            ),
            (
                "In that case, your FINAL ASSISTANT RESPONSE "
                "must include the NEXUS_STATE_UPDATE block "
                "required by the session protocol."
            ),
            (
                "For work completed in this resumed turn, place "
                "the exact completed item text in completed_work."
            ),
            (
                "Remove completed items from pending_work and "
                "return the full remaining pending list."
            ),
            (
                "Set active_item to the next remaining pending "
                "item, or null when no pending work remains."
            ),
            (
                "Do not substitute memory_add, a checkpoint, "
                "tool output, or prose for NEXUS_STATE_UPDATE."
            ),
            (
                "Once the requested pending work is completed "
                "and verified, stop using tools and return the "
                "final response."
            ),
        ]
    )

    return "\n".join(
        lines
    )
