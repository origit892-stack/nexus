from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import re


@dataclass(
    frozen=True,
    slots=True,
)
class EvidenceRequirements:
    artifact: bool = False
    tests: bool = False
    integration: bool = False
    studio: bool = False
    runtime: bool = False
    visual: bool = False

    def required_names(
        self,
    ) -> tuple[str, ...]:
        result = []

        if self.artifact:
            result.append(
                "artifact"
            )

        if self.tests:
            result.append(
                "tests"
            )

        if self.integration:
            result.append(
                "integration"
            )

        if self.studio:
            result.append(
                "studio"
            )

        if self.runtime:
            result.append(
                "runtime"
            )

        if self.visual:
            result.append(
                "visual"
            )

        return tuple(result)


@dataclass(
    frozen=True,
    slots=True,
)
class CompletionEvidenceDecision:
    complete: bool
    status: str
    required: tuple[str, ...]
    satisfied: tuple[str, ...]
    missing: tuple[str, ...]
    reason: str

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "complete":
                self.complete,

            "status":
                self.status,

            "required":
                list(
                    self.required
                ),

            "satisfied":
                list(
                    self.satisfied
                ),

            "missing":
                list(
                    self.missing
                ),

            "reason":
                self.reason,
        }


_ROBLOX_WORDS = (
    "roblox",
    "studio",
    "workspace",
    "serverstorage",
    "replicatedstorage",
    "startergui",
    "starterplayer",
    "terrain",
    "meshpart",
    "proximityprompt",
    "luau",
    "rojo",
)


_MUTATION_WORDS = (
    "implement",
    "create",
    "build",
    "add",
    "change",
    "modify",
    "fix",
    "remove",
    "delete",
    "move",
    "place",
    "spawn",
    "arrange",
    "position",
    "update",
    "replace",
    "rework",
    "redesign",
    "integrate",
)


_RUNTIME_WORDS = (
    "gameplay",
    "playtest",
    "play test",
    "runtime",
    "interaction",
    "interact",
    "prompt",
    "damage",
    "stamina",
    "inventory",
    "harvest",
    "sprint",
    "respawn",
    "enemy",
    "zombie",
    "movement",
)


_VISUAL_WORDS = (
    "visual",
    "look",
    "appearance",
    "lighting",
    "material",
    "texture",
    "ui",
    "hud",
    "layout",
    "position",
    "arrange",
    "environment",
    "scene",
    "beautiful",
    "polish",
)


_TEST_WORDS = (
    "test",
    "tests",
    "pytest",
    "regression",
    "compile",
    "qa",
    "validate",
    "verification",
)


def _contains_any(
    text: str,
    words: tuple[str, ...],
) -> bool:
    return any(
        word in text
        for word in words
    )


def infer_evidence_requirements(
    *,
    task: str,
    understanding: dict[str, Any] | None = None,
    plan: Any = None,
) -> EvidenceRequirements:
    parts = [
        str(task),
    ]

    if understanding:
        for key in (
            "user_goal",
            "desired_end_state",
            "explicit_requests",
            "recommended_plan",
            "completion_definition",
            "evidence_required",
        ):
            if key in understanding:
                parts.append(
                    str(
                        understanding[
                            key
                        ]
                    )
                )

    if plan is not None:
        parts.append(
            str(plan)
        )

    text = " ".join(
        parts
    ).lower()

    roblox = _contains_any(
        text,
        _ROBLOX_WORDS,
    )

    mutation = _contains_any(
        text,
        _MUTATION_WORDS,
    )

    runtime = (
        roblox
        and mutation
        and _contains_any(
            text,
            _RUNTIME_WORDS,
        )
    )

    visual = (
        roblox
        and mutation
        and _contains_any(
            text,
            _VISUAL_WORDS,
        )
    )

    tests = (
        mutation
        and _contains_any(
            text,
            _TEST_WORDS,
        )
    )

    studio = (
        roblox
        and mutation
    )

    integration = (
        mutation
        and (
            roblox
            or "integrat" in text
            or "deploy" in text
            or "sync" in text
        )
    )

    artifact = mutation

    return EvidenceRequirements(
        artifact=artifact,
        tests=tests,
        integration=integration,
        studio=studio,
        runtime=runtime,
        visual=visual,
    )


_TRUE_MARKERS = (
    "=PASS",
    "=YES",
    "=TRUE",
    " verified",
    " verification passed",
    " successfully verified",
)


def _evidence_text(
    evidence: Any,
) -> str:
    if evidence is None:
        return ""

    if isinstance(
        evidence,
        str,
    ):
        return evidence

    return str(evidence)


def _marker_satisfied(
    *,
    name: str,
    evidence: Any,
) -> bool:
    if isinstance(
        evidence,
        dict,
    ):
        direct_keys = (
            name,
            name + "_verified",
            name + "_verification",
        )

        for key in direct_keys:
            value = evidence.get(
                key
            )

            if value is True:
                return True

            if isinstance(
                value,
                str,
            ) and value.upper() in (
                "PASS",
                "YES",
                "TRUE",
                "VERIFIED",
            ):
                return True

    text = (
        _evidence_text(
            evidence
        )
        .lower()
    )

    patterns = {
        "artifact": (
            "artifact=pass",
            "implementation=pass",
            "source_mutation=pass",
            "file_write=pass",
        ),

        "tests": (
            "tests=pass",
            "regression=pass",
            "compile=pass",
            "qa=pass",
        ),

        "integration": (
            "integration=pass",
            "integration_verified=pass",
            "rojo_persistence=pass",
            "sync=pass",
        ),

        "studio": (
            "studio_verification=pass",
            "studio=pass",
            "studio_verified=yes",
        ),

        "runtime": (
            "runtime_verification=pass",
            "runtime=pass",
            "playtest=pass",
            "play_test=pass",
        ),

        "visual": (
            "visual_verification=pass",
            "visual_qa=pass",
            "visual=pass",
        ),
    }

    return any(
        marker in text
        for marker in patterns[
            name
        ]
    )


def evaluate_completion_evidence(
    *,
    requirements: EvidenceRequirements,
    evidence: Any,
) -> CompletionEvidenceDecision:
    required = (
        requirements
        .required_names()
    )

    if not required:
        return CompletionEvidenceDecision(
            complete=True,
            status="COMPLETE",
            required=(),
            satisfied=(),
            missing=(),
            reason=(
                "No external completion evidence "
                "is required for this task."
            ),
        )

    satisfied = tuple(
        name
        for name in required
        if _marker_satisfied(
            name=name,
            evidence=evidence,
        )
    )

    missing = tuple(
        name
        for name in required
        if name not in satisfied
    )

    if missing:
        return CompletionEvidenceDecision(
            complete=False,
            status=(
                "VERIFICATION_PENDING"
            ),
            required=required,
            satisfied=satisfied,
            missing=missing,
            reason=(
                "Implementation evidence does not "
                "satisfy all completion requirements."
            ),
        )

    return CompletionEvidenceDecision(
        complete=True,
        status="COMPLETE",
        required=required,
        satisfied=satisfied,
        missing=(),
        reason=(
            "All required completion evidence "
            "has been observed."
        ),
    )
