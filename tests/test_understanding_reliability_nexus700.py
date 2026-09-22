from __future__ import annotations

from pathlib import Path
import ast


SOURCE_PATH = Path(
    "nexus/runtime/understanding.py"
)

SOURCE = SOURCE_PATH.read_text(
    encoding="utf-8"
)

TREE = ast.parse(SOURCE)


def test_understanding_contract_mentions_recommended_plan():
    assert (
        "recommended_plan"
        in SOURCE
    )


def test_understanding_contract_mentions_completion_definition():
    assert (
        "completion_definition"
        in SOURCE
    )


def test_understanding_has_schema_repair_path():
    lower = SOURCE.lower()

    assert "repair" in lower
    assert "schema" in lower


def test_understanding_has_finalization_path():
    lower = SOURCE.lower()

    assert (
        "finaliz"
        in lower
    )


def test_understanding_parser_does_not_silently_drop_required_fields():
    required = (
        "recommended_plan",
        "completion_definition",
    )

    for field in required:
        assert field in SOURCE
