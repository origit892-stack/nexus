import json
from pathlib import Path

from nexus.runtime.understanding import (
    FORM_FIELDS,
    extract_json_object,
    load_project_context,
    load_understanding_config,
    render_executor_brief,
    validate_understanding,
)


def payload():
    return {
        "user_goal": "Understand existing content.",
        "desired_end_state": "Evidence-backed report.",
        "current_requested_phase": "Investigation.",
        "explicit_requests": [
            "Inspect current state.",
        ],
        "explicit_restrictions": [],
        "implicit_requirements": [],
        "relevant_game_context": [
            "Roblox project.",
        ],
        "known_project_facts": [],
        "unknowns_requiring_discovery": [
            "Current project contents.",
        ],
        "mutation_policy": "UNSURE",
        "evidence_needed": [
            "Direct project evidence.",
        ],
        "recommended_plan": [
            "Inspect relevant evidence.",
        ],
        "completion_definition": [
            "Requested questions are answered.",
        ],
        "response_expected": "Concise report.",
        "confidence": 0.75,
    }


def test_plain_json():
    expected = payload()

    assert extract_json_object(
        json.dumps(expected)
    ) == expected


def test_reasoning_prefix():
    expected = payload()

    raw = (
        "reasoning..."
        "</think>\n"
        + json.dumps(expected)
    )

    assert (
        extract_json_object(raw)
        == expected
    )


def test_markdown_fence():
    expected = payload()

    raw = (
        "</think>\n"
        "```json\n"
        + json.dumps(expected)
        + "\n```"
    )

    assert (
        extract_json_object(raw)
        == expected
    )


def test_schema_valid():
    assert (
        validate_understanding(
            payload()
        )
        == []
    )


def test_missing_field_fails():
    value = payload()

    del value[
        "desired_end_state"
    ]

    errors = (
        validate_understanding(
            value
        )
    )

    assert any(
        "desired_end_state"
        in error
        for error in errors
    )


def test_bad_mutation_value_fails():
    value = payload()

    value[
        "mutation_policy"
    ] = "MAGIC"

    errors = (
        validate_understanding(
            value
        )
    )

    assert any(
        "mutation_policy"
        in error
        for error in errors
    )


def test_bad_confidence_fails():
    value = payload()

    value["confidence"] = 2.0

    errors = (
        validate_understanding(
            value
        )
    )

    assert any(
        "confidence"
        in error
        for error in errors
    )


def test_all_fields_defined():
    value = payload()

    for field in FORM_FIELDS:
        assert field in value


def test_executor_brief_drops_meta():
    value = payload()

    value["_private"] = {
        "x": 1
    }

    rendered = (
        render_executor_brief(
            value
        )
    )

    assert "_private" not in rendered


def test_required_config():
    cfg = (
        load_understanding_config()
    )

    assert cfg["required"] is True
    assert cfg["backend"] == "mlx"
    assert cfg["local_only"] is True
    assert cfg["tools_allowed"] is False


def test_bunkergame_context():
    context = load_project_context(
        Path.home()
        / "Documents"
        / "Projects"
        / "BunkerGame"
    ).casefold()

    assert "roblox" in context
    assert "rojo" in context
    assert "terrain" in context
    assert "blender" in context
    assert "open3d" in context


def test_single_string_list_field_is_normalized():
    from nexus.runtime.understanding import (
        normalize_understanding_structure,
    )

    value = payload()

    value[
        "completion_definition"
    ] = "The requested result is complete."

    normalized = (
        normalize_understanding_structure(
            value
        )
    )

    assert normalized[
        "completion_definition"
    ] == [
        "The requested result is complete."
    ]

    assert (
        validate_understanding(
            normalized
        )
        == []
    )


def test_normalization_does_not_invent_missing_fields():
    from nexus.runtime.understanding import (
        normalize_understanding_structure,
    )

    value = payload()

    del value[
        "completion_definition"
    ]

    normalized = (
        normalize_understanding_structure(
            value
        )
    )

    assert (
        "completion_definition"
        not in normalized
    )


def test_understanding_runtime_defaults_on(
    monkeypatch,
):
    from nexus.runtime.understanding import (
        understanding_enabled,
    )

    monkeypatch.delenv(
        "NEXUS_UNDERSTANDING_MODE",
        raising=False,
    )

    assert understanding_enabled()


def test_understanding_can_be_disabled_for_tests(
    monkeypatch,
):
    from nexus.runtime.understanding import (
        understanding_enabled,
    )

    monkeypatch.setenv(
        "NEXUS_UNDERSTANDING_MODE",
        "OFF",
    )

    assert not understanding_enabled()


def test_extract_json_from_complete_raw_when_think_never_closes():
    from nexus.runtime.understanding import (
        extract_json_object,
    )

    value = payload()

    raw = (
        "<think>\n"
        "unfinished reasoning text\n"
        + json.dumps(value)
    )

    assert (
        extract_json_object(raw)
        == value
    )


def test_finalizer_config_exists():
    from nexus.runtime.understanding import (
        load_understanding_config,
    )

    cfg = (
        load_understanding_config()
    )

    assert (
        cfg[
            "finalizer_max_tokens"
        ]
        >= 512
    )

    assert (
        cfg[
            "finalizer_attempts"
        ]
        >= 1
    )


def test_final_answer_prompt_closes_think_prefix():
    from nexus.runtime.understanding import (
        _build_final_answer_prompt,
    )

    class FakeTokenizer:
        def apply_chat_template(
            self,
            messages,
            tokenize=False,
            add_generation_prompt=True,
        ):
            return (
                "system\n"
                "user\n"
                "assistant\n"
                "<think>"
            )

    prompt = _build_final_answer_prompt(
        tokenizer=FakeTokenizer(),
        messages=[],
    )

    assert prompt.rstrip().endswith(
        "</think>"
    )


def test_final_answer_prompt_does_not_open_new_think():
    from nexus.runtime.understanding import (
        _build_final_answer_prompt,
    )

    class FakeTokenizer:
        def apply_chat_template(
            self,
            messages,
            tokenize=False,
            add_generation_prompt=True,
        ):
            return (
                "assistant-ready"
            )

    prompt = _build_final_answer_prompt(
        tokenizer=FakeTokenizer(),
        messages=[],
    )

    assert prompt.rstrip().endswith(
        "</think>"
    )
