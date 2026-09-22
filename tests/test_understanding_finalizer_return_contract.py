import ast
from pathlib import Path

import nexus.runtime.understanding as understanding


def test_every_finalizer_success_return_is_payload_metrics_tuple():
    source = Path(
        understanding.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    fn = next(
        node
        for node in tree.body
        if (
            isinstance(node, ast.FunctionDef)
            and node.name
            == "_finalize_understanding_payload"
        )
    )

    returns = [
        node
        for node in ast.walk(fn)
        if isinstance(node, ast.Return)
    ]

    assert returns

    for node in returns:
        assert isinstance(
            node.value,
            ast.Tuple,
        )
        assert len(
            node.value.elts
        ) == 2


def test_empty_list_recovery_return_includes_metrics():
    source = Path(
        understanding.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert (
        "FINALIZER EMPTY-LIST RECOVERY"
        in source
    )

    marker = source.index(
        "FINALIZER EMPTY-LIST RECOVERY"
    )

    tail = source[
        marker:marker + 1000
    ]

    assert "payload" in tail
    assert "all_metrics" in tail
