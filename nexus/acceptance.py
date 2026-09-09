from dataclasses import dataclass, field
from pathlib import Path

import hashlib
import re


FORBIDDEN_REAL_EVIDENCE = [
    r"\bstub\b",
    r"\bstubbed\b",
    r"\bmock\b",
    r"\bmocked\b",
    r"\bplaceholder\b",
    r"\bsimulated\b",
    r"\bsimulation\b",
    r"\bfake\b",
    r"\bdry[- ]?run\b",
    r"\bnot actually\b",
    r"\bnot executed\b",
    r"\bnot run\b",
    r"\bpending\b",
    r"\bTODO\b",
    r"\bno actual\b",
]


@dataclass
class Evidence:
    description: str = ""
    command: str | None = None
    exit_code: int | None = None
    artifacts: list[str] = field(
        default_factory=list
    )
    text: str = ""


@dataclass
class Criterion:
    name: str
    requires_real_implementation: bool = False
    requires_execution: bool = False


@dataclass
class AcceptanceResult:
    passed: bool
    reason: str
    artifact_hashes: dict = field(
        default_factory=dict
    )


def _contains_forbidden(text):
    for pattern in FORBIDDEN_REAL_EVIDENCE:
        if re.search(
            pattern,
            text or "",
            re.I,
        ):
            return pattern

    return None


def sha256(path):
    h = hashlib.sha256()

    with Path(path).open("rb") as f:
        for chunk in iter(
            lambda: f.read(
                1024 * 1024
            ),
            b"",
        ):
            h.update(chunk)

    return h.hexdigest()


def verify(
    criterion,
    evidence,
):
    combined = "\n".join(
        [
            evidence.description or "",
            evidence.command or "",
            evidence.text or "",
        ]
    )

    if criterion.requires_real_implementation:
        forbidden = _contains_forbidden(
            combined
        )

        if forbidden:
            return AcceptanceResult(
                False,
                (
                    "REAL_IMPLEMENTATION_REQUIRED:"
                    f"FORBIDDEN_EVIDENCE={forbidden}"
                ),
            )

    if criterion.requires_execution:
        if not evidence.command:
            return AcceptanceResult(
                False,
                "REAL_EXECUTION_REQUIRED:NO_COMMAND",
            )

        if evidence.exit_code is None:
            return AcceptanceResult(
                False,
                "REAL_EXECUTION_REQUIRED:NO_EXIT_CODE",
            )

        if evidence.exit_code != 0:
            return AcceptanceResult(
                False,
                (
                    "REAL_EXECUTION_FAILED:"
                    f"EXIT_CODE={evidence.exit_code}"
                ),
            )

    hashes = {}

    for raw in evidence.artifacts:
        p = Path(raw).expanduser()

        if (
            not p.exists()
            or not p.is_file()
            or p.stat().st_size == 0
        ):
            return AcceptanceResult(
                False,
                f"INVALID_ARTIFACT={p}",
            )

        hashes[str(p)] = sha256(
            p
        )

    return AcceptanceResult(
        True,
        "ACCEPTANCE_EVIDENCE_VALID",
        hashes,
    )


def guard_final_answer(text):
    if not text:
        return text

    claims_pass = bool(
        re.search(
            r"\bPASS\b",
            text,
            re.I,
        )
    )

    if not claims_pass:
        return text

    forbidden = _contains_forbidden(
        text
    )

    if not forbidden:
        return text

    return (
        "NEXUS_ACCEPTANCE_OVERRIDE=FAIL\n"
        "MODEL_PASS_REJECTED=YES\n"
        "REASON=PASS report contains evidence "
        "incompatible with real acceptance: "
        f"{forbidden}\n\n"
        "ORIGINAL_MODEL_REPORT:\n"
        + text
    )
