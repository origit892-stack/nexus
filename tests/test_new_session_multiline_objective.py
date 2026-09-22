import ast
from pathlib import Path

import nexus.ui.app as app


def _source():
    return Path(
        app.__file__
    ).read_text(
        encoding="utf-8"
    )


def _new_session_source():
    source = _source()
    tree = ast.parse(source)

    cls = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.ClassDef)
            and node.name == "NewSessionScreen"
        )
    )

    return (
        ast.get_source_segment(
            source,
            cls,
        )
        or ""
    )


def test_objective_uses_multiline_textarea():
    source = _new_session_source()

    assert "yield TextArea(" in source
    assert 'id="objective"' in source
    assert '"#objective"' in source
    assert "TextArea" in source
    assert ".text" in source


def test_session_title_remains_input():
    source = _new_session_source()

    assert 'id="session-title"' in source
    assert "Input" in source
