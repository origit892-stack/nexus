import pytest

from nexus.runtime.structured_output import (
    StructuredOutputError,
    parse_json_resilient,
    validate_mapping,
)


def test_plain_json():
    assert parse_json_resilient(
        '{"ok":true}'
    ) == {
        "ok": True
    }


def test_markdown_fenced_json():
    value = parse_json_resilient(
        'Result:\n```json\n{"ok": true}\n```'
    )

    assert value["ok"] is True


def test_balanced_json_inside_noise():
    value = parse_json_resilient(
        'thinking...\n{"a": {"b": 2}}\nfinished'
    )

    assert value == {
        "a": {
            "b": 2
        }
    }


def test_braces_inside_strings():
    value = parse_json_resilient(
        'prefix {"x":"hello } world","n":3} suffix'
    )

    assert value["n"] == 3


def test_invalid_raises():
    with pytest.raises(
        StructuredOutputError
    ):
        parse_json_resilient(
            "definitely not json"
        )


def test_required_fields():
    with pytest.raises(
        StructuredOutputError
    ):
        validate_mapping(
            {"a": 1},
            required=(
                "a",
                "b",
            ),
        )
