import ast
from pathlib import Path


SOURCE = Path(
    "nexus/agent.py"
).read_text(
    encoding="utf-8"
)

TREE = ast.parse(SOURCE)


def call_name(node):
    if not isinstance(node, ast.Call):
        return None

    if isinstance(node.func, ast.Name):
        return node.func.id

    if isinstance(node.func, ast.Attribute):
        return node.func.attr

    return None


def events():
    result = []

    for node in ast.walk(TREE):
        if not isinstance(node, ast.Call):
            continue

        if not isinstance(node.func, ast.Attribute):
            continue

        if node.func.attr != "event":
            continue

        if len(node.args) < 3:
            continue

        name = node.args[1]
        payload = node.args[2]

        if not isinstance(name, ast.Constant):
            continue

        if not isinstance(payload, ast.Dict):
            continue

        keys = set()
        constants = {}

        for key, value in zip(
            payload.keys,
            payload.values,
        ):
            if not isinstance(key, ast.Constant):
                continue

            keys.add(key.value)

            if isinstance(value, ast.Constant):
                constants[key.value] = value.value

        result.append(
            {
                "name": name.value,
                "line": node.lineno,
                "keys": keys,
                "constants": constants,
            }
        )

    return result


def test_single_completion_evaluator():
    calls = [
        node
        for node in ast.walk(TREE)
        if isinstance(node, ast.Call)
        and call_name(node)
        == "evaluate_execution_completion"
    ]

    assert len(calls) == 1


def test_exactly_two_completion_gate_events():
    found = [
        event
        for event in events()
        if event["name"]
        == "execution_completion_gate"
    ]

    assert len(found) == 2


def test_gate_events_have_pass_and_continue():
    found = [
        event
        for event in events()
        if event["name"]
        == "execution_completion_gate"
    ]

    values = {
        event["constants"].get("allow")
        for event in found
    }

    assert values == {
        False,
        True,
    }


def test_gate_payload_parity():
    required = {
        "iteration",
        "verdict",
        "allow",
        "summary",
        "unmet_conditions",
        "next_focus",
        "proposed_final_length",
        "evidence_count",
    }

    found = [
        event
        for event in events()
        if event["name"]
        == "execution_completion_gate"
    ]

    for event in found:
        assert required <= event["keys"]


def test_success_event_exists_once():
    found = [
        event
        for event in events()
        if event["name"]
        == "execution_success_return"
    ]

    assert len(found) == 1

    assert {
        "iteration",
        "proposed_final_length",
        "final_length",
        "status",
    } <= found[0]["keys"]


def test_events_follow_evaluator():
    evaluator = next(
        node.lineno
        for node in ast.walk(TREE)
        if isinstance(node, ast.Call)
        and call_name(node)
        == "evaluate_execution_completion"
    )

    relevant = [
        event
        for event in events()
        if event["name"] in {
            "execution_completion_gate",
            "execution_success_return",
        }
    ]

    assert relevant

    assert all(
        event["line"] > evaluator
        for event in relevant
    )


def test_human_visible_semantics_exist():
    strings = [
        node.value
        for node in ast.walk(TREE)
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
        )
    ]

    joined = "\n".join(strings)

    assert "EXECUTION COMPLETION" in joined
    assert "CONTINUE" in joined
    assert "PASS" in joined
    assert "EXECUTION SUCCESS RETURN" in joined
