from nexus.runtime.prompt_milestones import (
    should_activate_turn_checklist,
)


def test_small_prompts_stay_normal():
    assert not should_activate_turn_checklist(
        "Explain this function."
    )

    assert not should_activate_turn_checklist(
        "What is the current status?"
    )

    assert not should_activate_turn_checklist(
        "Perform a comprehensive READ-ONLY "
        "BunkerGame inspection."
    )


def test_explicit_master_prompt_activates():
    assert should_activate_turn_checklist(
        """MASTER PROMPT

Inspect BunkerGame completely.
Do not modify anything.
"""
    )


def test_three_step_request_activates():
    assert should_activate_turn_checklist(
        """Perform a read-only audit.

1. Inspect architecture.
2. Inspect gameplay.
3. Produce a verified summary.
"""
    )


def test_bullet_master_request_activates():
    assert should_activate_turn_checklist(
        """Review the project:
- Inspect architecture.
- Inspect gameplay.
- Inspect tooling.
"""
    )


def test_ordered_two_step_request_activates():
    assert should_activate_turn_checklist(
        """Execute every step in order:
1. Inspect architecture.
2. Verify the result.
Do not declare completion until all steps pass.
"""
    )


def test_inline_master_prompt_forms_activate():
    assert should_activate_turn_checklist(
        "MASTER PROMPT: Inspect BunkerGame."
    )

    assert should_activate_turn_checklist(
        "MASTER PROMPT — Inspect BunkerGame."
    )

    assert should_activate_turn_checklist(
        "MASTER PROMPT\n\nInspect BunkerGame."
    )

    assert should_activate_turn_checklist(
        "## MASTER PROMPT\nInspect BunkerGame."
    )

    assert not should_activate_turn_checklist(
        "MASTER PROMPTING is useful."
    )
