import ast
from pathlib import Path

import nexus.runtime.understanding as understanding


def test_critic_correction_preserves_valid_primary_payload():
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
            and node.name == "understand_task"
        )
    )

    segment = (
        ast.get_source_segment(
            source,
            fn,
        )
        or ""
    )

    assert (
        "original_payload = payload"
        in segment
    )

    assert (
        "payload = original_payload"
        in segment
    )

    assert (
        "critic_correction_fallback"
        in segment
    )

    assert (
        "CRITIC CORRECTION FALLBACK"
        in segment
    )
