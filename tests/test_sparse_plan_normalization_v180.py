from nexus.runtime.planner import (
    normalize_plan_structure,
    validate_plan,
)


OPTIONAL_EMPTY_LISTS = (
    "approval_gates",
    "targets",
    "search_strategy",
    "evidence_plan",
    "evaluation_plan",
    "selection_strategy",
    "first_actions",
)


def sparse_plan():
    return {
        "current_phase": "read requested files",
        "authorized_now": [
            "read pyproject.toml",
            "read README.md",
        ],
        "forbidden_now": [
            "do not modify files",
        ],
        "deferred_actions": [],
        "stop_conditions": [
            "requested facts are reported",
        ],
    }


def test_normalizer_fills_optional_lists():
    result = normalize_plan_structure(
        sparse_plan()
    )

    for field in OPTIONAL_EMPTY_LISTS:
        assert result[field] == []


def test_normalizer_does_not_mutate_input():
    source = sparse_plan()
    original = dict(source)

    normalize_plan_structure(source)

    assert source == original


def test_normalizer_does_not_invent_core_fields():
    result = normalize_plan_structure(
        {
            "current_phase": "inspect",
        }
    )

    assert "authorized_now" not in result
    assert "forbidden_now" not in result
    assert "stop_conditions" not in result


def test_validator_remains_strict_for_raw_sparse_plan():
    errors = validate_plan(
        sparse_plan()
    )

    assert any(
        "approval_gates" in error
        for error in errors
    )


def test_normalized_sparse_plan_passes_structural_validation():
    normalized = normalize_plan_structure(
        sparse_plan()
    )

    errors = validate_plan(
        normalized
    )

    missing = [
        error
        for error in errors
        if "missing field" in error
    ]

    assert missing == []
