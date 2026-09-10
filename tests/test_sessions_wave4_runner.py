from __future__ import annotations

import pytest

import nexus.sessions.runner as runner
from nexus.sessions.store import SessionStore


class FakeResult:
    def __init__(self, text, run_id="wave4-run"):
        self.text = text
        self.run_id = run_id

    def __str__(self):
        return self.text


class FakeAgent:
    def __init__(self, result):
        self.result = result
        self.prompts = []

    def run(self, prompt):
        self.prompts.append(prompt)
        return self.result


def make_session(tmp_path):
    store = SessionStore(tmp_path)
    session = store.create("Wave 4 runner objective", "Wave 4 Runner")
    return store, session


def test_prompt_contains_state_update_protocol(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)
    agent = FakeAgent(FakeResult("normal result"))
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    runner.continue_session(tmp_path, session.id, "do work")

    assert len(agent.prompts) == 1
    prompt = agent.prompts[0]
    assert "STATE UPDATE PROTOCOL:" in prompt
    assert "NEXUS_STATE_UPDATE" in prompt
    assert "NEXUS_STATE_UPDATE_END" in prompt


def test_valid_update_applies_and_is_stripped(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)
    store.replace_pending(session.id, ["task one", "task two"])
    store.set_active_item(session.id, "task one")

    text = '''Visible success.
NEXUS_STATE_UPDATE
{
  "active_item": "task two",
  "completed_work": ["task one"],
  "pending_work": ["task two"],
  "add_blockers": ["need review"],
  "clear_blockers": [],
  "checkpoint": "task one complete"
}
NEXUS_STATE_UPDATE_END'''

    agent = FakeAgent(FakeResult(text))
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    result = runner.continue_session(tmp_path, session.id, "do task one")
    loaded = store.get(session.id)

    assert result == "Visible success."
    assert loaded.last_result == "Visible success."
    assert loaded.history[-1]["type"] == "result"
    assert loaded.history[-1]["text"] == "Visible success."
    assert loaded.working_state["completed_work"] == ["task one"]
    assert loaded.working_state["pending_work"] == ["task two"]
    assert loaded.working_state["active_item"] == "task two"
    assert loaded.working_state["blockers"] == ["need review"]
    assert loaded.working_state["last_checkpoint"] == "task one complete"
    assert loaded.working_state["checkpoint_serial"] == 1


def test_explicit_state_checkpoint_prevents_double_checkpoint(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)

    text = '''ok
NEXUS_STATE_UPDATE
{"checkpoint":"explicit checkpoint"}
NEXUS_STATE_UPDATE_END'''

    agent = FakeAgent(FakeResult(text))
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    runner.continue_session(tmp_path, session.id, "work")
    loaded = store.get(session.id)

    assert loaded.working_state["checkpoint_serial"] == 1
    assert loaded.working_state["last_checkpoint"] == "explicit checkpoint"


def test_update_without_checkpoint_still_auto_checkpoints(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)

    text = '''ok
NEXUS_STATE_UPDATE
{"completed_work":["done"]}
NEXUS_STATE_UPDATE_END'''

    agent = FakeAgent(FakeResult(text))
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    runner.continue_session(tmp_path, session.id, "finish done")
    loaded = store.get(session.id)

    assert loaded.working_state["completed_work"] == ["done"]
    assert loaded.working_state["checkpoint_serial"] == 1
    assert "finish done" in loaded.working_state["last_checkpoint"]


def test_invalid_update_does_not_fail_successful_turn(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)

    text = '''Work itself succeeded.
NEXUS_STATE_UPDATE
{ invalid }
NEXUS_STATE_UPDATE_END'''

    agent = FakeAgent(FakeResult(text))
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    result = runner.continue_session(tmp_path, session.id, "work")
    loaded = store.get(session.id)

    assert loaded.status == "READY"
    assert str(result) == text
    assert any(
        entry.get("type") == "state_update_rejected"
        for entry in loaded.history
    )
    assert loaded.working_state["checkpoint_serial"] == 1


def test_normal_result_preserves_legacy_return_object(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)
    fake_result = FakeResult("plain result")
    agent = FakeAgent(fake_result)
    monkeypatch.setattr(runner, "_agent", lambda project_path: agent)

    result = runner.continue_session(tmp_path, session.id, "plain work")

    assert result is fake_result
    loaded = store.get(session.id)
    assert loaded.last_result == "plain result"


def test_state_update_not_processed_on_failure(tmp_path, monkeypatch):
    store, session = make_session(tmp_path)

    class FailingAgent:
        def run(self, prompt):
            raise RuntimeError("failure")

    monkeypatch.setattr(runner, "_agent", lambda project_path: FailingAgent())

    with pytest.raises(RuntimeError):
        runner.continue_session(tmp_path, session.id, "fail")

    loaded = store.get(session.id)
    assert loaded.status == "FAILED"
    assert loaded.working_state["checkpoint_serial"] == 0
