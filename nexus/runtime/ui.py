from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text


console = Console()


def banner(
    title,
    subtitle=None,
):
    body = Text()

    body.append(
        title,
        style="bold cyan",
    )

    if subtitle:
        body.append(
            "\n"
        )

        body.append(
            subtitle,
            style="dim",
        )

    console.print(
        Panel(
            body,
            border_style="cyan",
            padding=(
                1,
                2,
            ),
        )
    )


def status_table(
    status,
):
    table = Table(
        title="Nexus Status",
        show_header=False,
        expand=True,
    )

    table.add_column(
        "Field",
        style="bold",
        width=20,
    )

    table.add_column(
        "Value",
    )

    def add(
        label,
        value,
    ):
        table.add_row(
            label,
            str(
                value
                if value not in (
                    None,
                    "",
                    [],
                )
                else "—"
            ),
        )

    add(
        "Workspace",
        status.workspace,
    )

    add(
        "Objective",
        status.current_objective,
    )

    add(
        "Run",
        status.run_id,
    )

    add(
        "Run status",
        status.run_status,
    )

    add(
        "Active agent",
        status.active_agent,
    )

    add(
        "Current step",
        status.current_step,
    )

    add(
        "Progress",
        status.progress,
    )

    add(
        "Last tool",
        status.last_tool,
    )

    add(
        "Retries",
        status.retries,
    )

    add(
        "Evidence",
        status.evidence_count,
    )

    add(
        "Blockers",
        ", ".join(
            status.blockers
        )
        if status.blockers
        else "none",
    )

    add(
        "Jobs running",
        status.jobs_running,
    )

    add(
        "Jobs pending",
        status.jobs_pending,
    )

    add(
        "Jobs failed",
        status.jobs_failed,
    )

    add(
        "Resumable runs",
        status.resumable_runs,
    )

    return table


def success(
    message,
):
    console.print(
        f"[bold green]✓[/bold green] "
        f"{message}"
    )


def warning(
    message,
):
    console.print(
        f"[bold yellow]![/bold yellow] "
        f"{message}"
    )


def failure(
    message,
):
    console.print(
        f"[bold red]✗[/bold red] "
        f"{message}"
    )
