from __future__ import annotations

from nexus.agent import Agent


class FakeStore:
    def __init__(
        self,
    ):
        self.events = []
        self.finishes = []

    def event(
        self,
        rid,
        name,
        payload,
    ):
        self.events.append(
            (
                rid,
                name,
                payload,
            )
        )

    def finish(
        self,
        rid,
        status,
        result,
    ):
        self.finishes.append(
            (
                rid,
                status,
                result,
            )
        )


class FakeRunState:
    def __init__(
        self,
    ):
        self.saved = []

    def save(
        self,
        payload,
    ):
        self.saved.append(
            payload
        )


def _agent():
    agent = object.__new__(
        Agent
    )

    agent.role = "director"
    agent.store = FakeStore()
    agent._understanding = None
    agent._execution_plan = None

    return agent


def test_canonical_commit_blocks_unverified_roblox():
    agent = _agent()
    state = FakeRunState()

    complete, result, decision = (
        agent
        ._commit_completion_with_evidence(
            rid="r1",
            run_state=state,
            task=(
                "Move Roblox MeshParts "
                "into a line in Studio."
            ),
            iteration=1,
            final=(
                "ARTIFACT=PASS"
            ),
        )
    )

    assert not complete

    assert (
        decision.status
        == "VERIFICATION_PENDING"
    )

    assert (
        agent.store.finishes[-1][1]
        == "VERIFICATION_PENDING"
    )

    assert (
        state.saved[-1]["status"]
        == "VERIFICATION_PENDING"
    )

    assert (
        result.startswith(
            "VERIFICATION_PENDING"
        )
    )


def test_canonical_commit_accepts_verified_roblox():
    agent = _agent()
    state = FakeRunState()

    complete, result, decision = (
        agent
        ._commit_completion_with_evidence(
            rid="r2",
            run_state=state,
            task=(
                "Move Roblox MeshParts "
                "into a line in Studio."
            ),
            iteration=1,
            final=(
                "ARTIFACT=PASS\\n"
                "INTEGRATION=PASS\\n"
                "STUDIO_VERIFICATION=PASS\\n"
                "VISUAL_QA=PASS"
            ),
        )
    )

    assert complete
    assert decision.complete

    assert (
        agent.store.finishes[-1][1]
        == "PASS"
    )

    assert (
        state.saved[-1]["status"]
        == "PASS"
    )


def test_canonical_commit_allows_non_mutating_answer():
    agent = _agent()
    state = FakeRunState()

    complete, result, decision = (
        agent
        ._commit_completion_with_evidence(
            rid="r3",
            run_state=state,
            task=(
                "Explain what this script does."
            ),
            iteration=0,
            final=(
                "It parses configuration."
            ),
        )
    )

    assert complete
    assert decision.complete

    assert (
        agent.store.finishes[-1][1]
        == "PASS"
    )
