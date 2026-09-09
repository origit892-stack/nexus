from __future__ import annotations

import time


def retry_call(
    fn,
    attempts=3,
    base_delay=1.0,
    exceptions=(Exception,),
):
    last = None

    for attempt in range(
        1,
        int(attempts) + 1,
    ):
        try:
            return fn()

        except exceptions as e:
            last = e

            if attempt >= attempts:
                break

            time.sleep(
                float(base_delay)
                * (2 ** (attempt - 1))
            )

    raise last
