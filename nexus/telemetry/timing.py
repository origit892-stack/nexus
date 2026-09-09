from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, asdict


@dataclass
class TimingEvent:
    kind: str
    name: str
    started: float
    finished: float
    elapsed: float
    metadata: dict


class TimingLedger:
    def __init__(self):
        self.events = []
        self.lock = threading.Lock()

    def record(
        self,
        kind,
        name,
        started,
        finished=None,
        metadata=None,
    ):
        finished = (
            finished
            if finished is not None
            else time.time()
        )

        event = TimingEvent(
            kind=str(kind),
            name=str(name),
            started=float(started),
            finished=float(finished),
            elapsed=float(
                finished - started
            ),
            metadata=dict(
                metadata or {}
            ),
        )

        with self.lock:
            self.events.append(
                event
            )

        return event

    def summary(self):
        totals = {}

        for event in self.events:
            totals.setdefault(
                event.kind,
                0.0,
            )

            totals[event.kind] += (
                event.elapsed
            )

        return {
            "events": [
                asdict(x)
                for x in self.events
            ],
            "totals": {
                key: round(
                    value,
                    4,
                )
                for key, value
                in totals.items()
            },
            "event_count": len(
                self.events
            ),
        }

    def json(self):
        return json.dumps(
            self.summary(),
            ensure_ascii=False,
        )
