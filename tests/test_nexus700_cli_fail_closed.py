from pathlib import Path
import ast


def test_cli_contains_fail_closed_agent_result():
    source = Path(
        "nexus/cli.py"
    ).read_text(
        encoding="utf-8"
    )

    ast.parse(source)

    assert (
        "NEXUS700_FAIL_CLOSED_AGENT_RESULT"
        in source
    )

    assert (
        'startswith("AGENT_EXCEPTION=")'
        in source
    )

    assert (
        "typer.Exit(code=1)"
        in source
    )
