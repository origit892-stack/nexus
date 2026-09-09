from __future__ import annotations

from dataclasses import dataclass, field
import json
import uuid


@dataclass
class TaskNode:
    id: str
    role: str
    task: str
    dependencies: list[str] = field(
        default_factory=list
    )
    status: str = "PENDING"
    result: str = ""


class TaskDAG:
    def __init__(self):
        self.nodes: dict[str, TaskNode] = {}

    def add(
        self,
        role,
        task,
        dependencies=None,
    ):
        nid = uuid.uuid4().hex[:10]

        self.nodes[nid] = TaskNode(
            id=nid,
            role=role,
            task=task,
            dependencies=dependencies or [],
        )

        return nid

    def ready(self):
        ready = []

        for node in self.nodes.values():
            if node.status != "PENDING":
                continue

            if all(
                self.nodes[d].status == "PASS"
                for d in node.dependencies
                if d in self.nodes
            ):
                ready.append(node)

        return ready

    def mark(
        self,
        node_id,
        status,
        result="",
    ):
        node = self.nodes[node_id]
        node.status = status
        node.result = result

    def dump(self):
        return {
            nid: {
                "role": n.role,
                "task": n.task,
                "dependencies": n.dependencies,
                "status": n.status,
                "result": n.result,
            }
            for nid, n in self.nodes.items()
        }
