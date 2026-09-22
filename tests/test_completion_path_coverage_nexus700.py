from __future__ import annotations

from pathlib import Path
import ast


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(
    SOURCE
)


def _run():
    agent = next(
        node
        for node in TREE.body
        if (
            isinstance(
                node,
                ast.ClassDef,
            )
            and node.name
            == "Agent"
        )
    )

    return next(
        node
        for node in agent.body
        if (
            isinstance(
                node,
                ast.FunctionDef,
            )
            and node.name
            == "run"
        )
    )


def test_canonical_commit_helper_exists():
    assert (
        "NEXUS700_CANONICAL_COMPLETION_COMMIT_V1"
        in SOURCE
    )


def test_normal_execution_uses_evidence_commit():
    run = _run()

    segment = (
        ast.get_source_segment(
            SOURCE,
            run,
        )
        or ""
    )

    assert (
        "NEXUS700_NORMAL_EXECUTION_EVIDENCE_COMMIT_V1"
        in segment
    )

    assert (
        "_commit_completion_with_evidence("
        in segment
    )


def test_obsolete_last_return_gate_removed():
    assert (
        "NEXUS700_COMPLETION_EVIDENCE_GATE_V1"
        not in SOURCE
    )


def test_pending_status_is_persisted():
    assert (
        '"VERIFICATION_PENDING"'
        in SOURCE
    )

    assert (
        '"completion_evidence_pending"'
        in SOURCE
    )


def test_fast_lookup_remains_separate():
    run = _run()

    segment = (
        ast.get_source_segment(
            SOURCE,
            run,
        )
        or ""
    )

    assert (
        "zero_llm_fast_lookup"
        in segment
    )

    assert (
        "FAST_LOOKUP"
        in segment
    )
