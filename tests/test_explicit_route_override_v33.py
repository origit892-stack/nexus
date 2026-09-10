from nexus.runtime.fast_router import (
    classify_task,
    explicit_route_name,
    route_source,
)


def test_explicit_fast_lookup_overrides_edit_words():
    task = """
    This is a FAST_LOOKUP task.
    Find assets and verify references.
    Determine what may need editing later.
    Do not edit.
    """

    assert (
        explicit_route_name(task)
        == "FAST_LOOKUP"
    )

    assert (
        classify_task(task).name
        == "FAST_LOOKUP"
    )

    assert (
        route_source(task)
        == "EXPLICIT"
    )


def test_explicit_edit_and_verify():
    task = """
    This is an EDIT_AND_VERIFY task.
    Find, edit, update and verify the file.
    """

    assert (
        classify_task(task).name
        == "EDIT_AND_VERIFY"
    )

    assert (
        route_source(task)
        == "EXPLICIT"
    )


def test_route_colon_fast_lookup():
    assert (
        classify_task(
            "ROUTE: FAST_LOOKUP\n"
            "Find tree assets."
        ).name
        == "FAST_LOOKUP"
    )


def test_nexus_route_equals_fast_lookup():
    assert (
        classify_task(
            "NEXUS_ROUTE=FAST_LOOKUP\n"
            "inventory tree assets"
        ).name
        == "FAST_LOOKUP"
    )


def test_no_explicit_route_uses_classifier():
    task = "Find all tree assets."

    assert (
        explicit_route_name(task)
        is None
    )

    assert (
        route_source(task)
        == "CLASSIFIER"
    )


def test_fast_lookup_contract_preserved():
    route = classify_task(
        "This is a FAST_LOOKUP task."
    )

    assert route.name == "FAST_LOOKUP"
    assert route.discovery_budget == 8
    assert route.action_iteration == 5
