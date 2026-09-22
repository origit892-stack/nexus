from __future__ import annotations

from dataclasses import dataclass
from typing import Any


def _items(
    value: Any,
) -> tuple[str, ...]:
    if value is None:
        return ()

    if isinstance(value, str):
        value = [value]

    if not isinstance(
        value,
        (list, tuple),
    ):
        return ()

    result: list[str] = []

    for item in value:
        text = str(item).strip()

        if (
            text
            and text not in result
        ):
            result.append(text)

    return tuple(result)


@dataclass(frozen=True)
class TaskContract:
    goal: str
    current_phase: str
    deliverables: tuple[str, ...]
    must_do: tuple[str, ...]
    must_not_do: tuple[str, ...]
    evidence_required: tuple[str, ...]
    done_when: tuple[str, ...]
    mutation_policy: str

    @classmethod
    def from_understanding_and_plan(
        cls,
        *,
        understanding: dict[str, Any],
        plan: dict[str, Any],
    ) -> "TaskContract":
        goal = str(
            understanding.get(
                "user_goal",
                understanding.get(
                    "actual_goal",
                    understanding.get(
                        "request",
                        "",
                    ),
                ),
            )
        ).strip()

        current_phase = str(
            plan.get(
                "current_phase",
                understanding.get(
                    "current_requested_phase",
                    understanding.get(
                        "current_phase",
                        "",
                    ),
                ),
            )
        ).strip()

        deliverables = _items(
            understanding.get(
                "desired_end_state",
                understanding.get(
                    "desired_result",
                ),
            )
        )

        if not deliverables:
            deliverables = _items(
                understanding.get(
                    "response_expected",
                    understanding.get(
                        "expected_response",
                    ),
                )
            )

        must_do = _items(
            plan.get(
                "authorized_now"
            )
        )

        must_not_do = _items(
            plan.get(
                "forbidden_now"
            )
        )

        evidence_required = _items(
            plan.get(
                "evidence_plan"
            )
        )

        evaluation = _items(
            plan.get(
                "evaluation_plan"
            )
        )

        evidence_required = tuple(
            dict.fromkeys(
                evidence_required
                + evaluation
            )
        )

        done_when = _items(
            plan.get(
                "stop_conditions"
            )
        )

        mutation_policy = str(
            understanding.get(
                "mutation_policy",
                "UNSURE",
            )
        ).strip().upper()

        return cls(
            goal=goal,
            current_phase=current_phase,
            deliverables=deliverables,
            must_do=must_do,
            must_not_do=must_not_do,
            evidence_required=evidence_required,
            done_when=done_when,
            mutation_policy=mutation_policy,
        )

    def as_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "goal": self.goal,
            "current_phase": self.current_phase,
            "deliverables": list(
                self.deliverables
            ),
            "must_do": list(
                self.must_do
            ),
            "must_not_do": list(
                self.must_not_do
            ),
            "evidence_required": list(
                self.evidence_required
            ),
            "done_when": list(
                self.done_when
            ),
            "mutation_policy": (
                self.mutation_policy
            ),
        }
