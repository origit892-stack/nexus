import pytest
from nexus.sessions.state_update import SessionStateUpdate, apply_state_update, extract_state_update, parse_state_update_data, strip_state_update
from nexus.sessions.store import SessionStore
def make_session(tmp_path):
    store = SessionStore(tmp_path); return store, store.create("Wave 4 objective", "Wave 4")
def test_no_block(): assert extract_state_update("normal response") is None
def test_extract():
    u = extract_state_update("x\nNEXUS_STATE_UPDATE\n{\"active_item\":\"two\",\"completed_work\":[\"one\"],\"pending_work\":[\"two\"],\"checkpoint\":\"one done\"}\nNEXUS_STATE_UPDATE_END")
    assert u.active_item == "two" and u.completed_work == ["one"]
def test_invalid():
    with pytest.raises(ValueError, match="INVALID_JSON"): extract_state_update("NEXUS_STATE_UPDATE\n{ nope }\nNEXUS_STATE_UPDATE_END")
def test_missing_end():
    with pytest.raises(ValueError, match="END_MISSING"): extract_state_update('NEXUS_STATE_UPDATE\n{"completed_work":[]}')
def test_unknown():
    with pytest.raises(ValueError, match="UNKNOWN_FIELDS"): parse_state_update_data({"destroy_project": True})
def test_dedupe(): assert parse_state_update_data({"completed_work":["one","one","two"]}).completed_work == ["one","two"]
def test_strip(): assert strip_state_update('Visible answer.\nNEXUS_STATE_UPDATE\n{"completed_work":["one"]}\nNEXUS_STATE_UPDATE_END') == "Visible answer."
def test_apply_completed(tmp_path):
    store,s=make_session(tmp_path); store.replace_pending(s.id,["one","two"]); store.set_active_item(s.id,"one"); x=apply_state_update(store,s.id,SessionStateUpdate(completed_work=["one"]))
    assert x.working_state["completed_work"]==["one"] and x.working_state["pending_work"]==["two"] and x.working_state["active_item"] is None
def test_pending(tmp_path):
    store,s=make_session(tmp_path); store.mark_done(s.id,"done"); x=apply_state_update(store,s.id,SessionStateUpdate(pending_work=["done","new"])); assert x.working_state["pending_work"]==["new"]
def test_blockers(tmp_path):
    store,s=make_session(tmp_path); store.add_blocker(s.id,"old"); x=apply_state_update(store,s.id,SessionStateUpdate(add_blockers=["new","new"],clear_blockers=["old"])); assert x.working_state["blockers"]==["new"]
def test_active(tmp_path):
    store,s=make_session(tmp_path); x=apply_state_update(store,s.id,SessionStateUpdate(active_item="next")); assert x.working_state["active_item"]=="next"
def test_completed_not_reactivated(tmp_path):
    store,s=make_session(tmp_path); store.mark_done(s.id,"done"); x=apply_state_update(store,s.id,SessionStateUpdate(active_item="done")); assert x.working_state["active_item"] is None
def test_checkpoint(tmp_path):
    store,s=make_session(tmp_path); x=apply_state_update(store,s.id,SessionStateUpdate(checkpoint="cp")); assert x.working_state["checkpoint_serial"]==1; x=apply_state_update(store,s.id,SessionStateUpdate()); assert x.working_state["checkpoint_serial"]==1
