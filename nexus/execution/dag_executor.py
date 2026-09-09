from __future__ import annotations

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)
from dataclasses import dataclass
import threading
import time

from nexus.execution.governor import (
    ResourceGovernor,
)


@dataclass
class NodeResult:
    id: str
    role: str
    status: str
    result: str
    started: float
    finished: float


class ParallelDAGExecutor:
    def __init__(
        self,
        tasks,
        runner,
        max_parallel=2,
    ):
        self.tasks = {
            t.id: t
            for t in tasks
        }

        self.runner = runner

        self.max_parallel = int(
            max_parallel
        )

        self.governor = (
            ResourceGovernor()
        )

        self.results = {}

        self.lock = threading.Lock()

    def _ready(self):
        ready = []

        for tid, task in self.tasks.items():
            if tid in self.results:
                continue

            deps = task.dependencies

            if all(
                dep in self.results
                and self.results[
                    dep
                ].status == "PASS"
                for dep in deps
            ):
                ready.append(task)

        return ready

    def _blocked(self):
        blocked = []

        for tid, task in self.tasks.items():
            if tid in self.results:
                continue

            for dep in task.dependencies:
                if (
                    dep in self.results
                    and self.results[
                        dep
                    ].status != "PASS"
                ):
                    blocked.append(task)
                    break

        return blocked

    def _run_one(self, task):
        started = time.time()

        try:
            result = self.runner(
                task
            )

            status = (
                "PASS"
                if result.get(
                    "status"
                ) == "PASS"
                else "FAIL"
            )

            text = str(
                result.get(
                    "result",
                    "",
                )
            )

        except Exception as e:
            status = "FAIL"

            text = (
                f"{type(e).__name__}: "
                f"{e}"
            )

        return NodeResult(
            id=task.id,
            role=task.role,
            status=status,
            result=text,
            started=started,
            finished=time.time(),
        )

    def execute(self):
        while len(
            self.results
        ) < len(
            self.tasks
        ):
            for task in self._blocked():
                self.results[
                    task.id
                ] = NodeResult(
                    id=task.id,
                    role=task.role,
                    status="BLOCKED",
                    result=(
                        "DEPENDENCY_FAILED"
                    ),
                    started=time.time(),
                    finished=time.time(),
                )

            ready = self._ready()

            if not ready:
                if len(
                    self.results
                ) == len(
                    self.tasks
                ):
                    break

                unresolved = [
                    x
                    for x in self.tasks
                    if x not in self.results
                ]

                raise RuntimeError(
                    "DAG_DEADLOCK="
                    + ",".join(
                        unresolved
                    )
                )

            limit = (
                self.governor
                .parallel_limit(
                    self.max_parallel
                )
            )

            batch = ready[
                :limit
            ]

            with ThreadPoolExecutor(
                max_workers=len(batch)
            ) as pool:
                futures = {
                    pool.submit(
                        self._run_one,
                        task,
                    ): task
                    for task in batch
                }

                for future in as_completed(
                    futures
                ):
                    result = (
                        future.result()
                    )

                    with self.lock:
                        self.results[
                            result.id
                        ] = result

        return self.results
