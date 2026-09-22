from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import hashlib
import json
import re


@dataclass(
    frozen=True,
    slots=True,
)
class PromptComplexity:
    chars: int
    words: int
    lines: int
    nonempty_lines: int
    headings: int
    numbered_items: int
    bullet_items: int
    imperative_signals: int
    final_markers: int
    score: int
    milestone_mode: bool
    reasons: tuple[str, ...]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "chars": self.chars,
            "words": self.words,
            "lines": self.lines,
            "nonempty_lines":
                self.nonempty_lines,
            "headings":
                self.headings,
            "numbered_items":
                self.numbered_items,
            "bullet_items":
                self.bullet_items,
            "imperative_signals":
                self.imperative_signals,
            "final_markers":
                self.final_markers,
            "score":
                self.score,
            "milestone_mode":
                self.milestone_mode,
            "reasons":
                list(self.reasons),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class Milestone:
    id: str
    title: str
    objective: str
    requirements: tuple[str, ...]
    restrictions: tuple[str, ...]
    dependencies: tuple[str, ...]
    evidence_required: tuple[str, ...]
    completion_definition: tuple[str, ...]
    mutation_policy: str = "UNSURE"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "id": self.id,
            "title": self.title,
            "objective": self.objective,
            "requirements":
                list(self.requirements),
            "restrictions":
                list(self.restrictions),
            "dependencies":
                list(self.dependencies),
            "evidence_required":
                list(self.evidence_required),
            "completion_definition":
                list(
                    self.completion_definition
                ),
            "mutation_policy":
                self.mutation_policy,
        }


@dataclass(
    frozen=True,
    slots=True,
)
class MilestonePlan:
    master_prompt_sha256: str
    master_prompt: str
    milestones: tuple[Milestone, ...]
    global_restrictions: tuple[str, ...]
    final_completion_definition: tuple[str, ...]

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "master_prompt_sha256":
                self.master_prompt_sha256,
            "master_prompt":
                self.master_prompt,
            "milestones": [
                item.to_dict()
                for item in self.milestones
            ],
            "global_restrictions":
                list(
                    self.global_restrictions
                ),
            "final_completion_definition":
                list(
                    self.final_completion_definition
                ),
        }


_IMPERATIVE_WORDS = (
    "inspect",
    "determine",
    "identify",
    "verify",
    "map",
    "produce",
    "implement",
    "create",
    "build",
    "modify",
    "audit",
    "classify",
    "reconstruct",
    "answer",
    "include",
    "separate",
    "provide",
    "finish",
    "do not",
    "never",
    "required",
)


def analyze_prompt_complexity(
    prompt: str,
) -> PromptComplexity:
    text = str(prompt)
    lower = text.lower()

    lines = text.splitlines()
    nonempty = [
        line
        for line in lines
        if line.strip()
    ]

    headings = sum(
        1
        for line in nonempty
        if (
            re.match(
                r"^\s*#{1,6}\s+",
                line,
            )
            or re.match(
                r"^\s*=+.*=+\s*$",
                line,
            )
            or (
                len(line.strip()) >= 4
                and line.strip().isupper()
            )
        )
    )

    numbered = sum(
        1
        for line in nonempty
        if re.match(
            r"^\s*\d+[.)]\s+",
            line,
        )
    )

    bullets = sum(
        1
        for line in nonempty
        if re.match(
            r"^\s*[-*]\s+",
            line,
        )
    )

    imperative = sum(
        lower.count(word)
        for word in _IMPERATIVE_WORDS
    )

    final_markers = len(
        re.findall(
            r"\b[A-Z][A-Z0-9_]{3,}"
            r"\s*=\s*"
            r"(?:PASS|NO|YES|READY|DEFINED)",
            text,
        )
    )

    chars = len(text)
    words = len(
        re.findall(
            r"\S+",
            text,
        )
    )

    score = 0
    reasons = []

    if chars >= 6000:
        score += 5
        reasons.append(
            "chars>=6000"
        )
    elif chars >= 3000:
        score += 3
        reasons.append(
            "chars>=3000"
        )
    elif chars >= 1800:
        score += 1
        reasons.append(
            "chars>=1800"
        )

    if len(nonempty) >= 80:
        score += 4
        reasons.append(
            "nonempty_lines>=80"
        )
    elif len(nonempty) >= 40:
        score += 2
        reasons.append(
            "nonempty_lines>=40"
        )

    if headings >= 8:
        score += 4
        reasons.append(
            "headings>=8"
        )
    elif headings >= 4:
        score += 2
        reasons.append(
            "headings>=4"
        )

    if numbered >= 10:
        score += 3
        reasons.append(
            "numbered_items>=10"
        )
    elif numbered >= 5:
        score += 1
        reasons.append(
            "numbered_items>=5"
        )

    if bullets >= 20:
        score += 3
        reasons.append(
            "bullet_items>=20"
        )
    elif bullets >= 10:
        score += 1
        reasons.append(
            "bullet_items>=10"
        )

    if imperative >= 25:
        score += 3
        reasons.append(
            "imperative_signals>=25"
        )
    elif imperative >= 12:
        score += 1
        reasons.append(
            "imperative_signals>=12"
        )

    if final_markers >= 5:
        score += 2
        reasons.append(
            "final_markers>=5"
        )

    milestone_mode = (
        score >= 6
        or chars >= 9000
        or (
            headings >= 6
            and numbered >= 6
        )
    )

    return PromptComplexity(
        chars=chars,
        words=words,
        lines=len(lines),
        nonempty_lines=len(nonempty),
        headings=headings,
        numbered_items=numbered,
        bullet_items=bullets,
        imperative_signals=imperative,
        final_markers=final_markers,
        score=score,
        milestone_mode=milestone_mode,
        reasons=tuple(reasons),
    )


def master_prompt_hash(
    prompt: str,
) -> str:
    return hashlib.sha256(
        prompt.encode(
            "utf-8"
        )
    ).hexdigest()


def validate_milestone_plan(
    *,
    prompt: str,
    payload: dict[str, Any],
) -> list[str]:
    errors = []

    milestones = payload.get(
        "milestones"
    )

    if not isinstance(
        milestones,
        list,
    ):
        return [
            "milestones must be a list"
        ]

    if not milestones:
        errors.append(
            "milestones must not be empty"
        )

    if len(milestones) > 20:
        errors.append(
            "too many milestones"
        )

    seen = set()

    for index, milestone in enumerate(
        milestones,
        start=1,
    ):
        if not isinstance(
            milestone,
            dict,
        ):
            errors.append(
                f"milestone {index} "
                "must be an object"
            )
            continue

        for field in (
            "id",
            "title",
            "objective",
            "requirements",
            "restrictions",
            "dependencies",
            "evidence_required",
            "completion_definition",
            "mutation_policy",
        ):
            if field not in milestone:
                errors.append(
                    f"milestone {index} "
                    f"missing {field}"
                )

        mid = milestone.get(
            "id"
        )

        if isinstance(
            mid,
            str,
        ):
            if mid in seen:
                errors.append(
                    "duplicate milestone id: "
                    + mid
                )
            seen.add(mid)

        for field in (
            "requirements",
            "restrictions",
            "dependencies",
            "evidence_required",
            "completion_definition",
        ):
            value = milestone.get(
                field
            )

            if (
                value is not None
                and not isinstance(
                    value,
                    list,
                )
            ):
                errors.append(
                    f"milestone {index} "
                    f"{field} must be a list"
                )

    for index, milestone in enumerate(
        milestones,
        start=1,
    ):
        if not isinstance(
            milestone,
            dict,
        ):
            continue

        policy = str(
            milestone.get(
                "mutation_policy",
                "",
            )
            or ""
        ).strip().upper()

        if policy not in {
            "READ_ONLY",
            "MUTATING",
            "UNSURE",
        }:
            errors.append(
                f"milestone {index} "
                "mutation_policy must be "
                "READ_ONLY, MUTATING, or UNSURE"
            )

    expected_hash = (
        master_prompt_hash(
            prompt
        )
    )

    actual_hash = payload.get(
        "master_prompt_sha256"
    )

    if actual_hash != expected_hash:
        errors.append(
            "master prompt hash mismatch"
        )

    return errors


def milestone_execution_prompt(
    *,
    plan: MilestonePlan,
    index: int,
) -> str:
    milestone = (
        plan.milestones[
            index
        ]
    )

    return (
        "NEXUS MASTER PROMPT MILESTONE MODE\n\n"
        "MASTER_PROMPT_SHA256="
        + plan.master_prompt_sha256
        + "\n\n"
        "CURRENT_MILESTONE="
        + milestone.id
        + "\n"
        "TITLE="
        + milestone.title
        + "\n\n"
        "OBJECTIVE:\n"
        + milestone.objective
        + "\n\n"
        "REQUIREMENTS:\n"
        + json.dumps(
            list(
                milestone.requirements
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "MILESTONE_RESTRICTIONS:\n"
        + json.dumps(
            list(
                milestone.restrictions
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "GLOBAL_RESTRICTIONS:\n"
        + json.dumps(
            list(
                plan.global_restrictions
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "DEPENDENCIES:\n"
        + json.dumps(
            list(
                milestone.dependencies
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "EVIDENCE_REQUIRED:\n"
        + json.dumps(
            list(
                milestone.evidence_required
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "COMPLETION_DEFINITION:\n"
        + json.dumps(
            list(
                milestone.completion_definition
            ),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "Execute ONLY this milestone. "
        "Do not silently execute later milestones. "
        "All global restrictions remain binding."
    )


def milestone_compiler_system_prompt() -> str:
    return """
You are the Nexus Master Prompt Milestone Compiler.

You do NOT execute the user's task.
Your job is to transform one large master request into a
small ordered sequence of semantically complete milestones.
The original user request is authoritative.

CRITICAL RULES:
1. Preserve every explicit requirement.
2. Preserve every explicit restriction.
3. Preserve every requested evidence requirement.
4. Preserve final success markers.
5. Do not invent project facts.
6. Do not silently remove difficult requirements.
7. Do not turn restrictions into optional guidance.
8. Each milestone must be independently understandable.
9. Dependencies must be explicit.
10. A later milestone must not be executed early.
11. Prefer 3-8 milestones.
12. Use more only when genuinely required.
13. Keep read-only discovery separate from mutation.
14. Keep destructive work behind prerequisite evidence.
15. Keep runtime QA after implementation.
16. Keep visual QA after visual implementation.
17. The final milestone should verify the master request's
    overall completion when appropriate.

MUTATION POLICY CONTRACT:
Every milestone object MUST contain "mutation_policy".
Its value MUST be exactly one of:
"READ_ONLY", "MUTATING", or "UNSURE".

READ_ONLY means the milestone itself needs only observation,
reading, inspection, reasoning, or reporting and does not
require commands, tests, file changes, delegation, or another
capability blocked by READ_ONLY mode.

MUTATING means completing the milestone requires creating,
editing, deleting, repairing, executing commands or tests,
running programs, delegating work, or otherwise using a tool
that READ_ONLY mode blocks.

UNSURE is permitted only when the milestone genuinely cannot
be classified. Runtime treats UNSURE as READ_ONLY.

Global boundary restrictions do NOT determine milestone
mutation policy. Restrictions such as "do not modify Nexus",
"do not modify BunkerGame", "do not write outside workspace",
or "respect READ-ONLY milestones" constrain scope but must
not turn an otherwise MUTATING milestone into READ_ONLY.

Classify every milestone independently.

Return exactly one JSON object with:
{
  "master_prompt_sha256": "string",
  "milestones": [
    {
      "id": "M1",
      "title": "string",
      "objective": "string",
      "requirements": ["string"],
      "restrictions": ["string"],
      "dependencies": ["string"],
      "evidence_required": ["string"],
      "completion_definition": ["string"],
      "mutation_policy": "READ_ONLY | MUTATING | UNSURE"
    }
  ],
  "global_restrictions": ["string"],
  "final_completion_definition": ["string"]
}
""".strip()


def milestone_compiler_messages(
    *,
    prompt: str,
) -> list[dict[str, str]]:
    digest = master_prompt_hash(
        prompt
    )

    return [
        {
            "role": "system",
            "content":
                milestone_compiler_system_prompt(),
        },
        {
            "role": "user",
            "content": (
                "MASTER_PROMPT_SHA256="
                + digest
                + "\n\n"
                + "MASTER REQUEST:\n"
                + prompt
            ),
        },
    ]


def milestone_plan_from_payload(
    *,
    prompt: str,
    payload: dict[str, Any],
) -> MilestonePlan:
    payload = normalize_milestone_payload(
        payload
    )

    errors = validate_milestone_plan(
        prompt=prompt,
        payload=payload,
    )

    if errors:
        raise ValueError(
            "INVALID_MILESTONE_PLAN: "
            + "; ".join(errors)
        )

    milestones = tuple(
        Milestone(
            id=str(item["id"]),
            title=str(
                item["title"]
            ),
            objective=str(
                item["objective"]
            ),
            requirements=tuple(
                str(value)
                for value
                in item[
                    "requirements"
                ]
            ),
            restrictions=tuple(
                str(value)
                for value
                in item[
                    "restrictions"
                ]
            ),
            dependencies=tuple(
                str(value)
                for value
                in item[
                    "dependencies"
                ]
            ),
            evidence_required=tuple(
                str(value)
                for value
                in item[
                    "evidence_required"
                ]
            ),
            completion_definition=tuple(
                str(value)
                for value
                in item[
                    "completion_definition"
                ]
            ),
                    mutation_policy=str(
                item[
                    "mutation_policy"
                ]
            ).strip().upper(),
)
        for item in payload[
            "milestones"
        ]
    )

    return MilestonePlan(
        master_prompt_sha256=(
            master_prompt_hash(
                prompt
            )
        ),
        master_prompt=prompt,
        milestones=milestones,
        global_restrictions=tuple(
            str(value)
            for value
            in payload.get(
                "global_restrictions",
                [],
            )
        ),
        final_completion_definition=tuple(
            str(value)
            for value
            in payload.get(
                "final_completion_definition",
                [],
            )
        ),
    )


# NEXUS700_MILESTONE_NORMALIZER_V1
_MILESTONE_LIST_FIELDS = (
    "requirements",
    "restrictions",
    "dependencies",
    "evidence_required",
    "completion_definition",
)


def _normalize_string_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if isinstance(value, str):
        value = value.strip()

        if not value:
            return []

        return [value]

    if isinstance(value, (list, tuple)):
        result = []

        for item in value:
            if item is None:
                continue

            text = str(item).strip()

            if text:
                result.append(text)

        return result

    return [str(value).strip()]


def normalize_milestone_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    if not isinstance(payload, dict):
        return payload

    result = dict(payload)

    milestones = result.get(
        "milestones"
    )

    if isinstance(milestones, list):
        normalized = []

        for item in milestones:
            if not isinstance(item, dict):
                normalized.append(item)
                continue

            current = dict(item)

            for field in _MILESTONE_LIST_FIELDS:
                if field in current:
                    current[field] = (
                        _normalize_string_list(
                            current[field]
                        )
                    )

            normalized.append(current)

        result["milestones"] = normalized

    for field in (
        "global_restrictions",
        "final_completion_definition",
    ):
        if field in result:
            result[field] = (
                _normalize_string_list(
                    result[field]
                )
            )

    return result


def milestone_validation_errors(
    *,
    prompt: str,
    payload: dict[str, Any],
) -> list[str]:
    normalized = (
        normalize_milestone_payload(
            payload
        )
    )

    return validate_milestone_plan(
        prompt=prompt,
        payload=normalized,
    )


def milestone_repair_messages(
    *,
    prompt: str,
    payload: dict[str, Any],
    errors: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                milestone_compiler_system_prompt()
                + "\n\n"
                + "SCHEMA REPAIR MODE.\n"
                + "Return the COMPLETE corrected JSON object.\n"
                + "Do not omit milestones.\n"
                + "Do not change the user's intent.\n"
                + "Preserve all restrictions.\n"
                + "All requirements, restrictions, dependencies, "
                + "evidence_required and completion_definition "
                + "fields MUST be JSON arrays of strings.\n"
                + "global_restrictions and "
                + "final_completion_definition MUST also be "
                + "JSON arrays of strings.\n"
                + "Do not add commentary outside the JSON."
            ),
        },
        {
            "role": "user",
            "content": (
                "MASTER REQUEST:\n"
                + prompt
                + "\n\nCURRENT PAYLOAD:\n"
                + json.dumps(
                    payload,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n\nVALIDATION ERRORS:\n"
                + json.dumps(
                    errors,
                    ensure_ascii=False,
                    indent=2,
                )
            ),
        },
    ]


# NEXUS700_TURN_CHECKLIST_EXECUTION_PROTOCOL_V1

MILESTONE_EXECUTION_PROTOCOL = (
    "NEXUS_MILESTONE_EXECUTION_V1"
)


def turn_checklist_execution_prompt(
    *,
    plan,
    index,
):
    """
    Convert one already-planned milestone into a standalone
    Director execution prompt.

    This prompt is an execution protocol, not a new user
    request. Agent.run must bypass Understanding and Planner
    when this canonical prefix is present.
    """

    if index < 0 or index >= len(plan.milestones):
        raise IndexError(
            "MILESTONE_INDEX_OUT_OF_RANGE"
        )

    milestone = plan.milestones[index]

    base = milestone_execution_prompt(
        plan=plan,
        index=index,
    )

    position = (
        str(index + 1)
        + " of "
        + str(len(plan.milestones))
    )

    return (
        MILESTONE_EXECUTION_PROTOCOL
        + "\n"
        + "TURN_CHECKLIST_EXECUTION=YES\n"
        + "MILESTONE_POSITION="
        + position
        + "\n\n"
        + base
        + "\n\n"
        + "MASTER CONTEXT:\n"
        + "- This is milestone "
        + str(milestone.id)
        + " ("
        + position
        + ").\n"
        + "- Execute only this milestone.\n"
        + "- Do not execute later milestones.\n"
        + "- Completion applies only to this milestone.\n"
        + "- Do not declare the master turn complete.\n"
    )


def is_turn_checklist_execution_prompt(
    task,
):
    return (
        isinstance(task, str)
        and task.startswith(
            MILESTONE_EXECUTION_PROTOCOL
            + "\n"
        )
    )


# NEXUS700_TURN_CHECKLIST_ACTIVATION_V1

def should_activate_turn_checklist(
    prompt: str,
) -> bool:
    """
    Decide whether one user turn should be compiled into
    the persistent Turn Checklist.

    This is intentionally separate from the legacy large-prompt
    complexity score. Explicit master prompts and clearly
    structured multi-step requests should not need thousands
    of characters to receive milestone orchestration.
    """

    text = str(prompt or "")
    stripped = text.strip()

    if not stripped:
        return False

    complexity = analyze_prompt_complexity(
        stripped
    )

    # Preserve the existing high-complexity path exactly.
    if complexity.milestone_mode:
        return True

    lower = stripped.lower()

    # Explicit opt-in is authoritative.
    # Explicit user opt-in. Keep this deliberately simple:
    # support multiline and one-line forms without relying on
    # list formatting or the legacy complexity threshold.
    explicit_text = stripped.lstrip()

    while explicit_text.startswith("#"):
        explicit_text = (
            explicit_text[1:]
            .lstrip()
        )

    explicit_upper = explicit_text.upper()

    explicit_master = False

    for marker in (
        "MASTER PROMPT",
        "MASTER REQUEST",
        "MILESTONE MODE",
    ):
        if not explicit_upper.startswith(marker):
            continue

        remainder = explicit_text[
            len(marker):
        ]

        if (
            not remainder
            or remainder[0].isspace()
            or remainder[0]
            in ":;-–—"
        ):
            explicit_master = True
            break

    if explicit_master:
        return True

    # A genuinely structured request with at least three
    # concrete list items is a multi-stage turn even when short.
    structured_items = (
        complexity.numbered_items
        + complexity.bullet_items
    )

    if structured_items >= 3:
        return True

    # Strong execution-order language plus multiple explicit
    # items also counts as a master turn.
    ordered_language = any(
        phrase in lower
        for phrase in (
            "execute every",
            "complete every",
            "all stages",
            "all steps",
            "in order",
            "do not stop after",
            "do not declare",
        )
    )

    if (
        structured_items >= 2
        and ordered_language
    ):
        return True

    return False

# Canonical protocol for the final gate of a persisted
# Turn Checklist. This is not a new master request.
FINAL_VERIFICATION_PROTOCOL = (
    "NEXUS_FINAL_VERIFICATION_V1"
)


def final_verification_execution_prompt(
    verification_prompt,
    *,
    mutation_policy="NORMAL",
    restrictions=(),
):
    """
    Mark an already-planned master turn's final verification
    as a canonical execution protocol.

    mutation_policy and restrictions are semantic metadata
    derived from the persisted plan. Runtime capability
    enforcement remains independently authoritative.
    """
    normalized_policy = (
        str(mutation_policy or "NORMAL")
        .strip()
        .upper()
    )

    normalized_restrictions = [
        str(value)
        for value in restrictions
    ]

    return (
        FINAL_VERIFICATION_PROTOCOL
        + "\n"
        + "TURN_CHECKLIST_FINAL_VERIFICATION=YES\n"
        + "MUTATION_POLICY="
        + normalized_policy
        + "\n"
        + "FINAL_RESTRICTIONS:\n"
        + json.dumps(
            normalized_restrictions,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        + str(verification_prompt)
    )


def is_final_verification_prompt(
    task,
):
    return (
        isinstance(task, str)
        and task.startswith(
            FINAL_VERIFICATION_PROTOCOL
            + "\n"
        )
    )



# NEXUS700_PREPLANNED_SEMANTIC_VIEW_V1
#
# Understanding should reason about the semantic task contract,
# not about execution-protocol control text. The Director still
# receives the original canonical execution prompt unchanged.
def preplanned_understanding_prompt(
    task,
):
    if not isinstance(task, str):
        return task

    if is_turn_checklist_execution_prompt(
        task
    ):
        return _milestone_understanding_view(
            task
        )

    if is_final_verification_prompt(
        task
    ):
        return _final_understanding_view(
            task
        )

    return task


def _extract_protocol_section(
    text,
    label,
    *,
    next_labels,
):
    marker = label + ":\n"

    start = text.find(marker)

    if start < 0:
        return ""

    start += len(marker)

    ends = []

    for next_label in next_labels:
        candidate = text.find(
            "\n\n"
            + next_label
            + ":\n",
            start,
        )

        if candidate >= 0:
            ends.append(candidate)

    end = (
        min(ends)
        if ends
        else len(text)
    )

    return text[
        start:end
    ].strip()


def _protocol_scalar(
    text,
    key,
):
    prefix = key + "="

    for line in text.splitlines():
        if line.startswith(prefix):
            return line[
                len(prefix):
            ].strip()

    return ""


def _json_protocol_list(
    text,
    label,
    *,
    next_labels,
):
    raw = _extract_protocol_section(
        text,
        label,
        next_labels=next_labels,
    )

    if not raw:
        return []

    try:
        value = json.loads(raw)
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return []

    if not isinstance(value, list):
        return []

    return [
        str(item)
        for item in value
    ]


def _render_semantic_list(
    title,
    values,
):
    lines = [
        title + ":"
    ]

    if not values:
        lines.append("- None")
    else:
        lines.extend(
            "- " + str(value)
            for value in values
        )

    return "\n".join(lines)


def _milestone_understanding_view(
    task,
):
    labels = (
        "OBJECTIVE",
        "REQUIREMENTS",
        "MILESTONE_RESTRICTIONS",
        "GLOBAL_RESTRICTIONS",
        "DEPENDENCIES",
        "EVIDENCE_REQUIRED",
        "COMPLETION_DEFINITION",
    )

    objective = _extract_protocol_section(
        task,
        "OBJECTIVE",
        next_labels=labels[1:],
    )

    requirements = _json_protocol_list(
        task,
        "REQUIREMENTS",
        next_labels=labels[2:],
    )

    milestone_restrictions = (
        _json_protocol_list(
            task,
            "MILESTONE_RESTRICTIONS",
            next_labels=labels[3:],
        )
    )

    global_restrictions = (
        _json_protocol_list(
            task,
            "GLOBAL_RESTRICTIONS",
            next_labels=labels[4:],
        )
    )

    dependencies = _json_protocol_list(
        task,
        "DEPENDENCIES",
        next_labels=labels[5:],
    )

    evidence = _json_protocol_list(
        task,
        "EVIDENCE_REQUIRED",
        next_labels=labels[6:],
    )

    completion = _json_protocol_list(
        task,
        "COMPLETION_DEFINITION",
        next_labels=(),
    )

    # milestone_execution_prompt appends one execution-control
    # sentence after the JSON completion list. Keep only the JSON
    # array when possible.
    if completion:
        pass
    else:
        raw_completion = (
            _extract_protocol_section(
                task,
                "COMPLETION_DEFINITION",
                next_labels=(),
            )
        )

        decoder = json.JSONDecoder()

        try:
            decoded, _ = decoder.raw_decode(
                raw_completion
            )
        except (
            json.JSONDecodeError,
            TypeError,
        ):
            decoded = []

        if isinstance(decoded, list):
            completion = [
                str(item)
                for item in decoded
            ]

    milestone_id = _protocol_scalar(
        task,
        "CURRENT_MILESTONE",
    )

    title = _protocol_scalar(
        task,
        "TITLE",
    )

    position = _protocol_scalar(
        task,
        "MILESTONE_POSITION",
    )

    restrictions = []

    for value in (
        milestone_restrictions
        + global_restrictions
    ):
        if value not in restrictions:
            restrictions.append(value)

    parts = [
        "NEXUS PREPLANNED SEMANTIC INPUT",
        "EXECUTION_KIND=MILESTONE",
        "MILESTONE_ID=" + milestone_id,
        "MILESTONE_POSITION=" + position,
        "TITLE=" + title,
        "",
        "OBJECTIVE:",
        objective,
        "",
        _render_semantic_list(
            "REQUIREMENTS",
            requirements,
        ),
        "",
        _render_semantic_list(
            "RESTRICTIONS",
            restrictions,
        ),
        "",
        _render_semantic_list(
            "DEPENDENCIES",
            dependencies,
        ),
        "",
        _render_semantic_list(
            "EVIDENCE_REQUIRED",
            evidence,
        ),
        "",
        _render_semantic_list(
            "COMPLETION_DEFINITION",
            completion,
        ),
        "",
        (
            "Interpret the objective above as the actual "
            "goal for this execution unit. Restrictions are "
            "binding. Do not treat protocol or orchestration "
            "instructions as user goals."
        ),
    ]

    return "\n".join(parts).strip()


def _final_understanding_view(
    task,
):
    mutation_policy = _protocol_scalar(
        task,
        "MUTATION_POLICY",
    )

    raw_restrictions = _protocol_json_field(
        task,
        "FINAL_RESTRICTIONS",
    )

    restrictions = (
        [
            str(value)
            for value in raw_restrictions
        ]
        if isinstance(
            raw_restrictions,
            list,
        )
        else []
    )

    master = _extract_protocol_section(
        task,
        "MASTER PROMPT",
        next_labels=(
            "FINAL COMPLETION DEFINITION",
        ),
    )

    completion = _extract_protocol_section(
        task,
        "FINAL COMPLETION DEFINITION",
        next_labels=(),
    )

    control = (
        "Do not redo completed milestones. "
        "Verify whether the master request as a whole "
        "meets its final completion definition."
    )

    if completion.endswith(control):
        completion = completion[
            :-len(control)
        ].rstrip()

    return (
        "NEXUS PREPLANNED SEMANTIC INPUT\n"
        "EXECUTION_KIND=FINAL_VERIFICATION\n"
        "MUTATION_POLICY="
        + (
            mutation_policy
            or "NORMAL"
        )
        + "\n\n"
        "ACTUAL_GOAL:\n"
        "Verify whether the already-completed master request "
        "satisfies its final completion definition.\n\n"
        + _render_semantic_list(
            "RESTRICTIONS",
            restrictions,
        )
        + "\n\n"
        "MASTER_REQUEST:\n"
        + master
        + "\n\n"
        "FINAL_COMPLETION_DEFINITION:\n"
        + completion
        + "\n\n"
        "The MUTATION_POLICY field above is authoritative. "
        "Restrictions are binding. Do not reinterpret "
        "execution-protocol control text as the user's goal."
    ).strip()



# NEXUS700_PROTOCOL_JSON_FIELD_V1
#
# Decode one JSON value immediately following a protocol field.
# Unlike section-label extraction, this does not require the next
# protocol marker to use LABEL: syntax.
def _protocol_json_field(
    text,
    label,
):
    marker = label + ":\n"

    start = text.find(marker)

    if start < 0:
        return None

    payload = text[
        start + len(marker):
    ].lstrip()

    decoder = json.JSONDecoder()

    try:
        value, _ = decoder.raw_decode(
            payload
        )
    except (
        json.JSONDecodeError,
        TypeError,
    ):
        return None

    return value


def milestone_requires_normal_capability(
    milestone: Milestone,
) -> bool:
    """
    Determine whether the milestone contract explicitly requires
    capability unavailable in READ_ONLY mode.

    This is intentionally one-way authorization reconciliation:
    it may escalate READ_ONLY/UNSURE to MUTATING when the compiled
    milestone itself requires execution or mutation. It never
    downgrades MUTATING and never uses global restrictions as
    authorization signals.
    """
    text = "\n".join(
        (
            str(milestone.title),
            str(milestone.objective),
            *(
                str(value)
                for value in milestone.requirements
            ),
            *(
                str(value)
                for value in milestone.evidence_required
            ),
            *(
                str(value)
                for value
                in milestone.completion_definition
            ),
        )
    ).lower()

    phrases = (
        "create ",
        "implement ",
        "add runnable",
        "add ",
        "write ",
        "edit ",
        "modify ",
        "update ",
        "delete ",
        "remove ",
        "repair ",
        "fix ",
        "generate ",
        "install ",
        "execute ",
        "run ",
        "run the ",
        "run full",
        "run tests",
        "run the tests",
        "run the complete test",
        "run the full",
        "test suite",
        "unittest",
        "pytest",
        "exercise the cli",
        "exercise ",
        "invoke the cli",
        "separate processes",
        "separate process",
        "process executions",
        "command-line",
        "command line",
        "cli acceptance",
        "delegat",
    )

    return any(
        phrase in text
        for phrase in phrases
    )


def reconcile_milestone_mutation_policies(
    plan: MilestonePlan,
) -> MilestonePlan:
    """
    Reconcile compiler policy with explicit milestone capability
    requirements.

    MUTATING is preserved. READ_ONLY/UNSURE are escalated only
    when the milestone's own semantic contract requires NORMAL
    execution capability.
    """
    reconciled = []

    for milestone in plan.milestones:
        policy = str(
            milestone.mutation_policy
            or "UNSURE"
        ).strip().upper()

        if (
            policy != "MUTATING"
            and milestone_requires_normal_capability(
                milestone
            )
        ):
            policy = "MUTATING"

        reconciled.append(
            Milestone(
                id=milestone.id,
                title=milestone.title,
                objective=milestone.objective,
                requirements=milestone.requirements,
                restrictions=milestone.restrictions,
                dependencies=milestone.dependencies,
                evidence_required=milestone.evidence_required,
                completion_definition=(
                    milestone.completion_definition
                ),
                mutation_policy=policy,
            )
        )

    return MilestonePlan(
        master_prompt_sha256=(
            plan.master_prompt_sha256
        ),
        master_prompt=plan.master_prompt,
        milestones=tuple(reconciled),
        global_restrictions=(
            plan.global_restrictions
        ),
        final_completion_definition=(
            plan.final_completion_definition
        ),
    )
