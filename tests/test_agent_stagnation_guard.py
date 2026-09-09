from __future__ import annotations

from types import SimpleNamespace

from nexus.agent import Agent


class FakeCompletions:
    def __init__(
        self,
        responses,
    ):
        self.responses = iter(
            responses
        )

    def create(
        self,
        **kwargs,
    ):
        return next(
            self.responses
        )


class FakeClient:
    def __init__(
        self,
        responses,
    ):
        self.chat = SimpleNamespace(
            completions=FakeCompletions(
                responses
            )
        )


def tool_response(
    call_id,
    name,
    arguments,
):
    call = SimpleNamespace(
        id=call_id,
        function=SimpleNamespace(
            name=name,
            arguments=arguments,
        ),
    )

    message = SimpleNamespace(
        content="",
        tool_calls=[
            call
        ],
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=message
            )
        ]
    )


def final_response(
    text,
):
    message = SimpleNamespace(
        content=text,
        tool_calls=[],
    )

    return SimpleNamespace(
        choices=[
            SimpleNamespace(
                message=message
            )
        ]
    )


def build_agent(
    tmp_path,
    responses,
):
    cfg = {
        "base_url": (
            "http://127.0.0.1:11434/v1"
        ),
        "model": "nexus-qwen",
        "agents": {
            "max_iterations": 10,
            "max_depth": 2,
        },
        "runtime": {
            "temperature": 0,
            "max_output_tokens": 512,
        },
    }

    agent = Agent(
        cfg,
        str(tmp_path),
        role="director",
        live=False,
    )

    agent.client = FakeClient(
        responses
    )

    return agent


def test_three_identical_calls_warn_then_finish(
    tmp_path,
):
    responses = [
        tool_response(
            "1",
            "memory_search",
            '{"query":"same","limit":1}',
        ),
        tool_response(
            "2",
            "memory_search",
            '{"query":"same","limit":1}',
        ),
        tool_response(
            "3",
            "memory_search",
            '{"query":"same","limit":1}',
        ),
        final_response(
            "Finished."
        ),
    ]

    agent = build_agent(
        tmp_path,
        responses,
    )

    result = agent.run(
        "test repeated calls"
    )

    assert result.startswith(
        "Finished."
    )


def test_four_identical_calls_fail_fast(
    tmp_path,
):
    responses = [
        tool_response(
            str(i),
            "memory_search",
            '{"query":"same","limit":1}',
        )
        for i in range(
            1,
            5,
        )
    ]

    agent = build_agent(
        tmp_path,
        responses,
    )

    result = agent.run(
        "test stagnation"
    )

    assert result.startswith(
        "NEXUS_STAGNATION_DETECTED:"
    )

    assert "memory_search" in result


def test_different_call_resets_counter(
    tmp_path,
):
    responses = [
        tool_response(
            "1",
            "memory_search",
            '{"query":"a","limit":1}',
        ),
        tool_response(
            "2",
            "memory_search",
            '{"query":"a","limit":1}',
        ),
        tool_response(
            "3",
            "memory_search",
            '{"query":"b","limit":1}',
        ),
        tool_response(
            "4",
            "memory_search",
            '{"query":"a","limit":1}',
        ),
        final_response(
            "Done."
        ),
    ]

    agent = build_agent(
        tmp_path,
        responses,
    )

    result = agent.run(
        "test reset"
    )

    assert result.startswith(
        "Done."
    )
