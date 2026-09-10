from nexus.runtime.route_policy import (
    automatic_route_enforcement_enabled,
)


def test_default_off(
    monkeypatch,
):
    monkeypatch.delenv(
        "NEXUS_ROUTE_MODE",
        raising=False,
    )

    assert not (
        automatic_route_enforcement_enabled()
    )


def test_strict_available(
    monkeypatch,
):
    monkeypatch.setenv(
        "NEXUS_ROUTE_MODE",
        "STRICT",
    )

    assert (
        automatic_route_enforcement_enabled()
    )
