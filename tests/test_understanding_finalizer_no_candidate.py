import pytest

import nexus.runtime.understanding as understanding


def _config():
    return {
        "finalizer_attempts": 2,
        "finalizer_max_tokens": 128,
    }


def test_zero_parsed_candidates_raise_understanding_error(
    monkeypatch,
):
    monkeypatch.setattr(
        understanding,
        "_generate_final_answer",
        lambda **kwargs: (
            "not-json",
            {},
        ),
    )

    def fail_extract(_raw):
        raise understanding.UnderstandingError(
            "No valid JSON object found"
        )

    monkeypatch.setattr(
        understanding,
        "extract_json_object",
        fail_extract,
    )

    with pytest.raises(
        understanding.UnderstandingError
    ) as exc:
        understanding._finalize_understanding_payload(
            model=object(),
            tokenizer=object(),
            user_request="Inspect project",
            previous_output="invalid",
            cfg=_config(),
        )

    assert (
        "Understanding finalizer failed"
        in str(exc.value)
    )

    assert (
        "No valid JSON object found"
        in str(exc.value)
    )


def test_zero_candidate_does_not_enter_list_recovery(
    monkeypatch,
):
    monkeypatch.setattr(
        understanding,
        "_generate_final_answer",
        lambda **kwargs: (
            "not-json",
            {},
        ),
    )

    def fail_extract(_raw):
        raise understanding.UnderstandingError(
            "No valid JSON object found"
        )

    monkeypatch.setattr(
        understanding,
        "extract_json_object",
        fail_extract,
    )

    calls = []

    def recovery(payload):
        calls.append(payload)
        return payload

    monkeypatch.setattr(
        understanding,
        "_complete_finalizer_empty_lists",
        recovery,
    )

    with pytest.raises(
        understanding.UnderstandingError
    ):
        understanding._finalize_understanding_payload(
            model=object(),
            tokenizer=object(),
            user_request="Inspect project",
            previous_output="invalid",
            cfg=_config(),
        )

    assert calls == []
