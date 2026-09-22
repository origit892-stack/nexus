from __future__ import annotations

import json
import random
import time

from dataclasses import dataclass
from typing import Callable, Generic, TypeVar


T = TypeVar("T")


class NexusReliabilityError(RuntimeError):
    pass


class RetryExhausted(NexusReliabilityError):
    pass


class CircuitOpen(NexusReliabilityError):
    pass


@dataclass(frozen=True)
class RetryPolicy:
    attempts: int = 3
    base_delay: float = 0.25
    max_delay: float = 4.0
    jitter: float = 0.10

    def delay_for(self, attempt: int) -> float:
        raw = min(
            self.max_delay,
            self.base_delay * (2 ** max(0, attempt - 1)),
        )

        return max(
            0.0,
            raw + random.uniform(
                -self.jitter,
                self.jitter,
            ),
        )


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        reset_after: float = 30.0,
    ):
        self.failure_threshold = max(
            1,
            failure_threshold,
        )

        self.reset_after = max(
            0.0,
            reset_after,
        )

        self.failures = 0
        self.opened_at: float | None = None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True

        if (
            time.monotonic()
            - self.opened_at
            >= self.reset_after
        ):
            self.failures = 0
            self.opened_at = None
            return True

        return False

    def success(self) -> None:
        self.failures = 0
        self.opened_at = None

    def failure(self) -> None:
        self.failures += 1

        if self.failures >= self.failure_threshold:
            self.opened_at = time.monotonic()


def retry_call(
    fn: Callable[[], T],
    *,
    policy: RetryPolicy | None = None,
    retry_if: Callable[[Exception], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    policy = policy or RetryPolicy()

    last_error: Exception | None = None

    for attempt in range(
        1,
        policy.attempts + 1,
    ):
        try:
            return fn()
        except Exception as exc:
            last_error = exc

            if (
                retry_if is not None
                and not retry_if(exc)
            ):
                raise

            if attempt >= policy.attempts:
                break

            sleep(
                policy.delay_for(attempt)
            )

    raise RetryExhausted(
        f"operation failed after "
        f"{policy.attempts} attempts: "
        f"{last_error}"
    ) from last_error
