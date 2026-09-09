"""
Nexus 1.7 Wave 2 - Context compaction and session state management.

This module provides deterministic context compaction logic without LLM requirements,
supports working state helpers for objectives, plans, completed work, pending work,
blockers, checkpoints, and handles migration of missing/null fields gracefully.
"""

from __future__ import annotations

import json
from dataclasses import (
    asdict,
    dataclass,
    field,
)
from datetime import (
    datetime,
    timezone,
)
from typing import (
    Any,
    Optional,
)


def utc_now():
    """Return current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


@dataclass
class WorkingState:
    """Represents the working state of a session including objectives, plans, and blockers."""
    
    objective: str = ""
    plan: list[dict] = field(default_factory=list)
    completed_work: list[str] = field(default_factory=list)
    pending_work: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    checkpoint: Optional[str] = None
    
    def __post_init__(self):
        """Ensure all fields are properly initialized."""
        if self.objective is None:
            self.objective = ""
        if self.plan is None:
            self.plan = []
        if self.completed_work is None:
            self.completed_work = []
        if self.pending_work is None:
            self.pending_work = []
        if self.blockers is None:
            self.blockers = []
    
    def to_dict(self) -> dict[str, Any]:
        """Convert working state to dictionary for serialization."""
        return {
            "objective": self.objective,
            "plan": self.plan,
            "completed_work": self.completed_work,
            "pending_work": self.pending_work,
            "blockers": self.blockers,
            "checkpoint": self.checkpoint,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> WorkingState:
        """Create WorkingState from dictionary with migration support."""
        # Handle missing/null fields gracefully for backward compatibility
        return cls(
            objective=data.get("objective", ""),
            plan=data.get("plan", []),
            completed_work=data.get("completed_work", []),
            pending_work=data.get("pending_work", []),
            blockers=data.get("blockers", []),
            checkpoint=data.get("checkpoint"),
        )


@dataclass
class ContextState:
    """Represents the context state including history and metadata."""
    
    history: list[dict] = field(default_factory=list)
    turn_count: int = 0
    status: str = "NEW"
    created_at: str = ""
    updated_at: str = ""
    
    def __post_init__(self):
        """Ensure all fields are properly initialized."""
        if self.history is None:
            self.history = []
        if self.turn_count < 0:
            self.turn_count = 0
    
    def to_dict(self) -> dict[str, Any]:
        """Convert context state to dictionary for serialization."""
        return {
            "history": self.history,
            "turn_count": self.turn_count,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ContextState:
        """Create ContextState from dictionary with migration support."""
        # Handle missing/null fields gracefully for backward compatibility
        return cls(
            history=data.get("history", []),
            turn_count=data.get("turn_count", 0),
            status=data.get("status", "NEW"),
            created_at=data.get("created_at", ""),
            updated_at=data.get("updated_at", ""),
        )


@dataclass
class ResumeState:
    """Represents the resume state for session resumption."""
    
    last_turn_result: Optional[str] = None
    interrupted_by: Optional[str] = None
    can_resume: bool = True
    
    def __post_init__(self):
        """Ensure all fields are properly initialized."""
        if self.last_turn_result is None:
            self.last_turn_result = ""
        if self.interrupted_by is None:
            self.interrupted_by = ""
    
    def to_dict(self) -> dict[str, Any]:
        """Convert resume state to dictionary for serialization."""
        return {
            "last_turn_result": self.last_turn_result,
            "interrupted_by": self.interrupted_by,
            "can_resume": self.can_resume,
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ResumeState:
        """Create ResumeState from dictionary with migration support."""
        # Handle missing/null fields gracefully for backward compatibility
        return cls(
            last_turn_result=data.get("last_turn_result"),
            interrupted_by=data.get("interrupted_by"),
            can_resume=data.get("can_resume", True),
        )


@dataclass
class SessionContext:
    """
    Complete session context combining working state, context state, and resume state.
    
    This class provides the unified view of a Nexus session including:
    - WorkingState: objectives, plans, completed/pending work, blockers, checkpoint
    - ContextState: history, turn count, status, timestamps
    - ResumeState: last result, interruption info, resumption capability
    
    Supports backward compatibility with existing sessions that may have missing fields.
    """
    
    working_state: WorkingState = field(default_factory=WorkingState)
    context_state: ContextState = field(default_factory=ContextState)
    resume_state: ResumeState = field(default_factory=ResumeState)
    
    def __post_init__(self):
        """Ensure all fields are properly initialized."""
        if self.working_state is None:
            self.working_state = WorkingState()
        if self.context_state is None:
            self.context_state = ContextState()
        if self.resume_state is None:
            self.resume_state = ResumeState()
    
    def to_dict(self) -> dict[str, Any]:
        """Convert session context to dictionary for serialization."""
        return {
            "working_state": self.working_state.to_dict(),
            "context_state": self.context_state.to_dict(),
            "resume_state": self.resume_state.to_dict(),
        }
    
    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> SessionContext:
        """Create SessionContext from dictionary with migration support."""
        # Handle missing/null fields gracefully for backward compatibility
        
        working_data = data.get("working_state") or {}
        context_data = data.get("context_state") or {}
        resume_data = data.get("resume_state") or {}
        
        return cls(
            working_state=WorkingState.from_dict(working_data),
            context_state=ContextState.from_dict(context_data),
            resume_state=ResumeState.from_dict(resume_data),
        )


def compact_context(history: list[dict], max_history_size: int = 100) -> list[dict]:
    """
    Deterministically compact session history without LLM requirements.
    
    This function removes redundant or duplicate entries while preserving
    the essential context needed for session resumption. The compaction is
    deterministic - same input always produces same output.
    
    Args:
        history: List of history entries to compact
        max_history_size: Maximum number of entries to keep after compaction
    
    Returns:
        Compacted list of history entries
    """
    if not history:
        return []
    
    # Track seen text patterns to avoid duplicates
    seen_texts = set()
    compacted = []
    
    for entry in history:
        text = str(entry.get("text", "")).strip()
        
        # Skip empty entries
        if not text:
            continue
        
        # Check for exact duplicate (same type and text)
        entry_type = str(entry.get("type", "unknown"))
        key = f"{entry_type}:{text}"
        
        if key in seen_texts:
            continue
        
        seen_texts.add(key)
        compacted.append(entry)
    
    # If we're still over the limit, remove oldest entries from non-critical types
    while len(compacted) > max_history_size:
        # Prioritize keeping recent result and instruction entries
        entry = compacted.pop(0)
        
        # Only remove if it's not a critical type (result or instruction)
        entry_type = str(entry.get("type", "unknown"))
        if entry_type in ("result", "instruction"):
            # Put back at the end to preserve order
            compacted.insert(-1, entry)
    
    return compacted


def normalize_session_data(session_data: dict[str, Any]) -> dict[str, Any]:
    """
    Normalize session data for schema consistency.
    
    Handles migration of missing/null fields gracefully for backward compatibility
    with existing sessions that may have been created before Wave 2 changes.
    
    Args:
        session_data: Raw session data from storage
    
    Returns:
        Normalized session data with all required fields present
    """
    # Initialize default values for missing fields
    normalized = {
        "id": session_data.get("id", ""),
        "title": session_data.get("title", ""),
        "project_path": session_data.get("project_path", ""),
        "objective": session_data.get("objective", ""),
        "status": session_data.get("status", "NEW"),
        "created_at": session_data.get("created_at", ""),
        "updated_at": session_data.get("updated_at", ""),
        "run_id": session_data.get("run_id"),
        "last_result": session_data.get("last_result"),
        "history": session_data.get("history") or [],
    }
    
    # Add Wave 2 fields if not present (backward compatible)
    normalized["working_state"] = {
        "objective": normalized["objective"],
        "plan": [],
        "completed_work": [],
        "pending_work": [],
        "blockers": [],
        "checkpoint": None,
    }
    
    normalized["context_state"] = {
        "history": normalized["history"],
        "turn_count": len(normalized["history"]),
        "status": normalized["status"],
        "created_at": normalized["created_at"],
        "updated_at": normalized["updated_at"],
    }
    
    normalized["resume_state"] = {
        "last_turn_result": normalized.get("last_result"),
        "interrupted_by": None,
        "can_resume": True,
    }
    
    return normalized


def migrate_session_data(session_data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """
    Migrate legacy session data to new schema.
    
    Returns the migrated data and a boolean indicating if migration occurred.
    
    Args:
        session_data: Raw session data from storage
    
    Returns:
        Tuple of (migrated_data, migration_occurred)
    """
    # Check if already migrated (has working_state field)
    if "working_state" in session_data:
        return session_data, False
    
    # Perform migration
    normalized = normalize_session_data(session_data)
    
    # Update timestamps for migrated sessions
    now = utc_now()
    normalized["context_state"]["updated_at"] = now
    normalized["resume_state"]["interrupted_by"] = None
    
    return normalized, True


COMPACTION_THRESHOLD = 24
RECENT_HISTORY_WINDOW = 12
SUMMARY_TEXT_LIMIT = 320


def _entry_text(
    entry,
):
    if not isinstance(
        entry,
        dict,
    ):
        return ""

    return str(
        entry.get(
            "text",
            "",
        )
    ).strip()


def _entry_type(
    entry,
):
    if not isinstance(
        entry,
        dict,
    ):
        return "event"

    return str(
        entry.get(
            "type",
            "event",
        )
    ).strip().lower()


def deterministic_summary(
    entries,
):
    lines = []

    for entry in entries:
        kind = _entry_type(
            entry
        )

        if kind not in {
            "objective",
            "instruction",
            "result",
            "failure",
            "error",
            "interrupt",
        }:
            continue

        text = _entry_text(
            entry
        )

        if not text:
            continue

        if len(text) > SUMMARY_TEXT_LIMIT:
            text = (
                text[
                    :SUMMARY_TEXT_LIMIT
                ]
                + "..."
            )

        lines.append(
            f"{kind.upper()}: {text}"
        )

    if not lines:
        return None

    return "\n".join(
        lines
    )


def build_agent_context(
    session,
):
    history = list(
        session.history
        or []
    )

    state = dict(
        session.context_state
        or {}
    )

    window = state.get(
        "recent_window",
        RECENT_HISTORY_WINDOW,
    )

    try:
        window = max(
            1,
            int(
                window
            ),
        )
    except (
        TypeError,
        ValueError,
    ):
        window = RECENT_HISTORY_WINDOW

    if len(
        history
    ) <= COMPACTION_THRESHOLD:
        recent = history
        summary = None
        compacted_through = 0
    else:
        compacted_through = max(
            0,
            len(
                history
            )
            - window,
        )

        older = history[
            :compacted_through
        ]

        recent = history[
            compacted_through:
        ]

        summary = (
            deterministic_summary(
                older
            )
        )

    state[
        "summary"
    ] = summary

    state[
        "compacted_through"
    ] = compacted_through

    state[
        "recent_window"
    ] = window

    state[
        "updated_at"
    ] = utc_now()

    session.context_state = state

    return {
        "working_state": dict(
            session.working_state
            or {}
        ),
        "summary": summary,
        "durable_facts": list(
            state.get(
                "durable_facts",
                [],
            )
        ),
        "recent_history": recent,
        "resume_state": dict(
            session.resume_state
            or {}
        ),
    }


def render_agent_context(
    session,
    current_instruction=None,
):
    context = build_agent_context(
        session
    )

    lines = [
        "Continue the existing Nexus session.",
        "",
        "WORKING STATE:",
        json.dumps(
            context[
                "working_state"
            ],
            ensure_ascii=False,
            indent=2,
        ),
        "",
    ]

    if context[
        "summary"
    ]:
        lines.extend(
            [
                "COMPACTED CONTEXT:",
                context[
                    "summary"
                ],
                "",
            ]
        )

    if context[
        "durable_facts"
    ]:
        lines.append(
            "DURABLE FACTS:"
        )

        for fact in context[
            "durable_facts"
        ]:
            lines.append(
                f"- {fact}"
            )

        lines.append(
            ""
        )

    lines.append(
        "RECENT HISTORY:"
    )

    for entry in context[
        "recent_history"
    ]:
        text = _entry_text(
            entry
        )

        if not text:
            continue

        lines.append(
            (
                f"{_entry_type(entry).upper()}: "
                f"{text}"
            )
        )

    if current_instruction:
        lines.extend(
            [
                "",
                "CURRENT INSTRUCTION:",
                str(
                    current_instruction
                ).strip(),
            ]
        )

    lines.extend(
        [
            "",
            (
                "Continue from the current real project "
                "state. Do not redo completed work "
                "unnecessarily."
            ),
        ]
    )

    return "\n".join(
        lines
    )
