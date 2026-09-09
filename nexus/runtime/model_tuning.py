from __future__ import annotations


ROLE_MAX_OUTPUT = {
    "researcher": 768,
    "qa": 768,
    "browser": 640,
    "architect": 1400,
    "security": 1200,
    "computer": 640,
    "devops": 1200,
}


def max_output_tokens(
    role,
    configured,
):
    configured = int(
        configured
    )

    cap = ROLE_MAX_OUTPUT.get(
        str(role)
    )

    if cap is None:
        return configured

    return min(
        configured,
        cap,
    )
