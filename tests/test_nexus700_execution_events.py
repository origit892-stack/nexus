import json

from nexus.runtime.completion_observability import (
    emit_completion_gate,
    emit_success_return,
)
from nexus.runtime.execution_events import (
    ExecutionEventBus,
)


class Decision:
    allow = False
    verdict = "CONTINUE"
    summary = "runtime QA missing"
    unmet_conditions = [
        "runtime QA"
    ]
    next_focus = "run QA"


def test_completion_events(tmp_path):
    path = (
        tmp_path
        / "events.jsonl"
    )

    bus = ExecutionEventBus(
        path,
        run_id="test-run",
    )

    emit_completion_gate(
        bus,
        iteration=4,
        decision=Decision(),
        proposed_final="done",
        evidence_count=3,
    )

    emit_success_return(
        bus,
        iteration=5,
        proposed_final="verified",
    )

    rows = [
        json.loads(line)
        for line in path.read_text().splitlines()
    ]

    assert rows[0]["event"] == (
        "execution_completion_gate"
    )

    assert rows[0]["payload"][
        "verdict"
    ] == "CONTINUE"

    assert rows[1]["event"] == (
        "execution_success_return"
    )
