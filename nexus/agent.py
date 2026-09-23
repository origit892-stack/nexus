from nexus.runtime.capability_envelope import (
    evaluate_capability,
)
import json
import threading
import time

from concurrent.futures import (
    ThreadPoolExecutor,
    as_completed,
)

from openai import OpenAI
from rich.console import Console

from .acceptance import (
    guard_final_answer,
)
from .store import Store
from .runtime.watchdog import RunWatchdog
from .runtime.evidence import EvidenceLedger
from .telemetry import TimingLedger
from .runtime.tool_cache import ToolCallCache
from .runtime.specialist_prompt import specialist_system_prompt
from .runtime.model_tuning import max_output_tokens
from .runtime.retry import retry_call
from .runtime.context import ContextEngine
from .runtime.run_state import RunState
from .memory import MemoryStore
from .tools import Tools
from .runtime.tool_factory import build_registry
from .tools.universal import UniversalTools, universal_schemas
from nexus.runtime.fast_router import classify_task, route_source
from nexus.runtime.speed_governor import SpeedGovernor, smart_mode_enabled
from nexus.runtime.route_policy import evaluate_route_tool, fast_lookup_hard_stop, automatic_route_enforcement_enabled
from nexus.runtime.understanding import (
    understand_task,
    render_executor_brief,
    UnderstandingError,
    understanding_enabled,
    compile_master_prompt,
)
from nexus.runtime.planner import plan_task, render_plan_brief, PlanningError
from nexus.runtime.execution_completion import (
    ExecutionCompletionError,
    evaluate_execution_completion,
    render_continue_instruction,
)
from nexus.runtime.task_contract import TaskContract
from nexus.runtime.execution_state import ExecutionState
from nexus.runtime.execution_core import (
    ExecutionCoreError,
    continuation_instruction,
    finalize_success,
    render_execution_progress,
)

from nexus.runtime.fast_first import (
    classify_fast_first,
    fast_lookup_contract,
    deterministic_fast_completion,
    FastFirstDecision,
)

from nexus.runtime.fast_lookup_engine import (
    execute_fast_lookup,
)

# NEXUS700_COMPLETION_EVIDENCE_IMPORT
from nexus.runtime.completion_evidence import (
    evaluate_completion_evidence,
    infer_evidence_requirements,
    preplanned_evidence_requirements,
)

# NEXUS700_MILESTONE_INTAKE_IMPORT_V1
from nexus.runtime.prompt_milestones import (
    analyze_prompt_complexity,
    milestone_execution_prompt,
    is_turn_checklist_execution_prompt,
    is_final_verification_prompt,
    preplanned_understanding_prompt,
)


console = Console()

PRINT_LOCK = threading.Lock()
CODER_LOCK = threading.Lock()


PROMPTS = {
    "director": """
You are Nexus Director.

You orchestrate rather than brute-force every task.

For substantial engineering work:

1. Inspect scope.
2. Delegate independent read-only analysis.
3. Compare evidence.
4. Assign exactly one Coder.
5. Run real tests.
6. Run independent QA.
7. Verify acceptance using acceptance_verify.
8. Report PASS only with real evidence.

CRITICAL ACCEPTANCE LAW:

A stub, mock, placeholder, simulation, fake implementation,
dry-run, pending implementation, or unexecuted command can NEVER
satisfy a criterion requiring a REAL implementation or REAL execution.

If the requirement says "real optimizer", a stub optimizer is FAIL.

If the requirement says "fresh generation", an old artifact is insufficient.

If the requirement says "executed", documentation is insufficient.

Never fabricate PASS.
""",

    "architect": """
You are Nexus Architect.

You are read-only.

Determine root cause, contracts, dependencies,
regression risks and the smallest correct implementation plan.
""",

    "coder": """
You are Nexus Coder.

You are the single implementation writer.

Make bounded changes only.

A checkpoint is created automatically before writes.

Never replace production behavior with stubs.

Run real tests.
""",

    "qa": """
You are Nexus independent QA.

You are read-only.

Distrust claims until verified.

A stub, mock or placeholder cannot satisfy
real implementation acceptance.
""",

    "researcher": """
You are Nexus Researcher.

Gather precise evidence.

Remain read-only unless another capability
is explicitly granted.
""",

    "security": """
You are Nexus Security Reviewer.

Review permissions, unsafe commands,
scope violations and dependency risks.
""",

    "browser": """
You are Nexus Browser Agent.

Research and navigate the web.
Use web_search, web_fetch and browser_open.
Do not perform local writes unless specifically authorized.
""",

    "computer": """
You are Nexus Computer Agent.

Operate the local graphical computer environment when required.
Use screenshots and macOS automation carefully.
Do not perform destructive actions without explicit authorization.
""",

    "devops": """
You are Nexus DevOps Agent.

Manage approved CLI processes, servers and SSH targets.
Prefer observable, reversible operations.
Never fabricate process success.
""",
}


def extract_text(
    msg,
):
    content = getattr(
        msg,
        "content",
        None,
    )

    if (
        isinstance(
            content,
            str,
        )
        and content.strip()
    ):
        return content.strip()

    for attr in (
        "reasoning_content",
        "reasoning",
    ):
        value = getattr(
            msg,
            attr,
            None,
        )

        if (
            isinstance(
                value,
                str,
            )
            and value.strip()
        ):
            return value.strip()

    extra = getattr(
        msg,
        "model_extra",
        None,
    ) or {}

    for key in (
        "reasoning",
        "thinking",
    ):
        value = extra.get(
            key
        )

        if (
            isinstance(
                value,
                str,
            )
            and value.strip()
        ):
            return value.strip()

    return ""


class Agent:

    def _configure_speed_governor(
        self,
        instruction: str,
    ):
        route = classify_task(
            instruction
        )

        self._speed_route = route

        self._speed_governor = SpeedGovernor(
            discovery_budget=(
                route.discovery_budget
            ),
            action_required_iteration=(
                route.action_iteration
            ),
        )

        return route

    def _speed_prompt(
        self,
    ) -> str:
        route = getattr(
            self,
            "_speed_route",
            None,
        )

        if route is None:
            return ""

        return (
            "\n\nNEXUS SPEED CONTRACT:\n"
            f"- route: {route.name}\n"
            f"- discovery budget: "
            f"{route.discovery_budget}\n"
            f"- concrete action required by "
            f"iteration: {route.action_iteration}\n"
            "- reuse prior tool results; do not "
            "repeat identical searches or reads\n"
            "- stop discovery once sufficient "
            "evidence exists\n"
            "- prefer one focused batch of work "
            "over iterative browsing\n"
            "- when independent read-only calls are needed, "
            "issue them together in the same model turn\n"
            "- FAST_LOOKUP should gather enough direct evidence "
            "before concluding; speed must not replace correctness\n"
            "- do not use memory_add for ordinary lookup results "
            "unless durable memory is explicitly required\n"
            "- FAST_LOOKUP is strictly read-only: only list_files, "
            "search_files, read_file, and memory_search are allowed\n"
            "- FAST_LOOKUP must never use shell, process_start, "
            "write_file, delegate_task, memory_add, package installs, "
            "Blender, Open3D, or any mutation\n"
            "- for FAST_LOOKUP, finish with the best supported answer "
            "rather than escaping the route policy\n"
        )


    def __init__(
            self,
            cfg,
            workspace,
            role="director",
            depth=0,
            live=True,
            allowed_tools=None,
            tool_budget=None,
            capability_policy="NORMAL",
        ):
            self.cfg = cfg
            self.workspace = workspace
            self.role = role
            self.depth = depth
            self.live = live
            self.allowed_tools = (
                set(allowed_tools)
                if allowed_tools is not None
                else None
            )
            self.tool_budget = tool_budget
            self.capability_policy = str(capability_policy or "NORMAL").upper()
            self.tool_calls_used = 0
            self.timing_ledger = TimingLedger()
            self.tool_cache = ToolCallCache()

            self.store = Store(
                workspace
            )

            self.client = OpenAI(
                base_url=cfg[
                    "base_url"
                ],
                api_key="ollama",
            )

            self.model = cfg[
                "model"
            ]

            self.context_engine = ContextEngine()
            self.watchdog = RunWatchdog(
                timeout_seconds=600
            )
            # NEXUS700_MILESTONE_STATE_V1
            self._master_prompt = None
            self._milestone_plan = None
            self._milestone_index = None
            self._prompt_complexity = None

    def say(
        self,
        text,
    ):
        if not self.live:
            return

        with PRINT_LOCK:
            console.print(
                text
            )

    def _enforce_capability_tool(
        self,
        tool_name,
    ):
        decision = evaluate_capability(
            policy=self.capability_policy,
            tool_name=tool_name,
        )

        if decision.allow:
            return

        raise PermissionError(
            "NEXUS_CAPABILITY_BLOCKED: "
            + str(self.capability_policy)
            + ":"
            + str(tool_name)
            + ":"
            + str(decision.reason)
        )

    def delegate_one(
        self,
        role,
        task,
    ):
        if role == "coder":
            if not CODER_LOCK.acquire(
                blocking=False
            ):
                return (
                    "CODER_ALREADY_RUNNING"
                )

        try:
            child = Agent(
                self.cfg,
                self.workspace,
                role=role,
                depth=self.depth + 1,
                live=self.live,
                        capability_policy=self.capability_policy,
                    )

            self.say(
                f"[cyan]AGENT START[/cyan] "
                f"{role}"
            )

            result = child.run(
                task
            )

            self.say(
                f"[cyan]AGENT END[/cyan] "
                f"{role}"
            )

            return result

        finally:
            if role == "coder":
                CODER_LOCK.release()

    def delegate_batch(
        self,
        specs,
    ):
        if any(
            x["role"] == "coder"
            for x in specs
        ):
            return (
                "PARALLEL_CODER_BLOCKED"
            )

        limit = min(
            int(
                self.cfg[
                    "agents"
                ][
                    "max_parallel"
                ]
            ),
            len(specs),
        )

        results = [
            None
        ] * len(specs)

        def worker(
            index,
            spec,
        ):
            child = Agent(
                self.cfg,
                self.workspace,
                role=spec[
                    "role"
                ],
                depth=self.depth + 1,
                live=self.live,
                        capability_policy=self.capability_policy,
                    )

            return (
                index,
                spec,
                child.run(
                    spec["task"]
                ),
            )

        with ThreadPoolExecutor(
            max_workers=limit
        ) as executor:
            futures = [
                executor.submit(
                    worker,
                    i,
                    spec,
                )
                for i, spec
                in enumerate(
                    specs
                )
            ]

            for future in as_completed(
                futures
            ):
                i, spec, result = (
                    future.result()
                )

                results[i] = {
                    "role": spec[
                        "role"
                    ],
                    "result": result,
                }

        return json.dumps(
            results,
            indent=2,
            ensure_ascii=False,
        )

    def delegation_schemas(
        self,
    ):
        if (
            self.role != "director"
            or self.depth >= int(
                self.cfg[
                    "agents"
                ][
                    "max_depth"
                ]
            )
        ):
            return []

        return [
            {
                "type": "function",
                "function": {
                    "name": "delegate_task",
                    "description": (
                        "Launch one isolated specialist. "
                        "Coder must use this route."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "role": {
                                "type": "string",
                                "enum": [
                                    "architect",
                                    "coder",
                                    "qa",
                                    "researcher",
                                    "security",
                                    "browser",
                                    "computer",
                                    "devops",
                                    "browser",
                                    "computer",
                                    "devops",
                                ],
                            },
                            "task": {
                                "type": "string",
                            },
                        },
                        "required": [
                            "role",
                            "task",
                        ],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "delegate_batch",
                    "description": (
                        "Launch parallel read-only specialists."
                    ),
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "tasks": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "role": {
                                            "type": "string",
                                            "enum": [
                                                "architect",
                                                "qa",
                                                "researcher",
                                                "security",
                                                "browser",
                                                "browser",
                                                "computer",
                                                "devops",
                                            ],
                                        },
                                        "task": {
                                            "type": "string",
                                        },
                                    },
                                    "required": [
                                        "role",
                                        "task",
                                    ],
                                },
                            },
                        },
                        "required": [
                            "tasks"
                        ],
                    },
                },
            },
        ]

    def _enforce_route_tool(
        self,
        *,
        name,
        arguments,
    ):
        if not automatic_route_enforcement_enabled():
            return None

        decision = evaluate_route_tool(
            route_name=self._speed_route.name,
            tool_name=name,
            arguments=arguments,
        )

        if decision.allow:
            return None

        return {
            "allow": False,
            "reason": decision.reason,
            "output": (
                "NEXUS ROUTE POLICY BLOCK: "
                + str(decision.reason)
                + ". The active route is "
                + str(self._speed_route.name)
                + ". Do not attempt an alternate "
                "tool to bypass this restriction."
            ),
        }


    # NEXUS700_COMPLETION_EVIDENCE_HELPER
    def _completion_evidence_gate(
        self,
        *,
        task,
        result,
    ):
        understanding = getattr(
            self,
            "_understanding",
            None,
        )

        plan = getattr(
            self,
            "_execution_plan",
            None,
        )

        requirements = (
            preplanned_evidence_requirements(
                task
            )
        )

        if requirements is None:
            requirements = (
                infer_evidence_requirements(
                    task=task,
                    understanding=(
                        self._understanding
                        if isinstance(
                            self._understanding,
                            dict,
                        )
                        else None
                    ),
                    plan=self._execution_plan,
                )
            )

        decision = (
            evaluate_completion_evidence(
                requirements=requirements,
                evidence=result,
            )
        )

        return decision



    # NEXUS700_CANONICAL_COMPLETION_COMMIT_V1
    def _commit_completion_with_evidence(
        self,
        *,
        rid,
        run_state,
        task,
        iteration,
        final,
        success_status="PASS",
    ):
        decision = (
            self._completion_evidence_gate(
                task=task,
                result=final,
            )
        )

        if not decision.complete:
            payload = decision.to_dict()

            self.store.event(
                rid,
                "completion_evidence_pending",
                payload,
            )

            pending = (
                "VERIFICATION_PENDING\n"
                + "MISSING_EVIDENCE="
                + ",".join(
                    decision.missing
                )
                + "\nIMPLEMENTATION_RESULT:\n"
                + str(final)
            )

            self.store.finish(
                rid,
                "VERIFICATION_PENDING",
                pending,
            )

            run_state.save({
                "role":
                    self.role,

                "task":
                    task,

                "status":
                    "VERIFICATION_PENDING",

                "iteration":
                    iteration,

                "result":
                    pending,

                "completion_evidence":
                    payload,
            })

            return (
                False,
                pending,
                decision,
            )

        self.store.event(
            rid,
            "completion_evidence_pass",
            decision.to_dict(),
        )

        self.store.finish(
            rid,
            success_status,
            final,
        )

        run_state.save({
            "role":
                self.role,

            "task":
                task,

            "status":
                success_status,

            "iteration":
                iteration,

            "result":
                final,

            "completion_evidence":
                decision.to_dict(),
        })

        return (
            True,
            final,
            decision,
        )



    # NEXUS700_MASTER_PROMPT_PREPROCESSOR_V1
    def _prepare_prompt_for_understanding(
        self,
        task,
    ):
        complexity = (
            analyze_prompt_complexity(
                task
            )
        )

        self._prompt_complexity = (
            complexity
        )

        if not complexity.milestone_mode:
            self._master_prompt = None
            self._milestone_plan = None
            self._milestone_index = None
            return task

        self._master_prompt = task

        if self.live:
            self.say(
                "[cyan]MASTER PROMPT: "
                "MILESTONE MODE[/cyan]"
            )

            self.say(
                "[cyan]MASTER PROMPT: "
                f"complexity={complexity.score}[/cyan]"
            )

        plan, metrics = (
            compile_master_prompt(
                task,
                progress=(
                    self.say
                    if self.live
                    else None
                ),
            )
        )

        self._milestone_plan = plan
        self._milestone_index = 0

        if not plan.milestones:
            raise RuntimeError(
                "NEXUS_MILESTONE_COMPILER_EMPTY"
            )

        if self.live:
            self.say(
                "[cyan]MASTER PROMPT: "
                f"{len(plan.milestones)} "
                "MILESTONES[/cyan]"
            )

            for item in plan.milestones:
                self.say(
                    "[cyan]"
                    + item.id
                    + ": "
                    + item.title
                    + "[/cyan]"
                )

        return milestone_execution_prompt(
            plan=plan,
            index=0,
        )


    def _preplanned_execution_brief(
        self,
        task,
    ):
        # NEXUS700_PREPLANNED_EXECUTION_BRIEF_V4
        return (
            "PREPLANNED TURN-CHECKLIST MILESTONE\n\n"
            "This execution prompt has already been planned.\n"
            "Execute it directly.\n"
            "Do not reinterpret it as a new user request.\n"
            "Do not perform another Understanding cycle.\n"
            "Do not perform another Planner cycle.\n"
            "A successful execution completes only the current milestone.\n"
            "Do not declare the master turn complete.\n\n"
            + str(task)
        )

    def run(
        self,
        task,
    ):
        # NEXUS700_MASTER_PROMPT_INTAKE_V2_RAW
        # NEXUS700_RAW_MILESTONE_EXECUTION_BOUNDARY_V1
        _raw_milestone_execution = (
            is_turn_checklist_execution_prompt(
                task
            )
        )

        _raw_final_verification = (
            is_final_verification_prompt(
                task
            )
        )

        _raw_preplanned_execution = (
            _raw_milestone_execution
            or _raw_final_verification
        )

        if not _raw_preplanned_execution:
            task = self._prepare_prompt_for_understanding(
                task
            )
        else:
            # This prompt was already planned by the persistent
            # Turn Checklist. Never feed it back into the master
            # prompt compiler.
            self._master_prompt = None
            self._milestone_plan = None
            self._milestone_index = None

        speed_route = (
            self._configure_speed_governor(
                task
            )
        )

        # NEXUS700_FAST_FIRST_DECISION
        fast_first = (
            FastFirstDecision(
                eligible=False,
                route="NORMAL",
                reason="preplanned_execution_bypass",
                read_only=(
                    self.capability_policy
                    == "READ_ONLY"
                ),
                deterministic_completion=False,
                skip_understanding_model=True,
                skip_planner_model=True,
                skip_completion_model=False,
                max_tool_calls=0,
                max_iterations=0,
            )
            if _raw_preplanned_execution
            else classify_fast_first(task)
        )
        self._fast_first_decision = fast_first
        self._fast_first_started_at = time.perf_counter()
        self._fast_first_tool_calls = 0

        if fast_first.eligible:
            self._understanding = None
            self._understanding_prompt = (
                "FAST_LOOKUP: deterministic read-only execution."
            )
            self._execution_plan = fast_lookup_contract(task)
            self._execution_plan_prompt = (
                "FAST_LOOKUP PLAN: use direct filesystem evidence; "
                "do not use memory as evidence; stop as soon as "
                "the requested facts have direct evidence."
            )
            if self.live:
                self.say(
                    "[green]NEXUS FAST-FIRST[/green] FAST_LOOKUP"
                )

        # NEXUS700_FAST_SKIP_REASONING
        # NEXUS700_FAST_ROUTER_V2_STATE_HOIST
        rid = self.store.new_run(
            self.role,
            task,
        )

        run_state = RunState(
            self.workspace,
            rid,
        )

        # NEXUS700_FAST_ROUTER_V2_PRE_UNDERSTANDING
        _zero_llm_started = time.perf_counter()
        _zero_llm_result = execute_fast_lookup(
            task=task,
            # NEXUS700_ZERO_LLM_WORKSPACE_FIX
            workspace=self.workspace,
        )

        if _zero_llm_result.handled:
            final = guard_final_answer(
                _zero_llm_result.answer
            )

            status = (
                "PASS"
                if final
                else "FAIL"
            )

            for _evidence in _zero_llm_result.evidence:
                self.store.event(
                    rid,
                    "fast_lookup_evidence",
                    _evidence.to_dict(),
                )

            self.store.event(
                rid,
                "zero_llm_fast_lookup",
                {
                    "route": "FAST_LOOKUP",
                    "director_model_calls": 0,
                    "understanding_model_calls": 0,
                    "planner_model_calls": 0,
                    "completion_model_calls": 0,
                    "filesystem_operations": (
                        _zero_llm_result.filesystem_operations
                    ),
                    "engine_elapsed_ms": (
                        _zero_llm_result.elapsed_ms
                    ),
                    "total_elapsed_ms": round(
                        (
                            time.perf_counter()
                            - _zero_llm_started
                        )
                        * 1000.0,
                        3,
                    ),
                },
            )

            self.store.finish(
                rid,
                status,
                final,
            )

            run_state.save({
                "role": self.role,
                "task": task,
                "status": status,
                "iteration": 0,
                "result": final,
                "route": "FAST_LOOKUP",
                "director_model_calls": 0,
            })

            if self.live:
                self.say(
                    "[green]NEXUS ZERO-LLM FAST LOOKUP[/green]"
                )

            return final

        # NEXUS700_PREPLANNED_REASONING_BYPASS_V5
        if _raw_preplanned_execution:
            # The persistent Turn Checklist already owns semantic
            # decomposition and planning. The canonical milestone
            # or final-verification prompt is authoritative here.
            #
            # Do not route preplanned execution through the general
            # Understanding or Planner models again. Doing so can
            # reinterpret an already-approved milestone and creates
            # a second structured-output failure boundary.
            self._understanding = None
            self._understanding_prompt = (
                self._preplanned_execution_brief(
                    task
                )
            )

            self._execution_plan = None
            self._execution_plan_prompt = ""
            self._task_contract = None
            self._execution_state = None

        else:
            if (
                understanding_enabled()
                and not fast_first.eligible
            ):
                try:
                    self._understanding = understand_task(
                        task,
                        progress=(
                            self.say
                            if self.live
                            else None
                        ),
                        run_critic=True,
                    )
                except UnderstandingError as exc:
                    raise RuntimeError(
                        "NEXUS_UNDERSTANDING_FAILED: "
                        + str(exc)
                    ) from exc
            
                self._understanding_prompt = (
                    render_executor_brief(
                        self._understanding
                    )
                )
            
                try:
                    self._execution_plan = plan_task(
                        user_request=task,
                        understanding=(
                            self._understanding
                        ),
                        progress=(
                            self.say
                            if self.live
                            else None
                        ),
                    )
                except PlanningError as exc:
                    raise RuntimeError(
                        "NEXUS_PLANNING_FAILED: "
                        + str(exc)
                    ) from exc
            
                self._execution_plan_prompt = (
                    render_plan_brief(
                        self._execution_plan
                    )
                )
            
                # NEXUS_TASK_STATE_V180
                self._task_contract = (
                    TaskContract
                    .from_understanding_and_plan(
                        understanding=self._understanding,
                        plan=self._execution_plan,
                    )
                )
            
                self._execution_state = (
                    ExecutionState.create(
                        self._task_contract
                    )
                )
            else:
                self._understanding = None
                self._understanding_prompt = ""
                self._execution_plan = None
                self._execution_plan_prompt = ""
                self._task_contract = None
                self._execution_state = None

        if self.live:
            self.say(
                "[cyan]NEXUS SPEED MODE:[/cyan] "
                + (
                    "SMART"
                    if smart_mode_enabled()
                    else "STRICT"
                )
            )

            if automatic_route_enforcement_enabled():
                self.say(
                    "[cyan]NEXUS ROUTE:[/cyan] "
                    + str(speed_route.name)
                    + " | ROUTE_SOURCE="
                    + route_source(task)
                    + " | discovery_budget="
                    + str(
                        speed_route.discovery_budget
                    )
                )

                if speed_route.name == "FAST_LOOKUP":
                    self.say(
                        "[cyan]CAPABILITIES:[/cyan] "
                        "ALLOW="
                        "list_files,search_files,"
                        "read_file,memory_search"
                        " | BLOCK="
                        "shell,process_start,"
                        "write_file,delegate_task,"
                        "memory_add,unknown"
                    )



    # NEXUS700_ZERO_LLM_AFTER_RUN_INITIALIZATION

        # NEXUS700_ZERO_LLM_FAST_LOOKUP
        # NEXUS700_FAST_ROUTER_V2_PRIMARY_GATE

        run_state.save({
            "role": self.role,
            "task": task,
            "status": "RUNNING",
            "iteration": 0,
            "speed_route": (
                speed_route.name
            ),
        })

        evidence_ledger = EvidenceLedger()

        tools = Tools(
            self.workspace,
            self.role,
            rid,
        )

        universal = UniversalTools(
            self.workspace,
            self.role,
        )


        include_mcp = bool(
            self.allowed_tools
            and any(
                str(name).startswith("mcp_")
                for name in self.allowed_tools
            )
        )

        registry, permissions = build_registry(
            self.workspace,
            self.role,
            rid,
            task_grants=self.allowed_tools,
            include_mcp=include_mcp,
        )
        if self.allowed_tools is not None:
            registry = registry.subset(
                self.allowed_tools
            )

        schemas = (
            registry.schemas()
            + self.delegation_schemas()
        )
        schemas = list(schemas)
        memory_store = MemoryStore(
            self.workspace
        )

        memory_hits = memory_store.search(
            task,
            limit=5,
        )

        memory_context = ""

        if memory_hits:
            memory_context = (
                "\n\nRELEVANT WORKSPACE MEMORY:\n"
                + "\n".join(
                    f"- {x['content']}"
                    for x in memory_hits
                )
            )

        system_content = (
            specialist_system_prompt(
                self.role
            )
            + self._understanding_prompt
            + self._execution_plan_prompt
            + (
                "\n\nNEXUS TASK CONTRACT:\n"
                + json.dumps(
                    self._task_contract.as_dict(),
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n\n"
                + render_execution_progress(
                    self._execution_state
                )
                + "\n\n"
                + (
                    "Use task_progress only when actual "
                    "evidence supports progress on an exact "
                    "listed requirement. A tool call alone "
                    "does not prove a requirement is DONE."
                )
                if self._task_contract is not None
                else ""
            )
        )

        messages = [
            {
                "role": "system",
                "content": system_content,
            },
            {
                "role": "user",
                "content": (
                    f"WORKSPACE:\n"
                    f"{self.workspace}\n\n"
                    f"TASK:\n"
                    f"{task}"
                    f"{memory_context}"
                ),
            },
        ]

        try:
            last_tool_signature = None
            repeated_tool_count = 0
            stagnation_warning_sent = False

            for iteration in range(
                1,
                int(
                    self.cfg[
                        "agents"
                    ][
                        "max_iterations"
                    ]
                )
                + 1,
            ):
                run_state.save({
                    "role": self.role,
                    "task": task,
                    "status": "RUNNING",
                    "iteration": iteration,
                })

                self.say(
                    f"[bold]"
                    f"{self.role.upper()}"
                    f"[/bold] "
                    f"iteration "
                    f"[bold]{iteration}[/bold]"
                )

                messages = (
                    self.context_engine
                    .compact_messages(
                        messages
                    )
                )

                self.watchdog.progress()

                inference_started = time.time()

                response = (
                    self.client
                    .chat
                    .completions
                    .create(
                        model=self.model,
                        messages=messages,
                        tools=schemas,
                        tool_choice="auto",
                        temperature=float(
                            self.cfg[
                                "runtime"
                            ][
                                "temperature"
                            ]
                        ),
                        max_tokens=(
                            max_output_tokens(
                                self.role,
                                self.cfg[
                                    "runtime"
                                ][
                                    "max_output_tokens"
                                ],
                            )
                        ),
                    )
                )

                self.timing_ledger.record(
                    "inference",
                    self.role,
                    inference_started,
                    time.time(),
                    {
                        "iteration": iteration,
                    },
                )

                msg = (
                    response
                    .choices[0]
                    .message
                )

                text = extract_text(
                    msg
                )

                calls = list(
                    msg.tool_calls
                    or []
                )

                assistant = {
                    "role": "assistant",
                    "content": text,
                }

                if calls:
                    assistant[
                        "tool_calls"
                    ] = [
                        {
                            "id": call.id,
                            "type": "function",
                            "function": {
                                "name": (
                                    call.function.name
                                ),
                                "arguments": (
                                    call.function.arguments
                                ),
                            },
                        }
                        for call in calls
                    ]

                messages.append(
                    assistant
                )

                if not calls:
                    # NEXUS700_FAST_DETERMINISTIC_COMPLETION
                    if fast_first.eligible:
                        _fast_entries = getattr(
                            evidence_ledger,
                            "entries",
                            [],
                        )
                        _fast_allow, _fast_reason = (
                            deterministic_fast_completion(
                                task=task,
                                evidence_entries=_fast_entries,
                            )
                        )
                        if _fast_allow:
                            # NEXUS700_FAST_FIRST_EVIDENCE_GUARD_V2
                            _fast_requirements = infer_evidence_requirements(
                                task=task,
                                understanding=(
                                    self._understanding
                                    if isinstance(
                                        self._understanding,
                                        dict,
                                    )
                                    else None
                                ),
                                plan=self._execution_plan,
                            )
                            if _fast_requirements.required_names():
                                _fast_allow = False
                                _fast_reason = (
                                    "MUTATING_TASK_REQUIRES_"
                                    "EVIDENCE_PIPELINE"
                                )
                            final = guard_final_answer(text)
                            status = (
                                "PASS"
                                if final == text
                                else "FAIL"
                            )
                            self.store.event(
                                rid,
                                "fast_first_completion",
                                {
                                    "allow": True,
                                    "reason": _fast_reason,
                                    "tool_calls": self._fast_first_tool_calls,
                                    "understanding_model_calls": 0,
                                    "planner_model_calls": 0,
                                    "completion_model_calls": 0,
                                    "elapsed_ms": round(
                                        (
                                            time.perf_counter()
                                            - self._fast_first_started_at
                                        )
                                        * 1000.0,
                                        3,
                                    ),
                                },
                            )
                            self.store.finish(
                                rid,
                                status,
                                final,
                            )
                            run_state.save({
                                "role": self.role,
                                "task": task,
                                "status": status,
                                "iteration": iteration,
                                "result": final,
                            })
                            if self.live:
                                self.say(
                                    "[green]FAST-FIRST COMPLETE[/green]"
                                )
                            return final

                    completion_allowed, completion_reason = (
                        self._speed_governor.completion_allowed(
                            route_name=self._speed_route.name
                        )
                    )

                    if not completion_allowed:
                        messages.append(
                            {
                                "role": "user",
                                "content": (
                                    "NEXUS COMPLETION GATE: "
                                    + str(completion_reason)
                                    + ". The FAST_LOOKUP does not yet "
                                    "have enough direct evidence. "
                                    "Continue focused read-only discovery. "
                                    "Inspect specific targets supplied by "
                                    "the user before finishing. Do not "
                                    "broaden the task."
                                ),
                            }
                        )

                        if self.live:
                            self.say(
                                "[yellow]COMPLETION GATE[/yellow] "
                                + str(completion_reason)
                            )

                        continue

                    # EXECUTION_COMPLETION_GATE_V173
                    #
                    # Speed completion protects route-specific
                    # evidence floors. This second gate protects
                    # the approved execution plan itself.
                    if self._execution_plan is not None:
                        try:
                            execution_decision = (
                                evaluate_execution_completion(
                                    task=task,
                                    plan=self._execution_plan,
                                    proposed_final=text,
                                    evidence_ledger=evidence_ledger,
                                    progress=(
                                        self.say
                                        if self.live
                                        else None
                                    ),
                                )
                            )
                        except ExecutionCompletionError as exc:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        "NEXUS EXECUTION COMPLETION "
                                        "GATE ERROR: "
                                        + str(exc)
                                        + ". Completion could not be "
                                        "verified. Continue focused work "
                                        "against the approved plan rather "
                                        "than assuming completion."
                                    ),
                                }
                            )

                            if self.live:
                                self.say(
                                    "[yellow]EXECUTION COMPLETION "
                                    "GATE[/yellow] ERROR"
                                )

                            continue

                        if not execution_decision.allow:
                            messages.append(
                                {
                                    "role": "user",
                                    "content": (
                                        render_continue_instruction(
                                            execution_decision
                                        )
                                    ),
                                }
                            )

                            # NEXUS700_CONTINUE_NORMALIZED
                            self.store.event(
                                rid,
                                "execution_completion_gate",
                                {
                                    "allow": False,
                                    "proposed_final_length": len(text or ""),
                                    "evidence_count": (
                                        len(evidence_ledger)
                                        if hasattr(
                                            evidence_ledger,
                                            "__len__",
                                        )
                                        else len(
                                            getattr(
                                                evidence_ledger,
                                                "entries",
                                                [],
                                            )
                                        )
                                    ),
                                    "iteration": iteration,
                                    "verdict": (
                                        execution_decision.verdict
                                    ),
                                    "summary": (
                                        execution_decision.summary
                                    ),
                                    "unmet_conditions": list(
                                        execution_decision
                                        .unmet_conditions
                                    ),
                                    "next_focus": list(
                                        execution_decision
                                        .next_focus
                                    ),
                                },
                            )

                            if self.live:
                                self.say(
                                    "[yellow]EXECUTION COMPLETION "
                                    "GATE[/yellow] CONTINUE"
                                )

                            continue
                        # NEXUS700_PASS_EVENT
                        self.store.event(
                            rid,
                            "execution_completion_gate",
                            {
                                "iteration": iteration,
                                "verdict": execution_decision.verdict,
                                "allow": True,
                                "summary": execution_decision.summary,
                                "unmet_conditions": list(
                                    execution_decision.unmet_conditions
                                ),
                                "next_focus": list(
                                    execution_decision.next_focus
                                ),
                                "proposed_final_length": len(text or ""),
                                "evidence_count": (
                                    len(evidence_ledger)
                                    if hasattr(
                                        evidence_ledger,
                                        "__len__",
                                    )
                                    else len(
                                        getattr(
                                            evidence_ledger,
                                            "entries",
                                            [],
                                        )
                                    )
                                ),
                            },
                        )

                        if self.live:
                            self.say(
                                "[green]EXECUTION COMPLETION GATE[/green] PASS"
                            )



                    final = (
                        guard_final_answer(
                            text
                        )
                    )

                    status = (
                        "PASS"
                        if final == text
                        else "FAIL"
                    )

                    # NEXUS700_NORMAL_EXECUTION_EVIDENCE_COMMIT_V1
                    _completion_ok, final, _completion_evidence = (
                        self._commit_completion_with_evidence(
                            rid=rid,
                            run_state=run_state,
                            task=task,
                            iteration=iteration,
                            final=final,
                            success_status="PASS",
                        )
                    )
                    if not _completion_ok:
                        return final

                    run_state.save({
                        "role": self.role,
                        "task": task,
                        "status": status,
                        "iteration": iteration,
                        "result": final,
                    })

                    evidence_summary = (
                        evidence_ledger.summary()
                    )

                    timing_summary = (
                        self.timing_ledger.summary()
                    )

                    final = (
                        final
                        + "\n\nNEXUS_EVIDENCE_SUMMARY="
                        + json.dumps(
                            evidence_summary,
                            ensure_ascii=False,
                        )
                        + "\nNEXUS_TIMING_SUMMARY="
                        + json.dumps(
                            timing_summary,
                            ensure_ascii=False,
                        )
                        + "\nNEXUS_SPEED_SUMMARY="
                        + json.dumps(
                            self._speed_governor.report(),
                            ensure_ascii=False,
                        )
                    )

                    # NEXUS700_SUCCESS_RETURN_EVENT
                    self.store.event(
                        rid,
                        "execution_success_return",
                        {
                            "iteration": iteration,
                            "proposed_final_length": len(text or ""),
                            "final_length": len(final or ""),
                            "status": status,
                        },
                    )

                    if self.live:
                        self.say(
                            "[green]EXECUTION SUCCESS RETURN[/green]"
                        )

                    return final

                for call in calls:
                    # NEXUS700_FAST_MEMORY_BLOCK
                    # NEXUS700_FAST_TOOL_COUNT
                    if fast_first.eligible:
                        self._fast_first_tool_calls += 1
                        if (
                            self._fast_first_tool_calls
                            > fast_first.max_tool_calls
                        ):
                            raise RuntimeError(
                                "NEXUS_FAST_FIRST_TOOL_BUDGET_EXCEEDED"
                            )

                    if (
                        fast_first.eligible
                        and call.function.name == "memory_add"
                    ):
                        if self.live:
                            self.say(
                                "[yellow]FAST-FIRST[/yellow] memory_add skipped"
                            )
                        continue

                    name = (
                        call.function.name
                    )

                    raw_arguments = (
                        call.function.arguments
                        or "{}"
                    )

                    try:
                        signature_args = json.loads(
                            raw_arguments
                        )
                    except Exception:
                        signature_args = (
                            raw_arguments
                        )

                    tool_signature = (
                        name,
                        json.dumps(
                            signature_args,
                            ensure_ascii=False,
                            sort_keys=True,
                            default=str,
                        ),
                    )

                    if (
                        tool_signature
                        == last_tool_signature
                    ):
                        repeated_tool_count += 1
                    else:
                        last_tool_signature = (
                            tool_signature
                        )
                        repeated_tool_count = 1
                        stagnation_warning_sent = False

                    if repeated_tool_count >= 4:
                        final = (
                            "NEXUS_STAGNATION_DETECTED:"
                            f"{name}:"
                            f"repeated={repeated_tool_count}"
                        )

                        self.store.finish(
                            rid,
                            "FAIL",
                            final,
                        )

                        run_state.save({
                            "role": self.role,
                            "task": task,
                            "status": "FAIL",
                            "iteration": iteration,
                            "result": final,
                        })

                        return final

                    if (
                        repeated_tool_count == 3
                        and not stagnation_warning_sent
                    ):
                        stagnation_warning_sent = True

                        output = (
                            "NEXUS_STAGNATION_WARNING: "
                            "This exact tool call has already "
                            "been requested repeatedly with "
                            "the same arguments. Do not call "
                            "it again. If the objective is "
                            "complete, return the final "
                            "assistant response now. If "
                            "durable session state changed, "
                            "include the required "
                            "NEXUS_STATE_UPDATE block directly "
                            "in that final response. Otherwise "
                            "choose a materially different "
                            "action."
                        )

                        evidence_ledger.record(
                            name,
                            signature_args,
                            output,
                        )

                        self.store.event(
                            rid,
                            "stagnation_warning",
                            {
                                "name": name,
                                "args": signature_args,
                                "repeated": (
                                    repeated_tool_count
                                ),
                            },
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": (
                                    call.id
                                ),
                                "content": output,
                            }
                        )

                        continue

                    if name not in {
                        "delegate_task",
                        "delegate_batch",
                    }:
                        self.tool_calls_used += 1

                        if (
                            self.tool_budget is not None
                            and self.tool_calls_used
                            > int(self.tool_budget)
                        ):
                            final = (
                                "NEXUS_TOOL_BUDGET_EXCEEDED="
                                f"{self.tool_budget}"
                            )

                            self.store.finish(
                                rid,
                                "FAIL",
                                final,
                            )

                            run_state.save({
                                "role": self.role,
                                "task": task,
                                "status": "FAIL",
                                "iteration": iteration,
                                "result": final,
                            })

                            return final

                    try:
                        args = json.loads(
                            call.function.arguments
                            or "{}"
                        )

                    except Exception:
                        args = {}

                    route_block = (
                        self._enforce_route_tool(
                            name=name,
                            arguments=args,
                        )
                    )

                    if route_block is not None:
                        output = route_block[
                            "output"
                        ]

                        self.store.event(
                            rid,
                            "route_policy",
                            {
                                "name": name,
                                "args": args,
                                "iteration": iteration,
                                "decision": "BLOCKED",
                                "reason": (
                                    route_block[
                                        "reason"
                                    ]
                                ),
                            },
                        )

                        evidence_ledger.record(
                            name,
                            args,
                            output,
                                                    outcome="BLOCKED_BY_POLICY",
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": (
                                    call.id
                                ),
                                "content": output,
                            }
                        )

                        if self.live:
                            self.say(
                                "[red]ROUTE BLOCK[/red] "
                                + str(
                                    route_block[
                                        "reason"
                                    ]
                                )
                            )

                        continue

                    speed_decision = (
                        self._speed_governor
                        .before_tool(
                            iteration=iteration,
                            name=name,
                            arguments=args,
                        )
                    )

                    if not speed_decision[
                        "allow"
                    ]:
                        output = (
                            self._speed_governor
                            .guidance(
                                speed_decision[
                                    "reason"
                                ]
                            )
                        )

                        self.store.event(
                            rid,
                            "speed_governor",
                            {
                                "name": name,
                                "args": args,
                                "iteration": (
                                    iteration
                                ),
                                "decision": (
                                    "SUPPRESSED"
                                ),
                                "reason": (
                                    speed_decision[
                                        "reason"
                                    ]
                                ),
                            },
                        )

                        evidence_ledger.record(
                            name,
                            args,
                            output,
                                                    outcome="BLOCKED_BY_POLICY",
                        )

                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": (
                                    call.id
                                ),
                                "content": output,
                            }
                        )

                        if self.live:
                            self.say(
                                "[cyan]"
                                "SPEED GOVERNOR"
                                "[/cyan] "
                                f"{name} "
                                f"{speed_decision['reason']}"
                            )

                        continue

                    self.say(
                        f"[yellow]TOOL[/yellow] "
                        f"{self.role}:{name} "
                        f"{json.dumps(args, ensure_ascii=False)[:600]}"
                    )

                    started = time.time()

                    # NEXUS700_CAPABILITY_DISPATCH_GATE_V1
                    try:
                        self._enforce_capability_tool(name)
                    except PermissionError as exc:
                        output = str(exc)
                        self.store.event(
                            rid,
                            "capability_policy",
                            {
                                "name": name,
                                "args": args,
                                "iteration": iteration,
                                "policy": self.capability_policy,
                                "decision": "BLOCKED",
                                "reason": output,
                            },
                        )
                        evidence_ledger.record(
                            name,
                            args,
                            output,
                                                    outcome="BLOCKED_BY_POLICY",
                        )
                        messages.append(
                            {
                                "role": "tool",
                                "tool_call_id": call.id,
                                "content": output,
                            }
                        )
                        if self.live:
                            self.say(
                                "[red]CAPABILITY BLOCK[/red] "
                                + output
                            )
                        continue
                    if name == "delegate_task":
                        output = (
                            self.delegate_one(
                                args["role"],
                                args["task"],
                            )
                        )

                    elif name == "delegate_batch":
                        output = (
                            self.delegate_batch(
                                args["tasks"]
                            )
                        )

                    else:
                        tool_def = registry.get(
                            name
                        )

                        if tool_def is None:
                            output = (
                                f"UNKNOWN_TOOL={name}"
                            )

                        else:
                            try:
                                permissions.enforce(
                                    tool_def.permission,
                                    name,
                                )

                                cached_output = (
                                    self.tool_cache.get(
                                        name,
                                        args,
                                    )
                                )

                                if cached_output is not None:
                                    output = cached_output

                                    self._speed_governor.record_tool_timing(
                                        name=name,
                                        duration=0.0,
                                        cached=True,
                                    )

                                    if self.live:
                                        self.say(
                                            f"[dim]TOOL CACHE HIT "
                                            f"{name}[/dim]"
                                        )

                                else:
                                    tool_started = time.time()

                                    output = registry.execute(
                                        name,
                                        args,
                                    )

                                    tool_finished = (
                                        time.time()
                                    )

                                    self.timing_ledger.record(
                                        "tool",
                                        name,
                                        tool_started,
                                        tool_finished,
                                        {
                                            "role": self.role,
                                        },
                                    )

                                    self._speed_governor.record_tool_timing(
                                        name=name,
                                        duration=(
                                            tool_finished
                                            - tool_started
                                        ),
                                        cached=False,
                                    )

                                    self.tool_cache.put(
                                        name,
                                        args,
                                        output,
                                    )

                            except PermissionError as e:
                                output = str(e)
                                evidence_ledger.record(
                                    name,
                                    args,
                                    output,
                                    outcome="EXECUTION_FAILED",
                                )
                                messages.append(
                                    {
                                        "role": "tool",
                                        "tool_call_id": call.id,
                                        "content": (
                                            self.context_engine
                                            .trim_tool_result(
                                                output
                                            )
                                        ),
                                    }
                                )
                                if self.live:
                                    self.say(
                                        "[red]TOOL PERMISSION FAILURE[/red] "
                                        + output
                                    )
                                continue

                    self._speed_governor.record_discovery_success(
                        tool_name=name
                    )

                    self._speed_governor.record_progress(
                        name
                    )

                    evidence_ledger.record(
                        name,
                        args,
                        output,
                    )

                    elapsed = (
                        time.time()
                        - started
                    )

                    self.say(
                        f"[green]"
                        f"TOOL DONE"
                        f"[/green] "
                        f"{name} "
                        f"{elapsed:.2f}s"
                    )

                    self.store.event(
                        rid,
                        "tool",
                        {
                            "name": name,
                            "args": args,
                            "elapsed": elapsed,
                            "output": str(
                                output
                            )[-20000:],
                        },
                    )

                    messages.append(
                        {
                            "role": "tool",
                            "tool_call_id": (
                                call.id
                            ),
                            "content": self.context_engine.trim_tool_result(output),
                        }
                    )

            final = (
                "MAX_ITERATIONS_REACHED"
            )

            self.store.finish(
                rid,
                "FAIL",
                final,
            )

            return final

        except KeyboardInterrupt:
            self.store.finish(
                rid,
                "INTERRUPTED",
                "KeyboardInterrupt",
            )

            raise

        except Exception as e:
            final = (
                "AGENT_EXCEPTION="
                f"{type(e).__name__}: {e}"
            )

            self.store.finish(
                rid,
                "FAIL",
                final,
            )

            return final
