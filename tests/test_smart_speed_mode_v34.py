from nexus.runtime.speed_governor import (
    SpeedGovernor,
    smart_mode_enabled,
)


def test_smart_is_default(
    monkeypatch,
):
    monkeypatch.delenv(
        "NEXUS_SPEED_MODE",
        raising=False,
    )

    assert smart_mode_enabled()


def test_strict_is_selectable(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )

    assert not smart_mode_enabled()


def test_smart_allows_unique_discovery_past_budget(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "SMART",
    )

    governor = SpeedGovernor(
        discovery_budget=1,
        action_required_iteration=1,
    )

    for index in range(10):
        result = governor.before_tool(
            iteration=index + 1,
            name="read_file",
            arguments={
                "path": (
                    f"/tmp/nexus_unique_{index}"
                ),
            },
        )

        assert result["allow"], (
            index,
            result,
        )


def test_smart_duplicate_guard_uses_runtime_limit(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "SMART",
    )

    governor = SpeedGovernor()

    args = {
        "path": "/tmp/nexus_same",
    }

    # Exactly the configured number of identical
    # calls must be accepted.
    for iteration in range(
        1,
        governor.repeated_call_limit + 1,
    ):
        result = governor.before_tool(
            iteration=iteration,
            name="read_file",
            arguments=args,
        )

        assert result["allow"], (
            iteration,
            result,
        )

    # The immediately following duplicate must
    # be rejected.
    blocked_iteration = (
        governor.repeated_call_limit
        + 1
    )

    result = governor.before_tool(
        iteration=blocked_iteration,
        name="read_file",
        arguments=args,
    )

    assert not result["allow"]

    assert (
        result["reason"]
        == "DUPLICATE_READ_ONLY_CALL"
    )


def test_smart_has_no_completion_floor(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "SMART",
    )

    governor = SpeedGovernor()

    assert (
        governor.completion_allowed(
            route_name="FAST_LOOKUP"
        )
        == (True, None)
    )


def test_strict_preserves_discovery_budget(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )

    governor = SpeedGovernor(
        discovery_budget=1,
        action_required_iteration=99,
    )

    first = governor.before_tool(
        iteration=1,
        name="read_file",
        arguments={
            "path": "/tmp/strict_a",
        },
    )

    assert first["allow"]

    second = governor.before_tool(
        iteration=2,
        name="read_file",
        arguments={
            "path": "/tmp/strict_b",
        },
    )

    assert not second["allow"]

    assert (
        second["reason"]
        == "DISCOVERY_BUDGET_EXCEEDED"
    )


def test_strict_preserves_action_pressure(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )

    governor = SpeedGovernor(
        discovery_budget=100,
        action_required_iteration=2,
    )

    first = governor.before_tool(
        iteration=1,
        name="read_file",
        arguments={
            "path": "/tmp/action_a",
        },
    )

    assert first["allow"]

    second = governor.before_tool(
        iteration=2,
        name="read_file",
        arguments={
            "path": "/tmp/action_b",
        },
    )

    assert not second["allow"]

    assert (
        second["reason"]
        == "ACTION_REQUIRED"
    )


def test_strict_preserves_completion_floor(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_SPEED_MODE",
        "STRICT",
    )

    governor = SpeedGovernor()

    allowed, reason = (
        governor.completion_allowed(
            route_name="FAST_LOOKUP"
        )
    )

    assert not allowed

    assert (
        reason
        == "INSUFFICIENT_DISCOVERY_EVIDENCE"
    )
