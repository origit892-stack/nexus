from __future__ import annotations

import json
import time

from openai import OpenAI

from nexus.agent import Agent
from nexus.config import effective_config
from nexus.execution import ParallelDAGExecutor
from nexus.models import ModelRouter
from nexus.planning import (
    PLANNER_SYSTEM,
    parse_plan,
)
from nexus.planning.fast import (
    FAST_PLANNER_SYSTEM,
    simple_web_research_plan,
    compact_objective,
)
from nexus.runtime.capabilities import (
    resolve_capabilities,
    tool_budget,
)
from nexus.runtime.tool_factory import (
    build_registry,
)
from nexus.runtime.evidence_integrity import (
    independent_evidence_passed,
)
from nexus.runtime.node_acceptance import (
    evaluate_node_completion,
)
from nexus.runtime.handoff import (
    build_dependency_handoff,
)


HARD_FAILURE_MARKERS = (
    "NEXUS_ACCEPTANCE_OVERRIDE=FAIL",
    "AGENT_EXCEPTION=",
    "MAX_ITERATIONS_REACHED",
    "NEXUS_TOOL_BUDGET_EXCEEDED=",
    "UNKNOWN_TOOL=",
)


class AutonomousOrchestrator:
    def __init__(
        self,
        workspace,
        live=True,
    ):
        self.workspace = workspace

        self.config = effective_config(
            workspace
        )

        self.live = live

        self.client = OpenAI(
            base_url=self.config[
                "base_url"
            ],
            api_key="ollama",
        )

        self.router = ModelRouter(
            self.config
        )

    def _planner_call(
        self,
        messages,
    ):
        started = time.time()

        kwargs = {
            "model": self.router.for_role(
                "director"
            ),
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 1200,
        }

        # Ollama's OpenAI-compatible endpoint supports
        # structured JSON response formatting on current
        # versions. Fall back cleanly if unavailable.
        try:
            response = (
                self.client
                .chat
                .completions
                .create(
                    **kwargs,
                    response_format={
                        "type": "json_object"
                    },
                )
            )

        except Exception:
            response = (
                self.client
                .chat
                .completions
                .create(
                    **kwargs
                )
            )

        elapsed = (
            time.time()
            - started
        )

        if self.live:
            print(
                "NEXUS PROFILE "
                f"planner_inference="
                f"{elapsed:.3f}s",
                flush=True,
            )

        return (
            response
            .choices[0]
            .message
            .content
            or ""
        )

    def plan(
        self,
        objective,
    ):
        objective = compact_objective(
            objective
        )

        # Deterministic fast path for common, low-risk
        # research -> independent verification workflows.
        fast = simple_web_research_plan(
            objective
        )

        if fast is not None:
            if self.live:
                print(
                    "NEXUS PROFILE "
                    "planner_fast_path=deterministic",
                    flush=True,
                )

            return parse_plan(
                json.dumps(
                    fast,
                    ensure_ascii=False,
                )
            )

        messages = [
            {
                "role": "system",
                "content": (
                    FAST_PLANNER_SYSTEM
                ),
            },
            {
                "role": "user",
                "content": objective,
            },
        ]

        last_error = None
        last_text = ""

        for attempt in range(
            1,
            3,
        ):
            last_text = (
                self._planner_call(
                    messages
                )
            )

            try:
                plan = parse_plan(
                    last_text
                )

                if self.live:
                    print(
                        "NEXUS PROFILE "
                        f"planner_attempts={attempt}",
                        flush=True,
                    )

                return plan

            except Exception as e:
                last_error = e

                if self.live:
                    print(
                        "NEXUS PROFILE "
                        f"planner_parse_failure="
                        f"{type(e).__name__}:{e}",
                        flush=True,
                    )

                # One compact repair only. Do not send the
                # large original planning prompt again.
                messages = [
                    {
                        "role": "system",
                        "content": (
                            FAST_PLANNER_SYSTEM
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            "Repair this invalid plan. "
                            "Return valid JSON only.\n"
                            f"ERROR={type(e).__name__}: {e}\n"
                            f"PLAN={last_text[:3000]}"
                        ),
                    },
                ]

        raise RuntimeError(
            "PLANNER_REPAIR_EXHAUSTED="
            f"{type(last_error).__name__}: "
            f"{last_error}"
        )

    def execute_plan(
        self,
        plan,
    ):
        completed = {}

        # Build once to discover the real runtime tool universe.
        full_registry, _ = build_registry(
            self.workspace,
            "director",
            "v83_capability_discovery",
            include_mcp=False,
        )

        available_tools = set(
            full_registry.names()
        )

        def runner(task):
            dependency_results = []

            for dep in task.dependencies:
                result = completed.get(
                    dep
                )

                if result is None:
                    continue

                dependency_results.append(
                    {
                        "task_id": dep,
                        "role": result.role,
                        "status": result.status,
                        "result": result.result,
                    }
                )

            handoff = (
                build_dependency_handoff(
                    dependency_results
                )
            )

            if self.live and dependency_results:
                print(
                    "NEXUS PROFILE "
                    f"handoff_chars={len(handoff)}",
                    flush=True,
                )

            acceptance = ""

            if task.acceptance:
                acceptance = (
                    "\n\nACCEPTANCE CRITERIA:\n"
                    + "\n".join(
                        f"- {x}"
                        for x in task.acceptance
                    )
                )

            allowed = resolve_capabilities(
                task.role,
                task.objective,
                task.acceptance,
                available_tools,
            )

            budget = tool_budget(
                task.role,
                task.objective,
            )

            capability_context = (
                "\n\nNEXUS TASK CAPABILITY CONTRACT:\n"
                f"ROLE={task.role}\n"
                f"TOOL_BUDGET={budget}\n"
                "AUTHORIZED_TOOLS="
                + (
                    ", ".join(
                        sorted(allowed)
                    )
                    if allowed
                    else "NONE"
                )
                + "\n"
                "Do not attempt tools outside this list. "
                "Do not inspect unrelated workspace state."
            )

            agent = Agent(
                self.config,
                self.workspace,
                role=task.role,
                live=self.live,
                allowed_tools=allowed,
                tool_budget=budget,
            )

            prompt = (
                task.objective
                + handoff
                + acceptance
                + capability_context
            )

            node_started = time.time()

            if self.live:
                print(
                    "NEXUS PROFILE "
                    f"node_start={task.id}:{task.role} "
                    f"prompt_chars={len(prompt)} "
                    f"tools={len(allowed)} "
                    f"budget={budget}",
                    flush=True,
                )

            result = agent.run(
                prompt
            )

            node_elapsed = (
                time.time()
                - node_started
            )

            if self.live:
                print(
                    "NEXUS PROFILE "
                    f"node_end={task.id}:{task.role} "
                    f"elapsed={node_elapsed:.3f}s "
                    f"result_chars={len(result)}",
                    flush=True,
                )

            hard_failure = any(
                marker in result
                for marker
                in HARD_FAILURE_MARKERS
            )

            # Acceptance is conservative:
            # explicit failure language also fails the node.
            lowered = result.lower()

            explicit_failure = any(
                marker in lowered
                for marker in (
                    "acceptance=fail",
                    "acceptance: fail",
                    "verification failed",
                    "unable to verify",
                    "could not verify",
                )
            )

            evidence_ok, evidence_reason = (
                independent_evidence_passed(
                    task.role,
                    task.objective,
                    task.acceptance,
                    result,
                )
            )

            completion_ok, completion_reason = (
                evaluate_node_completion(
                    task.role,
                    task.objective,
                    task.acceptance,
                    result,
                )
            )

            status = (
                "FAIL"
                if (
                    hard_failure
                    or explicit_failure
                    or not evidence_ok
                    or not completion_ok
                )
                else "PASS"
            )

            if not evidence_ok:
                result = (
                    result
                    + "\n\n"
                    + "NEXUS_EVIDENCE_INTEGRITY=FAIL"
                    + "\nREASON="
                    + evidence_reason
                )

            else:
                result = (
                    result
                    + "\n\n"
                    + "NEXUS_EVIDENCE_INTEGRITY=PASS"
                    + "\nREASON="
                    + evidence_reason
                )

            result = (
                result
                + "\nNEXUS_NODE_COMPLETION="
                + (
                    "PASS"
                    if completion_ok
                    else "FAIL"
                )
                + "\nNODE_COMPLETION_REASON="
                + completion_reason
            )

            return {
                "status": status,
                "result": result,
            }

        class RecordingExecutor(
            ParallelDAGExecutor
        ):
            def _run_one(
                self,
                task,
            ):
                result = super()._run_one(
                    task
                )

                completed[
                    task.id
                ] = result

                return result

        executor = RecordingExecutor(
            plan.tasks,
            runner,
            max_parallel=self.config[
                "agents"
            ][
                "max_parallel"
            ],
        )

        return executor.execute()

    def run(
        self,
        objective,
    ):
        plan = self.plan(
            objective
        )

        execution_started = time.time()

        results = self.execute_plan(
            plan
        )

        execution_elapsed = (
            time.time()
            - execution_started
        )

        if self.live:
            print(
                "NEXUS PROFILE "
                f"dag_execution="
                f"{execution_elapsed:.3f}s",
                flush=True,
            )

        passed = all(
            result.status == "PASS"
            for result in results.values()
        )

        return {
            "objective": objective,
            "plan": {
                "tasks": [
                    {
                        "id": task.id,
                        "role": task.role,
                        "objective": (
                            task.objective
                        ),
                        "dependencies": (
                            task.dependencies
                        ),
                        "acceptance": (
                            task.acceptance
                        ),
                    }
                    for task in plan.tasks
                ]
            },
            "results": {
                tid: {
                    "role": result.role,
                    "status": result.status,
                    "result": result.result,
                    "started": result.started,
                    "finished": result.finished,
                }
                for tid, result
                in results.items()
            },
            "status": (
                "PASS"
                if passed
                else "FAIL"
            ),
        }
