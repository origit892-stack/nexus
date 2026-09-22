from __future__ import annotations

from nexus.runtime import understanding


def test_schema_has_all_fifteen_fields():
    schema = (
        understanding
        ._schema_description()
    )

    assert (
        tuple(
            schema.keys()
        )
        == understanding.FORM_FIELDS
    )

    assert len(schema) == 15


def test_plan_and_completion_are_list_fields():
    assert (
        "recommended_plan"
        in understanding.LIST_FIELDS
    )

    assert (
        "completion_definition"
        in understanding.LIST_FIELDS
    )


def test_normal_structure_converts_string_lists():
    payload = {
        field: []
        for field
        in understanding.LIST_FIELDS
    }

    payload.update({
        "user_goal":
            "Reply Hello",

        "desired_end_state":
            "Hello is returned",

        "current_requested_phase":
            "Response",

        "mutation_policy":
            "READ_ONLY",

        "response_expected":
            "Hello",

        "confidence":
            1.0,

        "recommended_plan":
            "Reply exactly Hello",

        "completion_definition":
            "The response is exactly Hello",
    })

    result = (
        understanding
        .normalize_understanding_structure(
            payload
        )
    )

    assert result[
        "recommended_plan"
    ] == [
        "Reply exactly Hello"
    ]

    assert result[
        "completion_definition"
    ] == [
        "The response is exactly Hello"
    ]


def test_fidelity_prompt_forbids_meta_goal_substitution():
    prompt = (
        understanding
        ._system_prompt("")
    )

    assert (
        "Interpret the USER REQUEST itself"
        in prompt
    )

    assert (
        "For simple or literal requests, preserve their simplicity."
        in prompt
    )


def test_critic_guided_messages_include_original_request():
    messages = (
        understanding
        ._critic_guided_understanding_messages(
            user_request=(
                'reply with exactly "Hello"'
            ),
            payload={
                "user_goal":
                    "Understand intent"
            },
            critic={
                "verdict":
                    "FAIL",

                "issues": [
                    "invented project facts"
                ],

                "unsupported_claims": [],
                "contradictions": [],
                "summary":
                    "Not faithful",
            },
            context_pack="",
        )
    )

    combined = "\n".join(
        item["content"]
        for item in messages
    )

    assert (
        'reply with exactly "Hello"'
        in combined
    )

    assert (
        "CRITIC-GUIDED CORRECTION MODE"
        in combined
    )
