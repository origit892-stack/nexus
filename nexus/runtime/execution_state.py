from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from nexus.runtime.task_contract import (
    TaskContract,
)


STATUS_PENDING = "PENDING"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_DONE = "DONE"


@dataclass
class RequirementState:
    requirement: str
    status: str = STATUS_PENDING
    evidence: list[str] = field(
        default_factory=list
    )

    def add_evidence(
        self,
        evidence: str,
    ) -> None:
        text = str(evidence).strip()

        if (
            text
            and text not in self.evidence
        ):
            self.evidence.append(text)

        if self.evidence:
            self.status = (
                STATUS_IN_PROGRESS
            )

    def complete(
        self,
        evidence: str | None = None,
    ) -> None:
        if evidence is not None:
            self.add_evidence(
                evidence
            )

        self.status = STATUS_DONE


@dataclass
class ExecutionState:
    contract: TaskContract
    requirements: dict[
        str,
        RequirementState,
    ]

    @classmethod
    def create(
        cls,
        contract: TaskContract,
    ) -> "ExecutionState":
        ordered = (
            contract.must_do
            + contract.evidence_required
            + contract.done_when
        )

        requirements: dict[
            str,
            RequirementState,
        ] = {}

        for item in ordered:
            key = item.casefold()

            if key not in requirements:
                requirements[key] = (
                    RequirementState(
                        requirement=item
                    )
                )

        return cls(
            contract=contract,
            requirements=requirements,
        )

    def record_progress(
        self,
        requirement: str,
        evidence: str,
    ) -> None:
        key = requirement.casefold()

        if key not in self.requirements:
            raise KeyError(
                "Unknown task requirement: "
                + requirement
            )

        self.requirements[
            key
        ].add_evidence(
            evidence
        )

    def mark_done(
        self,
        requirement: str,
        evidence: str | None = None,
    ) -> None:
        key = requirement.casefold()

        if key not in self.requirements:
            raise KeyError(
                "Unknown task requirement: "
                + requirement
            )

        self.requirements[
            key
        ].complete(
            evidence
        )

    def apply_progress_update(
        self,
        *,
        requirement: str,
        status: str,
        evidence: str,
    ) -> None:
        key = str(
            requirement
        ).strip().casefold()

        if key not in self.requirements:
            raise KeyError(
                "Unknown task requirement: "
                + str(requirement)
            )

        normalized_status = str(
            status
        ).strip().upper()

        if normalized_status not in {
            STATUS_IN_PROGRESS,
            STATUS_DONE,
        }:
            raise ValueError(
                "Invalid progress status: "
                + normalized_status
            )

        evidence_text = str(
            evidence
        ).strip()

        if not evidence_text:
            raise ValueError(
                "Progress update requires evidence."
            )

        state = self.requirements[
            key
        ]

        if normalized_status == STATUS_DONE:
            state.complete(
                evidence_text
            )
        else:
            state.add_evidence(
                evidence_text
            )

    def incomplete(
        self,
    ) -> tuple[str, ...]:
        return tuple(
            state.requirement
            for state
            in self.requirements.values()
            if state.status != STATUS_DONE
        )

    def complete(
        self,
    ) -> bool:
        return (
            bool(self.requirements)
            and not self.incomplete()
        )

    def progress_fraction(
        self,
    ) -> float:
        total = len(
            self.requirements
        )

        if total == 0:
            return 0.0

        done = sum(
            1
            for state
            in self.requirements.values()
            if state.status == STATUS_DONE
        )

        return done / total

    def snapshot(
        self,
    ) -> dict[str, Any]:
        return {
            "complete": self.complete(),
            "progress": (
                self.progress_fraction()
            ),
            "incomplete": list(
                self.incomplete()
            ),
            "requirements": [
                {
                    "requirement": (
                        state.requirement
                    ),
                    "status": state.status,
                    "evidence": list(
                        state.evidence
                    ),
                }
                for state
                in self.requirements.values()
            ],
        }
