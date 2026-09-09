from __future__ import annotations

from dataclasses import dataclass, field
import json


@dataclass
class AcceptanceItem:
    name: str
    passed: bool
    evidence: str
    reason: str = ""


class AcceptanceReport:
    def __init__(
        self,
        task,
    ):
        self.task = task
        self.items: list[
            AcceptanceItem
        ] = []

    def add(
        self,
        name,
        passed,
        evidence,
        reason="",
    ):
        self.items.append(
            AcceptanceItem(
                name=name,
                passed=bool(passed),
                evidence=evidence,
                reason=reason,
            )
        )

    def passed(self):
        return (
            bool(self.items)
            and all(
                x.passed
                for x in self.items
            )
        )

    def to_dict(self):
        return {
            "task": self.task,
            "status": (
                "PASS"
                if self.passed()
                else "FAIL"
            ),
            "criteria": [
                {
                    "name": i.name,
                    "passed": i.passed,
                    "evidence": i.evidence,
                    "reason": i.reason,
                }
                for i in self.items
            ],
        }

    def to_text(self):
        data = self.to_dict()

        lines = [
            "NEXUS_ACCEPTANCE_REPORT",
            f"STATUS={data['status']}",
            "",
        ]

        for item in data[
            "criteria"
        ]:
            lines.append(
                f"[{'PASS' if item['passed'] else 'FAIL'}] "
                f"{item['name']}"
            )

            lines.append(
                f"EVIDENCE={item['evidence']}"
            )

            if item["reason"]:
                lines.append(
                    f"REASON={item['reason']}"
                )

            lines.append("")

        return "\n".join(lines)
