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
    def __init__(
        self,
        cfg,
        workspace,
        role="director",
        depth=0,
        live=True,
        allowed_tools=None,
        tool_budget=None,
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

    def run(
        self,
        task,
    ):
        rid = self.store.new_run(
            self.role,
            task,
        )

        run_state = RunState(
            self.workspace,
            rid,
        )

        run_state.save({
            "role": self.role,
            "task": task,
            "status": "RUNNING",
            "iteration": 0,
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
                    )

                    return final

                for call in calls:
                    name = (
                        call.function.name
                    )

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

                    self.say(
                        f"[yellow]TOOL[/yellow] "
                        f"{self.role}:{name} "
                        f"{json.dumps(args, ensure_ascii=False)[:600]}"
                    )

                    started = time.time()

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

                                    self.timing_ledger.record(
                                        "tool",
                                        name,
                                        tool_started,
                                        time.time(),
                                        {
                                            "role": self.role,
                                        },
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
