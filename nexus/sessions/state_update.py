from __future__ import annotations
import json
from dataclasses import dataclass, field
from typing import Any
STATE_UPDATE_BEGIN = "NEXUS_STATE_UPDATE"
STATE_UPDATE_END = "NEXUS_STATE_UPDATE_END"
@dataclass
class SessionStateUpdate:
    active_item: str | None = None
    completed_work: list[str] = field(default_factory=list)
    pending_work: list[str] | None = None
    add_blockers: list[str] = field(default_factory=list)
    clear_blockers: list[str] = field(default_factory=list)
    checkpoint: str | None = None
def _clean_text(value):
    if value is None: return None
    text = str(value).strip()
    return text if text else None
def _clean_list(value):
    if not isinstance(value, list): return []
    result = []
    for item in value:
        text = _clean_text(item)
        if text and text not in result: result.append(text)
    return result
def _normalize_pending(value):
    if value is None: return None
    if not isinstance(value, list): raise ValueError("STATE_UPDATE_PENDING_NOT_LIST")
    return _clean_list(value)
def parse_state_update_data(data: Any):
    if not isinstance(data, dict): raise ValueError("STATE_UPDATE_NOT_OBJECT")
    allowed = {"active_item","completed_work","pending_work","add_blockers","clear_blockers","checkpoint"}
    unknown = set(data) - allowed
    if unknown: raise ValueError("STATE_UPDATE_UNKNOWN_FIELDS:" + ",".join(sorted(unknown)))
    return SessionStateUpdate(
        active_item=_clean_text(data.get("active_item")), completed_work=_clean_list(data.get("completed_work")),
        pending_work=_normalize_pending(data.get("pending_work")), add_blockers=_clean_list(data.get("add_blockers")),
        clear_blockers=_clean_list(data.get("clear_blockers")), checkpoint=_clean_text(data.get("checkpoint")))
def _find_marker_line(
    text,
    marker,
    start=0,
):
    offset = 0

    for line in text.splitlines(
        keepends=True
    ):
        line_start = offset
        line_end = (
            offset
            + len(line)
        )

        if (
            line_start >= start
            and line.strip() == marker
        ):
            content_end = line_end

            while (
                content_end > line_start
                and text[
                    content_end - 1
                ] in "\r\n"
            ):
                content_end -= 1

            return (
                line_start,
                content_end,
                line_end,
            )

        offset = line_end

    return None


def extract_state_update(text):
    text = str(text)

    begin_match = _find_marker_line(
        text,
        STATE_UPDATE_BEGIN,
    )

    if begin_match is None:
        return None

    (
        begin_start,
        begin_content_end,
        begin_line_end,
    ) = begin_match

    end_match = _find_marker_line(
        text,
        STATE_UPDATE_END,
        start=begin_line_end,
    )

    if end_match is None:
        raise ValueError(
            "STATE_UPDATE_END_MISSING"
        )

    (
        end_start,
        end_content_end,
        end_line_end,
    ) = end_match

    second = _find_marker_line(
        text,
        STATE_UPDATE_BEGIN,
        start=end_line_end,
    )

    if second is not None:
        raise ValueError(
            "STATE_UPDATE_MULTIPLE_BLOCKS"
        )

    payload = text[
        begin_line_end:end_start
    ].strip()

    if payload.startswith(
        "```json"
    ):
        payload = payload[
            len("```json"):
        ].strip()

        if payload.endswith(
            "```"
        ):
            payload = payload[
                :-3
            ].strip()

    elif payload.startswith(
        "```"
    ):
        payload = payload[
            3:
        ].strip()

        if payload.endswith(
            "```"
        ):
            payload = payload[
                :-3
            ].strip()

    if not payload:
        raise ValueError(
            "STATE_UPDATE_EMPTY"
        )

    try:
        data = json.loads(
            payload
        )

    except json.JSONDecodeError as exc:
        raise ValueError(
            "STATE_UPDATE_INVALID_JSON"
        ) from exc

    return parse_state_update_data(
        data
    )


def strip_state_update(text):
    text = str(text)

    begin_match = _find_marker_line(
        text,
        STATE_UPDATE_BEGIN,
    )

    if begin_match is None:
        return text

    (
        begin_start,
        begin_content_end,
        begin_line_end,
    ) = begin_match

    end_match = _find_marker_line(
        text,
        STATE_UPDATE_END,
        start=begin_line_end,
    )

    if end_match is None:
        return text

    (
        end_start,
        end_content_end,
        end_line_end,
    ) = end_match

    result = (
        text[:begin_start]
        + text[end_line_end:]
    )

    return result.strip()


def apply_state_update(store, session_id, update):
    if not isinstance(update, SessionStateUpdate): raise TypeError("STATE_UPDATE_INVALID_TYPE")
    session = store.get(session_id)
    if session is None: raise KeyError(session_id)
    state = dict(session.working_state); completed = list(state.get("completed_work", [])); pending = list(state.get("pending_work", [])); blockers = list(state.get("blockers", []))
    for item in update.completed_work:
        if item not in completed: completed.append(item)
        pending = [x for x in pending if x != item]
        if state.get("active_item") == item: state["active_item"] = None
        state["last_completed_item"] = item
    if update.pending_work is not None: pending = [x for x in update.pending_work if x not in completed]
    for blocker in update.add_blockers:
        if blocker not in blockers: blockers.append(blocker)
    for blocker in update.clear_blockers: blockers = [x for x in blockers if x != blocker]
    if update.active_item is not None and update.active_item not in completed: state["active_item"] = update.active_item
    state["completed_work"] = completed; state["pending_work"] = pending; state["blockers"] = blockers
    if update.checkpoint is not None:
        try: serial = int(state.get("checkpoint_serial", 0))
        except (TypeError, ValueError): serial = 0
        state["checkpoint_serial"] = serial + 1; state["last_checkpoint"] = update.checkpoint
    session.working_state = state; store.save(session); return store.get(session_id)


def state_update_protocol_prompt():

    return """STATE UPDATE PROTOCOL:

After completing the requested work, emit exactly one machine-readable state update block at the end of your FINAL ASSISTANT RESPONSE when durable session state actually changed.

NEXUS_STATE_UPDATE

{
  "active_item": null,
  "completed_work": [],
  "pending_work": null,
  "add_blockers": [],
  "clear_blockers": [],
  "checkpoint": null
}

NEXUS_STATE_UPDATE_END

Rules:

- The block is optional only when durable session state did not change.
- If durable session state changed, the final assistant response MUST contain the block.
- The block must appear directly in the final assistant response.
- NEVER send the block through memory_add, memory tools, delegation, shell, files, acceptance tools, or any other tool.
- NEVER store the block as memory instead of returning it.
- NEVER ask another agent to return the block on your behalf.
- Output strict JSON only inside the block.
- Use only the listed fields.
- completed_work contains only work actually completed and verified in this turn.
- pending_work, when provided, replaces the current pending list.
- add_blockers contains newly discovered blockers supported by evidence.
- clear_blockers contains blockers actually resolved.
- active_item is the next currently active work item when known.
- checkpoint is a concise factual checkpoint for this successful turn when useful.
- Never claim completion, blocker resolution, or project facts without evidence from work actually performed.
- The state-update block must be the last content in the final response.
- Never emit more than one state-update block.

"""
