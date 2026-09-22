from nexus.runtime.understanding import (
    LIST_FIELDS,
    _complete_finalizer_empty_lists,
    normalize_understanding_structure,
)


def test_general_normalizer_does_not_invent_fields():
    result = normalize_understanding_structure(
        {
            "explicit_requests": [],
        }
    )

    assert (
        "completion_definition"
        not in result
    )

    assert (
        "implicit_requirements"
        not in result
    )


def test_finalizer_recovery_completes_missing_lists():
    result = _complete_finalizer_empty_lists(
        {
            "explicit_requests": [
                "Verify request",
            ],
        }
    )

    for field in LIST_FIELDS:
        assert field in result
        assert isinstance(
            result[field],
            list,
        )


def test_finalizer_recovery_preserves_existing_lists():
    result = _complete_finalizer_empty_lists(
        {
            "explicit_requests": [
                "Verify request",
            ],
        }
    )

    assert result[
        "explicit_requests"
    ] == [
        "Verify request",
    ]


def test_finalizer_recovery_does_not_invent_scalars():
    result = _complete_finalizer_empty_lists(
        {
            "explicit_requests": [],
        }
    )

    for field in (
        "user_goal",
        "desired_end_state",
        "current_requested_phase",
        "mutation_policy",
        "expected_response",
        "confidence",
    ):
        assert field not in result
