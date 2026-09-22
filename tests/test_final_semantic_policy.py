

def test_final_restrictions_survive_noncolon_protocol_boundary():
    from nexus.runtime.prompt_milestones import (
        final_verification_execution_prompt,
        preplanned_understanding_prompt,
    )

    canonical = (
        final_verification_execution_prompt(
            """
NEXUS_MILESTONE_FINAL_VERIFICATION_V1
Verify final completion.

MASTER PROMPT:
Perform a READ-ONLY audit.

FINAL COMPLETION DEFINITION:
- Audit verified.
""".strip(),
            mutation_policy="READ_ONLY",
            restrictions=(
                "READ_ONLY",
                "Do not modify source.",
                "Do not modify Studio.",
            ),
        )
    )

    semantic = (
        preplanned_understanding_prompt(
            canonical
        )
    )

    assert (
        "MUTATION_POLICY=READ_ONLY"
        in semantic
    )

    assert "- READ_ONLY" in semantic

    assert (
        "- Do not modify source."
        in semantic
    )

    assert (
        "- Do not modify Studio."
        in semantic
    )
