from __future__ import annotations

from dataclasses import dataclass, field
import uuid


@dataclass
class PlanNode:
    id: str
    role: str
    objective: str
    dependencies: list[str] = field(default_factory=list)
    status: str = "PENDING"
    attempts: int = 0
    max_attempts: int = 3
    result: str = ""
    acceptance: list[dict] = field(default_factory=list)


class ExecutionPlan:
    def __init__(self):
        self.nodes: dict[str, PlanNode] = {}

    def add(
        self,
        role,
        objective,
        dependencies=None,
        acceptance=None,
        max_attempts=3,
    ):
        node_id = uuid.uuid4().hex[:10]

        self.nodes[node_id] = PlanNode(
            id=node_id,
            role=role,
            objective=objective,
            dependencies=dependencies or [],
            acceptance=acceptance or [],
            max_attempts=max_attempts,
        )

        return node_id

    def ready(self):
        result = []

        for node in self.nodes.values():
            if node.status != "PENDING":
                continue

            blocked = False

            for dep in node.dependencies:
                dep_node = self.nodes.get(dep)

                if dep_node is None:
                    continue

                if dep_node.status != "PASS":
                    blocked = True
                    break

            if not blocked:
                result.append(node)

        return result

    def mark(
        self,
        node_id,
        status,
        result="",
    ):
        node = self.nodes[node_id]
        node.status = status
        node.result = result

    def serialize(self):
        return {
            nid: {
                "id": n.id,
                "role": n.role,
                "objective": n.objective,
                "dependencies": n.dependencies,
                "status": n.status,
                "attempts": n.attempts,
                "max_attempts": n.max_attempts,
                "result": n.result,
                "acceptance": n.acceptance,
            }
            for nid, n in self.nodes.items()
        }

    @classmethod
    def deserialize(cls, data):
        plan = cls()

        for nid, raw in data.items():
            plan.nodes[nid] = PlanNode(
                id=raw["id"],
                role=raw["role"],
                objective=raw["objective"],
                dependencies=raw.get(
                    "dependencies",
                    [],
                ),
                status=raw.get(
                    "status",
                    "PENDING",
                ),
                attempts=raw.get(
                    "attempts",
                    0,
                ),
                max_attempts=raw.get(
                    "max_attempts",
                    3,
                ),
                result=raw.get(
                    "result",
                    "",
                ),
                acceptance=raw.get(
                    "acceptance",
                    [],
                ),
            )

        return plan
