from pathlib import Path


def source():
    return Path(
        "nexus/ui/app.py"
    ).read_text()


def test_history_is_scrollable():
    text = source()

    assert (
        'id="session-history-scroll"'
        in text
    )

    assert "VerticalScroll" in text


def test_actions_have_fixed_container():
    text = source()

    assert (
        'id="session-actions"'
        in text
    )


def test_all_session_controls_exist():
    text = source()

    for control in (
        'id="open-agent-shell"',
        'id="continue-session"',
        'id="complete-session"',
        'id="close-session"',
    ):
        assert control in text


def test_escape_always_closes_detail():
    text = source()

    assert (
        '"escape"'
        in text
    )

    assert (
        "def action_close_session("
        in text
    )


def test_dynamic_version_preserved():
    text = source()

    assert (
        "from nexus import __version__"
        in text
    )

    assert (
        "AGENT OS / 1.6"
        not in text
    )
