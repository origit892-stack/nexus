from types import SimpleNamespace

from nexus.sessions.agent_shell import (
    _should_resume_turn_checklist,
)


def _session(
    *,
    active=True,
    final="FAIL",
    master="FAIL",
    status="NEW",
):
    return SimpleNamespace(
        status=status,
        working_state={
            "milestone_state": {
                "active": active,
                "current_milestone_index": None,
                "milestones": [
                    {
                        "id": "M1",
                        "status": "PASS",
                    },
                ],
                "final_verification": {
                    "status": final,
                    "result": None,
                    "evidence": [],
                },
                "master_status": master,
            },
        },
    )


def test_failed_final_verification_auto_resumes():
    assert _should_resume_turn_checklist(
        _session(
            final="FAIL",
            master="FAIL",
            status="NEW",
        )
    )


def test_top_level_new_does_not_block_resume():
    assert _should_resume_turn_checklist(
        _session(
            status="NEW",
        )
    )


def test_master_pass_does_not_resume():
    assert not _should_resume_turn_checklist(
        _session(
            final="PASS",
            master="PASS",
        )
    )


def test_inactive_checklist_does_not_resume():
    assert not _should_resume_turn_checklist(
        _session(
            active=False,
        )
    )


def test_non_checklist_session_does_not_resume():
    session = SimpleNamespace(
        status="NEW",
        working_state={},
    )

    assert not _should_resume_turn_checklist(
        session
    )
