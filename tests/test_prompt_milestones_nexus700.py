from __future__ import annotations

from nexus.runtime.prompt_milestones import (
    analyze_prompt_complexity,
    master_prompt_hash,
    milestone_execution_prompt,
    milestone_plan_from_payload,
    validate_milestone_plan,
)


def test_small_prompt_stays_normal():
    result = (
        analyze_prompt_complexity(
            'reply with exactly "Hello"'
        )
    )

    assert not result.milestone_mode


def test_large_prompt_enters_milestone_mode():
    prompt = "\n".join(
        (
            f"===== SECTION {index} =====\n"
            "Inspect the project.\n"
            "Determine current state.\n"
            "Do not modify anything.\n"
            f"FINAL_{index}=PASS"
        )
        for index in range(
            1,
            18,
        )
    )

    result = (
        analyze_prompt_complexity(
            prompt
        )
    )

    assert result.milestone_mode


def test_plan_hash_must_match_master_prompt():
    prompt = "Large task"

    payload = {
        "master_prompt_sha256":
            "wrong",

        "milestones": [],
    }

    errors = (
        validate_milestone_plan(
            prompt=prompt,
            payload=payload,
        )
    )

    assert (
        "master prompt hash mismatch"
        in errors
    )


def test_valid_plan_roundtrip():
    prompt = (
        "Inspect project, then verify it."
    )

    digest = master_prompt_hash(
        prompt
    )

    payload = {
        "master_prompt_sha256":
            digest,

        "milestones": [
            {
                "id":
                    "M1",

                "title":
                    "Inspect",

                "objective":
                    "Inspect project",

                "requirements": [
                    "Inspect project"
                ],

                "restrictions": [
                    "Read only"
                ],

                "dependencies":
                    [],

                "evidence_required": [
                    "Inspection evidence"
                ],

                "completion_definition": [
                    "Inspection complete"
                ],
            },
            {
                "id":
                    "M2",

                "title":
                    "Verify",

                "objective":
                    "Verify report",

                "requirements": [
                    "Verify findings"
                ],

                "restrictions":
                    [],

                "dependencies": [
                    "M1"
                ],

                "evidence_required": [
                    "Verification evidence"
                ],

                "completion_definition": [
                    "Verification complete"
                ],
            },
        ],

        "global_restrictions": [
            "Do not mutate project"
        ],

        "final_completion_definition": [
            "Audit complete"
        ],
    }

    plan = (
        milestone_plan_from_payload(
            prompt=prompt,
            payload=payload,
        )
    )

    assert len(
        plan.milestones
    ) == 2

    execution = (
        milestone_execution_prompt(
            plan=plan,
            index=0,
        )
    )

    assert (
        "Execute ONLY this milestone"
        in execution
    )

    assert (
        "Do not mutate project"
        in execution
    )


def test_string_completion_definition_is_safely_normalized():
    from nexus.runtime.prompt_milestones import (
        normalize_milestone_payload,
    )

    payload = {
        "milestones": [
            {
                "id": "M1",
                "title": "Audit",
                "objective": "Audit",
                "requirements": "Inspect",
                "restrictions": "Read only",
                "dependencies": [],
                "evidence_required": "Evidence",
                "completion_definition": "Complete",
            }
        ],
        "global_restrictions": "Do not mutate",
        "final_completion_definition": "Done",
    }

    result = normalize_milestone_payload(
        payload
    )

    item = result["milestones"][0]

    assert item[
        "completion_definition"
    ] == ["Complete"]

    assert item[
        "requirements"
    ] == ["Inspect"]

    assert result[
        "global_restrictions"
    ] == ["Do not mutate"]


def test_normalizer_preserves_existing_lists():
    from nexus.runtime.prompt_milestones import (
        normalize_milestone_payload,
    )

    payload = {
        "milestones": [
            {
                "requirements": [
                    "A",
                    "B",
                ],
                "completion_definition": [
                    "C",
                    "D",
                ],
            }
        ]
    }

    result = normalize_milestone_payload(
        payload
    )

    assert result[
        "milestones"
    ][0]["requirements"] == [
        "A",
        "B",
    ]

    assert result[
        "milestones"
    ][0][
        "completion_definition"
    ] == [
        "C",
        "D",
    ]
