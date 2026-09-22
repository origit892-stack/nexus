import pytest

from nexus.runtime.reliability import (
    CircuitBreaker,
    RetryExhausted,
    RetryPolicy,
    retry_call,
)


def test_retry_recovers():
    state = {
        "calls": 0
    }

    def operation():
        state["calls"] += 1

        if state["calls"] < 3:
            raise RuntimeError(
                "temporary"
            )

        return "ok"

    result = retry_call(
        operation,
        policy=RetryPolicy(
            attempts=3,
            base_delay=0,
            max_delay=0,
            jitter=0,
        ),
        sleep=lambda _: None,
    )

    assert result == "ok"
    assert state["calls"] == 3


def test_retry_exhausts():
    with pytest.raises(
        RetryExhausted
    ):
        retry_call(
            lambda: (
                _ for _ in ()
            ).throw(
                RuntimeError("bad")
            ),
            policy=RetryPolicy(
                attempts=2,
                base_delay=0,
                max_delay=0,
                jitter=0,
            ),
            sleep=lambda _: None,
        )


def test_circuit_breaker():
    breaker = CircuitBreaker(
        failure_threshold=2,
        reset_after=999,
    )

    assert breaker.allow()

    breaker.failure()
    assert breaker.allow()

    breaker.failure()
    assert not breaker.allow()

    breaker.success()
    assert breaker.allow()
