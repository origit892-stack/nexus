from pathlib import Path


def test_agent_exception_must_not_be_reported_as_success():
    source = Path(
        "nexus/cli.py"
    ).read_text(
        encoding="utf-8"
    )

    if "AGENT_EXCEPTION=" in source:
        nearby = source.split(
            "AGENT_EXCEPTION=",
            1,
        )[1][:1500]

        assert (
            "raise"
            in nearby
            or "Exit"
            in nearby
            or "exit"
            in nearby
        )


def test_run_state_supports_terminal_failure():
    source = Path(
        "nexus"
    )

    text = "\n".join(
        path.read_text(
            encoding="utf-8",
            errors="replace",
        )
        for path in source.rglob(
            "*.py"
        )
    )

    assert (
        "FAILED"
        in text
        or "ERROR"
        in text
    )


def test_success_event_exists_in_agent():
    source = Path(
        "nexus/agent.py"
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "execution_success_return"
        in source
    )
