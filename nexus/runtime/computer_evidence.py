from __future__ import annotations

import json
import time
from dataclasses import dataclass, asdict


@dataclass
class ComputerEvidenceEvent:
    kind: str
    timestamp: float
    payload: dict


class ComputerEvidenceLedger:
    def __init__(self):
        self.events = []

    def record(
        self,
        kind,
        **payload,
    ):
        self.events.append(
            ComputerEvidenceEvent(
                kind=str(kind),
                timestamp=time.time(),
                payload=dict(
                    payload
                ),
            )
        )

    def has_before_after(self):
        kinds = [
            event.kind
            for event in self.events
        ]

        return (
            "screenshot_before"
            in kinds
            and "screenshot_after"
            in kinds
        )

    def has_verification(self):
        return any(
            event.kind
            == "verification"
            and bool(
                event.payload.get(
                    "passed"
                )
            )
            for event in self.events
        )

    def acceptance_passed(self):
        return (
            self.has_before_after()
            and self.has_verification()
        )

    def json(self):
        return json.dumps(
            [
                asdict(
                    event
                )
                for event in self.events
            ],
            ensure_ascii=False,
            indent=2,
        )
