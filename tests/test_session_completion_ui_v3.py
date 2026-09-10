from pathlib import Path

import ast


def source():
    return Path(
        "nexus/ui/app.py"
    ).read_text()


def test_session_detail_has_all_controls():
    text = source()

    assert 'id="continue-session"' in text
    assert 'id="complete-session"' in text
    assert 'id="close-session"' in text


def test_complete_is_explicit_action():
    text = source()

    assert (
        '"action": "complete"'
        in text
    )

    assert (
        'if action == "complete":'
        in text
    )


def test_complete_persists_status():
    text = source()

    assert (
        'session.status = "COMPLETED"'
        in text
    )

    assert "store.save(" in text


def test_continue_path_remains():
    text = source()

    assert (
        'if action != "continue":'
        in text
    )

    assert (
        '"action": "continue_session"'
        in text
    )


def test_only_one_ui_completed_assignment():
    tree = ast.parse(
        source()
    )

    assignments = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Assign,
        ):
            continue

        if (
            isinstance(
                node.value,
                ast.Constant,
            )
            and node.value.value
            == "COMPLETED"
        ):
            assignments.append(
                node
            )

    assert len(assignments) == 1


def test_ui_version_dynamic():
    text = source()

    assert (
        "from nexus import __version__"
        in text
    )

    assert (
        "AGENT OS / 1.6"
        not in text
    )

    assert (
        "AGENT OS / {__version__}"
        in text
    )
