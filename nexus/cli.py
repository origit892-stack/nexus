import importlib.metadata
import sys
from pathlib import Path
import json
import yaml

import typer

from rich.console import Console
from rich.table import Table

from . import __version__

from .acceptance import (
    Criterion,
    Evidence,
    verify,
)

from .agent import Agent
from .projects.registry import ProjectRegistry
from .sessions.store import SessionStore
from .sessions.runner import run_session
from .ui.app import launch_home
from .runtime.status import collect_status
from .runtime.ui import banner as ui_banner, status_table, console as ui_console
from .runtime.readiness_cli import check_runtime, require_runtime

from .config import (
    effective_config,
    find_workspace,
    global_config,
    save_yaml,
)

from .hardware import detect

from .providers import ollama

from .store import Store
from nexus.runtime.terminal_host import prepare_terminal


console = Console()

app = typer.Typer(
    invoke_without_command=True,
    no_args_is_help=False,
    help=(
        "Nexus - local-first autonomous "
        "multi-agent runtime"
    ),
)


project_app = typer.Typer(
    help="Manage Nexus projects."
)

session_app = typer.Typer(
    help="Manage project sessions."
)

app.add_typer(
    project_app,
    name="project",
)

app.add_typer(
    session_app,
    name="session",
)


@app.callback(
    invoke_without_command=True
)
def nexus_home(
    ctx: typer.Context,
):
    """Nexus project and session home."""

    if (
        ctx.invoked_subcommand
        is None
    ):
        launch_home()



models_app = typer.Typer()
providers_app = typer.Typer()
acceptance_app = typer.Typer()

app.add_typer(
    models_app,
    name="models",
)

app.add_typer(
    providers_app,
    name="providers",
)

app.add_typer(
    acceptance_app,
    name="acceptance",
)


def manifest():
    path = (
        Path(__file__)
        .resolve()
        .parent
        .parent
        / "manifests"
        / "models.yaml"
    )

    with path.open(
        "r",
        encoding="utf-8",
    ) as f:
        return yaml.safe_load(
            f
        )


def ensure_model():
    cfg = global_config()

    if (
        cfg.get("provider")
        and cfg.get("model")
        and cfg.get("base_url")
    ):
        return cfg

    console.print(
        "[bold cyan]"
        "Nexus first-run setup"
        "[/bold cyan]"
    )

    h = detect()

    console.print(
        f"Hardware: {h['chip']}"
    )

    console.print(
        f"Memory: {h['memory_gb']} GB"
    )

    console.print(
        "No model provider configured."
    )

    console.print(
        "Using default local provider: Ollama"
    )

    result = ollama.bootstrap(
        cfg,
        manifest(),
    )

    console.print(
        f"Hardware profile: "
        f"{result['profile_name']}"
    )

    console.print(
        f"Base model: "
        f"{result['base_model']}"
    )

    console.print(
        f"Nexus model: "
        f"{result['model']}"
    )

    console.print(
        f"Context: "
        f"{result['profile']['context_length']}"
    )

    console.print(
        f"Benchmark: "
        f"{result['benchmark']['seconds']}s"
    )

    console.print(
        "[bold green]"
        "NEXUS_READY"
        "[/bold green]"
    )

    return global_config()


def require_workspace(
    path=None,
):
    if path:
        root = (
            Path(path)
            .expanduser()
            .resolve()
        )

    else:
        root = find_workspace()

    if root is None:
        root = (
            Path.cwd()
            .resolve()
        )

        if not (
            root
            / ".nexus"
            / "workspace.yaml"
        ).exists():
            raise typer.BadParameter(
                "No Nexus workspace found. "
                "Run: nexus init"
            )

    return root




@project_app.command("list")
def project_list():
    """List registered Nexus projects exactly once."""

    registry = ProjectRegistry()
    projects = registry.list()
    active = registry.active()

    for project in projects:
        marker = (
            "*"
            if (
                active is not None
                and active.id == project.id
            )
            else " "
        )

        typer.echo(
            f"{marker} "
            f"{project.name}\t"
            f"{project.path}"
        )



@project_app.command("add")
def project_add(
    path: str | None = typer.Argument(
        None
    ),
    name: str | None = typer.Option(
        None,
        "--name",
    ),
    choose: bool = typer.Option(
        False,
        "--choose",
    ),
):
    """Register a project directory."""

    registry = ProjectRegistry()

    resolved = path

    if choose or not resolved:
        resolved = (
            registry
            .choose_folder_macos()
        )

    if not resolved:
        raise typer.Exit(
            code=1
        )

    project = registry.add(
        resolved,
        name,
    )

    typer.echo(
        f"PROJECT_ADDED={project.name}"
    )

    typer.echo(
        f"PROJECT_PATH={project.path}"
    )


@project_app.command("use")
def project_use(
    project: str,
):
    """Set the active project."""

    selected = (
        ProjectRegistry()
        .use(
            project
        )
    )

    typer.echo(
        f"ACTIVE_PROJECT={selected.name}"
    )

    typer.echo(
        f"PROJECT_PATH={selected.path}"
    )


@project_app.command("remove")
def project_remove(
    project: str,
):
    """Remove a project from the registry."""

    removed = (
        ProjectRegistry()
        .remove(
            project
        )
    )

    if not removed:
        raise typer.Exit(
            code=1
        )

    typer.echo(
        "PROJECT_REMOVED=PASS"
    )


@session_app.command("list")
def session_list(
    project: str | None = typer.Option(
        None,
        "--project",
    ),
):
    """List sessions in the selected project."""

    registry = ProjectRegistry()

    selected = (
        registry.get(
            project
        )
        if project
        else registry.active()
    )

    if selected is None:
        typer.echo(
            "NO_ACTIVE_PROJECT"
        )

        raise typer.Exit(
            code=1
        )

    store = SessionStore(
        selected.path
    )

    for session in store.list():
        typer.echo(
            f"{session.id}\t"
            f"{session.status}\t"
            f"{session.title}"
        )


@session_app.command("new")
def session_new(
    objective: str,
    title: str | None = typer.Option(
        None,
        "--title",
    ),
    project: str | None = typer.Option(
        None,
        "--project",
    ),
    run_now: bool = typer.Option(
        True,
        "--run/--no-run",
    ),
):
    """Create a session in the selected project."""

    registry = ProjectRegistry()

    selected = (
        registry.get(
            project
        )
        if project
        else registry.active()
    )

    if selected is None:
        typer.echo(
            "NO_ACTIVE_PROJECT"
        )

        raise typer.Exit(
            code=1
        )

    store = SessionStore(
        selected.path
    )

    session = store.create(
        objective,
        title,
    )

    typer.echo(
        f"SESSION_ID={session.id}"
    )

    if run_now:
        run_session(
            selected.path,
            session.id,
        )


@session_app.command("resume")
def session_resume(
    session_id: str,
    project: str | None = typer.Option(
        None,
        "--project",
    ),
):
    """Resume/run an existing project session."""

    registry = ProjectRegistry()

    selected = (
        registry.get(
            project
        )
        if project
        else registry.active()
    )

    if selected is None:
        typer.echo(
            "NO_ACTIVE_PROJECT"
        )

        raise typer.Exit(
            code=1
        )

    return run_session(
        selected.path,
        session_id,
    )


@session_app.command("delete")
def session_delete(
    session_id: str,
    project: str | None = typer.Option(
        None,
        "--project",
    ),
):
    """Delete a saved project session."""

    registry = ProjectRegistry()

    selected = (
        registry.get(
            project
        )
        if project
        else registry.active()
    )

    if selected is None:
        raise typer.Exit(
            code=1
        )

    removed = (
        SessionStore(
            selected.path
        )
        .delete(
            session_id
        )
    )

    if not removed:
        raise typer.Exit(
            code=1
        )

    typer.echo(
        "SESSION_DELETED=PASS"
    )




@app.command()
def init(
    path: str = typer.Argument(
        ".",
        help="Workspace directory to initialize.",
    ),
):
    root = (
        Path(path)
        .expanduser()
        .resolve()
    )

    if not root.is_dir():
        raise typer.BadParameter(
            f"Directory not found: {root}"
        )

    d = (
        root
        / ".nexus"
    )

    d.mkdir(
        parents=True,
        exist_ok=True,
    )

    save_yaml(
        d / "workspace.yaml",
        {
            "name": root.name,
            "workspace_root": str(
                root
            ),
            "runtime": {},
            "permissions": {
                "sandbox": True,
                "director_read_only": True,
                "architect_read_only": True,
                "qa_read_only": True,
                "coder_single_writer": True,
                "checkpoint_before_write": True,
            },
        },
    )

    rules = (
        d
        / "rules.md"
    )

    if not rules.exists():
        rules.write_text(
            "# Nexus Workspace Rules\n\n"
            "- Stay inside this workspace.\n"
            "- Never fabricate PASS.\n"
            "- Create checkpoints before writes.\n"
            "- A stub/mock/placeholder never "
            "satisfies a criterion requiring "
            "a real implementation.\n"
        )

    (
        d
        / "checkpoints"
    ).mkdir(
        exist_ok=True
    )

    console.print(
        "[green]"
        "NEXUS_WORKSPACE_INITIALIZED=PASS"
        "[/green]"
    )

    console.print(
        f"ROOT={root}"
    )


def _chat(
    workspace,
):
    cfg = effective_config(
        workspace
    )

    console.print(
        "[bold cyan]"
        "Nexus Interactive"
        "[/bold cyan]"
    )

    console.print(
        f"Workspace: {workspace}"
    )

    console.print(
        f"Model: {cfg['model']}"
    )

    console.print(
        "Paste/type multiline prompts."
    )

    console.print(
        "Enter /send to execute."
    )

    console.print(
        "/clear clears the buffer."
    )

    console.print(
        "/exit quits."
    )

    buffer = []

    while True:
        try:
            line = console.input(
                "[bold]"
                "nexus> "
                "[/bold]"
            )

        except (
            EOFError,
            KeyboardInterrupt,
        ):
            break

        if line.strip() in {
            "/exit",
            "/quit",
        }:
            break

        if line.strip() == "/clear":
            buffer.clear()

            console.print(
                "Prompt buffer cleared."
            )

            continue

        if line.strip() == "/send":
            if not buffer:
                console.print(
                    "Prompt buffer is empty."
                )

                continue

            task = "\n".join(
                buffer
            )

            buffer.clear()

            result = Agent(
                cfg,
                str(workspace),
                role="director",
                live=True,
            ).run(
                task
            )

            console.print(
                "\n[bold cyan]"
                "FINAL"
                "[/bold cyan]"
            )

            console.print(
                result
            )

            continue

        buffer.append(
            line
        )

        console.print(
            "[dim]"
            f"buffered lines="
            f"{len(buffer)} "
            f"(/send to run)"
            "[/dim]"
        )


@app.command()
def chat(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    ensure_model()

    _chat(
        require_workspace(
            workspace
        )
    )


@app.command()
def run(
    task: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    ensure_model()

    root = require_workspace(
        workspace
    )

    require_runtime(
        str(root)
    )

    result = Agent(
        effective_config(
            root
        ),
        str(root),
        role="director",
        live=True,
    ).run(
        task
    )

    console.print(
        "\n[bold cyan]"
        "FINAL"
        "[/bold cyan]"
    )

    console.print(
        result
    )




@app.command()
def status(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
    ),
):
    """Show current Nexus runtime and execution status."""

    root = (
        Path(workspace).expanduser().resolve()
        if workspace
        else find_workspace()
    )

    if root is None:
        state = collect_status(
            str(Path.cwd().resolve())
        )
        state.workspace = None
    else:
        state = collect_status(
            str(root)
        )

    if json_output:
        typer.echo(
            json.dumps(
                state.as_dict(),
                ensure_ascii=False,
                indent=2,
            )
        )
        return

    ui_banner(
        "NEXUS",
        "Autonomous Agent Runtime",
    )

    ui_console.print(
        status_table(
            state
        )
    )

@app.command()
def ready(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    """Check whether the full Nexus runtime is ready."""

    root = (
        Path(workspace).expanduser().resolve()
        if workspace
        else find_workspace()
    )

    readiness, lines = check_runtime(
        str(root)
    )

    for line in lines:
        typer.echo(line)

    if not readiness.ready:
        raise typer.Exit(
            code=2
        )

@app.command()
def doctor(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    cfg = ensure_model()

    h = detect()

    checks = [
        (
            "HARDWARE",
            True,
            (
                f"{h['chip']} / "
                f"{h['memory_gb']}GB"
            ),
        ),
        (
            "PROVIDER",
            cfg.get(
                "provider"
            ) == "ollama",
            str(
                cfg.get(
                    "provider"
                )
            ),
        ),
        (
            "MODEL",
            bool(
                cfg.get(
                    "model"
                )
            ),
            str(
                cfg.get(
                    "model"
                )
            ),
        ),
        (
            "OLLAMA_API",
            ollama.api_alive(),
            "http://127.0.0.1:11434",
        ),
    ]

    result = verify(
        Criterion(
            "real optimizer",
            requires_real_implementation=True,
            requires_execution=True,
        ),
        Evidence(
            description=(
                "Optimizer stub by design"
            ),
            command=(
                "python optimize.py"
            ),
            exit_code=0,
            text=(
                "No actual optimization needed; "
                "stub."
            ),
        ),
    )

    checks.append(
        (
            "STUB_REJECTION",
            not result.passed,
            result.reason,
        )
    )

    table = Table()

    table.add_column(
        "Check"
    )

    table.add_column(
        "Status"
    )

    table.add_column(
        "Info"
    )

    failed = 0

    for name, ok, info in checks:
        if not ok:
            failed += 1

        table.add_row(
            name,
            (
                "[green]PASS[/green]"
                if ok
                else "[red]FAIL[/red]"
            ),
            str(info)[:120],
        )

    console.print(
        table
    )

    if failed:
        console.print(
            "[red]"
            "NEXUS_DOCTOR=FAIL"
            "[/red]"
        )

        raise typer.Exit(
            1
        )

    runtime_root = None
    if workspace:
        runtime_root = Path(workspace).expanduser().resolve()
    else:
        try:
            runtime_root = find_workspace()
        except Exception:
            runtime_root = None

    if runtime_root is not None:
        readiness, readiness_output = check_runtime(
            str(runtime_root)
        )
        for readiness_line in readiness_output:
            typer.echo(readiness_line)
        if not readiness.ready:
            raise typer.Exit(code=2)
    else:
        typer.echo("NEXUS_RUNTIME_REQUIREMENTS=SKIPPED_NO_WORKSPACE")

    console.print(
        "[bold green]"
        "NEXUS_DOCTOR=PASS"
        "[/bold green]"
    )


@models_app.command(
    "list"
)
def models_list():
    ollama.ensure_server()

    for model in ollama.list_models():
        console.print(
            model
        )


@models_app.command(
    "auto"
)
def models_auto():
    result = ollama.bootstrap(
        global_config(),
        manifest(),
    )

    console.print_json(
        json.dumps(
            result,
            default=str,
        )
    )


@models_app.command(
    "benchmark"
)
def models_benchmark():
    cfg = ensure_model()

    console.print_json(
        json.dumps(
            ollama.benchmark(
                cfg["model"]
            )
        )
    )


@models_app.command(
    "doctor"
)
def models_doctor():
    doctor()


@models_app.command(
    "install"
)
def models_install(
    family: str = "qwen",
):
    if family.lower() != "qwen":
        raise typer.BadParameter(
            "V3 automatic installation "
            "currently supports qwen."
        )

    models_auto()


@providers_app.command(
    "list"
)
def providers_list():
    cfg = global_config()

    table = Table()

    table.add_column(
        "Provider"
    )

    table.add_column(
        "Status"
    )

    table.add_row(
        "ollama",
        (
            "ACTIVE"
            if cfg.get(
                "provider"
            ) == "ollama"
            else "AVAILABLE"
        ),
    )

    table.add_row(
        "openai",
        "OPTIONAL / NOT REQUIRED",
    )

    table.add_row(
        "anthropic",
        "OPTIONAL / NOT REQUIRED",
    )

    table.add_row(
        "openrouter",
        "OPTIONAL / NOT REQUIRED",
    )

    console.print(
        table
    )


@acceptance_app.command(
    "verify"
)
def acceptance_verify(
    name: str = typer.Option(
        ...,
        "--name",
    ),
    real: bool = typer.Option(
        False,
        "--real",
    ),
    executed: bool = typer.Option(
        False,
        "--executed",
    ),
    evidence: str = typer.Option(
        "",
        "--evidence",
    ),
    command: str | None = typer.Option(
        None,
        "--command",
    ),
    exit_code: int | None = typer.Option(
        None,
        "--exit-code",
    ),
    artifact: list[str] = typer.Option(
        None,
        "--artifact",
    ),
):
    result = verify(
        Criterion(
            name,
            real,
            executed,
        ),
        Evidence(
            evidence,
            command,
            exit_code,
            artifact or [],
            evidence,
        ),
    )

    if result.passed:
        console.print(
            "[green]"
            "ACCEPTANCE=PASS"
            "[/green]"
        )

    else:
        console.print(
            "[red]"
            "ACCEPTANCE=FAIL"
            "[/red]"
        )

    console.print(
        f"REASON={result.reason}"
    )

    if not result.passed:
        raise typer.Exit(
            1
        )


@app.command()
def runs(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    root = require_workspace(
        workspace
    )

    table = Table()

    table.add_column(
        "Run"
    )

    table.add_column(
        "Role"
    )

    table.add_column(
        "Status"
    )

    table.add_column(
        "Task"
    )

    for row in Store(
        root
    ).recent():
        table.add_row(
            *map(
                str,
                row,
            )
        )

    console.print(
        table
    )


@app.command()
def config():
    console.print_json(
        json.dumps(
            global_config()
        )
    )


tools_app = typer.Typer()
mcp_app = typer.Typer()
memory_app = typer.Typer()
plugins_app = typer.Typer()

app.add_typer(
    tools_app,
    name="tools",
)

app.add_typer(
    mcp_app,
    name="mcp",
)

app.add_typer(
    memory_app,
    name="memory",
)

app.add_typer(
    plugins_app,
    name="plugins",
)


@tools_app.command("list")
def tools_list():
    from .runtime.tool_factory import (
        build_registry,
    )

    root = require_workspace()

    registry, _ = build_registry(
        str(root),
        "director",
        "cli_tools_list",
    )

    table = Table()

    table.add_column("Tool")
    table.add_column("Permission")
    table.add_column("Source")

    for item in registry.describe():
        table.add_row(
            item["name"],
            item["permission"],
            item["source"],
        )

    console.print(table)


@mcp_app.command("list")
def mcp_list_cmd():
    from .runtime.mcp_manager import (
        list_servers,
    )

    servers = list_servers()

    if not servers:
        console.print(
            "No MCP servers configured."
        )

        return

    table = Table()

    table.add_column("Name")
    table.add_column("Command")
    table.add_column("Enabled")

    for name, server in servers.items():
        table.add_row(
            name,
            server.get(
                "command",
                "",
            ),
            str(
                server.get(
                    "enabled",
                    True,
                )
            ),
        )

    console.print(table)


@mcp_app.command("add")
def mcp_add_cmd(
    name: str,
    command: str,
    args: list[str] = typer.Argument(None),
):
    from .runtime.mcp_manager import (
        add_server,
    )

    result = add_server(
        name,
        command,
        args or [],
    )

    console.print_json(
        json.dumps(result)
    )


@mcp_app.command("test")
def mcp_test_cmd(
    name: str,
):
    from .runtime.mcp_manager import (
        test_server,
    )

    console.print(
        test_server(name)
    )


@memory_app.command("add")
def memory_add_cmd(
    content: str,
    kind: str = "general",
):
    from .memory import MemoryStore

    root = require_workspace()

    store = MemoryStore(
        root
    )

    mid = store.add(
        content,
        kind,
    )

    console.print(
        f"MEMORY_ADDED={mid}"
    )


@memory_app.command("search")
def memory_search_cmd(
    query: str,
    limit: int = 10,
):
    from .memory import MemoryStore

    root = require_workspace()

    store = MemoryStore(
        root
    )

    console.print_json(
        json.dumps(
            store.search(
                query,
                limit,
            ),
            ensure_ascii=False,
        )
    )


@memory_app.command("list")
def memory_list_cmd(
    limit: int = 30,
):
    from .memory import MemoryStore

    root = require_workspace()

    store = MemoryStore(
        root
    )

    table = Table()

    table.add_column("ID")
    table.add_column("Time")
    table.add_column("Kind")
    table.add_column("Content")

    for row in store.list(limit):
        table.add_row(
            *map(str, row)
        )

    console.print(table)


@plugins_app.command("list")
def plugins_list_cmd():
    from .plugins import discover

    paths = discover()

    if not paths:
        console.print(
            "No Nexus plugins installed."
        )

        return

    for path in paths:
        console.print(path)


@app.command()
def permissions():
    from .runtime.permissions import (
        ROLE_MAX,
    )

    table = Table()

    table.add_column("Role")
    table.add_column("Maximum Permission")

    for role, level in sorted(
        ROLE_MAX.items()
    ):
        table.add_row(
            role,
            level,
        )

    console.print(table)


@app.command()
def resume(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    root = require_workspace(
        workspace
    )

    store = Store(
        root
    )

    run = store.get_run(
        run_id
    )

    if not run:
        console.print(
            f"[red]RUN_NOT_FOUND={run_id}[/red]"
        )
        raise typer.Exit(1)

    cfg = effective_config(
        root
    )

    console.print(
        f"RESUMING_RUN={run_id}"
    )

    console.print(
        f"PREVIOUS_STATUS={run['status']}"
    )

    task = (
        run["task"]
        + "\n\n"
        + "Resume this task from the previous "
          "interrupted/failed execution. "
          "Inspect current workspace state and "
          "do not redo completed work unnecessarily."
    )

    result = Agent(
        cfg,
        str(root),
        role="director",
        live=True,
    ).run(task)

    console.print(
        "\n[bold cyan]FINAL[/bold cyan]"
    )

    console.print(result)


@app.command()
def logs(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
    follow: bool = typer.Option(
        False,
        "--follow",
    ),
):
    import time

    root = require_workspace(
        workspace
    )

    store = Store(
        root
    )

    seen = 0

    while True:
        events = store.events_for_run(
            run_id
        )

        for event in events[
            seen:
        ]:
            event_id, ts, kind, payload = event

            console.print(
                f"[dim]{event_id}[/dim] "
                f"[cyan]{kind}[/cyan] "
                f"{payload}"
            )

        seen = len(events)

        if not follow:
            break

        time.sleep(1)


# ============================================================
# Nexus V7 durable jobs
# ============================================================

jobs_app = typer.Typer()

app.add_typer(
    jobs_app,
    name="jobs",
)


@jobs_app.command("create")
def jobs_create(
    name: str = typer.Option(
        ...,
        "--name",
    ),
    command: list[str] = typer.Option(
        ...,
        "--command",
    ),
    retries: int = typer.Option(
        2,
        "--retries",
    ),
    timeout: int = typer.Option(
        900,
        "--timeout",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs import JobStore

    root = require_workspace(
        workspace
    )

    store = JobStore(
        root
    )

    steps = [
        {
            "name": f"step-{i+1}",
            "command": cmd,
        }
        for i, cmd
        in enumerate(command)
    ]

    jid = store.create_job(
        name,
        steps,
        max_retries=retries,
        timeout_seconds=timeout,
    )

    console.print(
        f"JOB_CREATED={jid}"
    )


@jobs_app.command("run")
def jobs_run(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs import JobRunner

    root = require_workspace(
        workspace
    )

    runner = JobRunner(
        root
    )

    result = runner.run_job(
        run_id
    )

    console.print(
        f"JOB_RESULT={result}"
    )

    if result != "PASS":
        raise typer.Exit(1)


@jobs_app.command("resume")
def jobs_resume(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs import JobRunner

    root = require_workspace(
        workspace
    )

    runner = JobRunner(
        root
    )

    result = runner.run_job(
        run_id
    )

    console.print(
        f"JOB_RESUME_RESULT={result}"
    )

    if result != "PASS":
        raise typer.Exit(1)


@jobs_app.command("cancel")
def jobs_cancel(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs import JobStore

    root = require_workspace(
        workspace
    )

    store = JobStore(
        root
    )

    store.request_cancel(
        run_id
    )

    console.print(
        f"JOB_CANCEL_REQUESTED={run_id}"
    )


@jobs_app.command("list")
def jobs_list(
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
    limit: int = 30,
):
    from .jobs import JobStore

    root = require_workspace(
        workspace
    )

    store = JobStore(
        root
    )

    table = Table()

    table.add_column("ID")
    table.add_column("Time")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Attempts")
    table.add_column("Error")

    for row in store.list_jobs(
        limit
    ):
        table.add_row(
            *map(str, row)
        )

    console.print(table)


@jobs_app.command("show")
def jobs_show(
    run_id: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs import JobStore

    root = require_workspace(
        workspace
    )

    store = JobStore(
        root
    )

    job = store.get_job(
        run_id
    )

    if not job:
        console.print(
            f"JOB_NOT_FOUND={run_id}"
        )

        raise typer.Exit(1)

    console.print_json(
        json.dumps(
            {
                "job": job,
                "steps": (
                    store.get_steps(
                        run_id
                    )
                ),
            },
            default=str,
        )
    )


@jobs_app.command("worker")
def jobs_worker(
    once: bool = typer.Option(
        False,
        "--once",
    ),
    job: str | None = typer.Option(
        None,
        "--job",
    ),
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    from .jobs.worker import (
        run_worker,
    )

    root = require_workspace(
        workspace
    )

    run_worker(
        root,
        once=once,
        job_id=job,
    )


@app.command()
def auto(
    objective: str,
    workspace: str | None = typer.Option(
        None,
        "--workspace",
    ),
):
    """
    Plan and execute a task through the V8 autonomous DAG runtime.
    """

    from .orchestration.autonomous import (
        AutonomousOrchestrator,
    )

    root = require_workspace(
        workspace
    )

    require_runtime(
        str(root)
    )

    runtime = AutonomousOrchestrator(
        str(root),
        live=True,
    )

    result = runtime.run(
        objective
    )

    console.print_json(
        json.dumps(
            result,
            ensure_ascii=False,
            default=str,
        )
    )

    if result["status"] != "PASS":
        raise typer.Exit(1)


def main():
    """
    Nexus executable entrypoint.

    nexus
        -> interactive Projects / Sessions UI

    nexus --version
        -> version output

    nexus <command> ...
        -> Typer CLI
    """

    args = sys.argv[1:]

    if not args:
        prepare_terminal()
        return launch_home()

    if args in (
        ["--version"],
        ["-V"],
    ):
        try:
            version = importlib.metadata.version(
                "nexus"
            )
        except Exception:
            try:
                from nexus import __version__
                version = __version__
            except Exception:
                version = "1.1"

        print(
            f"Nexus {version}"
        )

        return None

    return app()


if __name__ == "__main__":
    main()
