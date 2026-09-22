from __future__ import annotations

from pathlib import Path
import ast

import nexus.runtime.planner as planner


def test_planner_final_wrapper_uses_r1_final_answer_mode(
    monkeypatch,
):
    observed = {}

    def fake_final_answer(
        *,
        model,
        tokenizer,
        messages,
        max_tokens,
    ):
        observed["model"] = model
        observed["tokenizer"] = tokenizer
        observed["messages"] = messages
        observed["max_tokens"] = max_tokens

        return (
            '{"ok":true}',
            {
                "total_seconds": 0.01,
            },
        )

    monkeypatch.setattr(
        planner,
        "_generate_final_answer",
        fake_final_answer,
    )

    model = object()
    tokenizer = object()

    raw, metrics = (
        planner._generate_planner_final(
            model=model,
            tokenizer=tokenizer,
            messages=[
                {
                    "role": "user",
                    "content": "Return JSON.",
                }
            ],
            max_tokens=128,
        )
    )

    assert raw == '{"ok":true}'
    assert metrics["total_seconds"] == 0.01

    assert observed["model"] is model
    assert observed["tokenizer"] is tokenizer
    assert observed["max_tokens"] == 128


def test_every_planner_json_model_consumer_uses_final_mode():
    path = Path(
        planner.__file__
    )

    tree = ast.parse(
        path.read_text()
    )

    legacy = []
    final_calls = []

    for node in tree.body:
        if not isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            continue

        calls = [
            child
            for child in ast.walk(node)
            if isinstance(
                child,
                ast.Call,
            )
            and isinstance(
                child.func,
                ast.Name,
            )
        ]

        names = [
            call.func.id
            for call in calls
        ]

        if "extract_json_object" not in names:
            continue

        if "_generate" in names:
            legacy.append(
                node.name
            )

        if "_generate_planner_final" in names:
            final_calls.extend(
                [
                    node.name
                ]
                * names.count(
                    "_generate_planner_final"
                )
            )

    assert legacy == []

    # Current Planner has exactly three model generations
    # whose result is consumed as structured JSON.
    assert len(final_calls) == 3


def test_critic_no_longer_calls_reasoning_generator_directly():
    path = Path(
        planner.__file__
    )

    source = path.read_text()
    tree = ast.parse(source)

    critic = next(
        node
        for node in tree.body
        if isinstance(
            node,
            ast.FunctionDef,
        )
        and node.name == "critique_plan"
    )

    calls = [
        child.func.id
        for child in ast.walk(critic)
        if isinstance(
            child,
            ast.Call,
        )
        and isinstance(
            child.func,
            ast.Name,
        )
    ]

    assert "_generate" not in calls

    assert (
        "_generate_planner_final"
        in calls
    )

    assert (
        "extract_json_object"
        in calls
    )


def test_planner_final_wrapper_accepts_legacy_sampling_keywords(
    monkeypatch,
):
    observed = {}

    def fake_final_answer(
        *,
        model,
        tokenizer,
        messages,
        max_tokens,
    ):
        observed[
            "max_tokens"
        ] = max_tokens

        return (
            '{"ok":true}',
            {},
        )

    monkeypatch.setattr(
        planner,
        "_generate_final_answer",
        fake_final_answer,
    )

    raw, metrics = (
        planner._generate_planner_final(
            model=object(),
            tokenizer=object(),
            messages=[],
            max_tokens=512,
            temperature=0.0,
            top_p=0.0,
        )
    )

    assert raw == '{"ok":true}'
    assert metrics == {}

    assert (
        observed[
            "max_tokens"
        ]
        == 512
    )


def test_all_real_structured_call_keywords_are_supported():
    import inspect

    path = Path(
        planner.__file__
    )

    tree = ast.parse(
        path.read_text()
    )

    supported = set(
        inspect.signature(
            planner._generate_planner_final
        ).parameters
    )

    calls = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not isinstance(
            node.func,
            ast.Name,
        ):
            continue

        if (
            node.func.id
            != "_generate_planner_final"
        ):
            continue

        keywords = {
            keyword.arg
            for keyword in node.keywords
            if keyword.arg is not None
        }

        calls.append(
            (
                node.lineno,
                keywords,
            )
        )

        assert (
            keywords
            <= supported
        ), (
            node.lineno,
            keywords - supported,
        )

    assert len(calls) == 3
