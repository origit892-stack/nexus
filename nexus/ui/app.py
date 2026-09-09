from __future__ import annotations

import asyncio
from pathlib import Path

from textual import on, work
from textual.app import (
    App,
    ComposeResult,
)
from textual.binding import Binding
from textual.containers import (
    Container,
    Horizontal,
    Vertical,
)
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Footer,
    Header,
    Input,
    Label,
    ListItem,
    ListView,
    Markdown,
    Static,
)

from nexus.projects.registry import (
    ProjectRegistry,
)
from nexus.sessions.store import (
    SessionStore,
)
from nexus.sessions.runner import (
    run_session,
    continue_session,
)
from nexus.sessions.agent_shell import run_agent_shell


CSS = """
Screen {
    background: #080b10;
    color: #edf4ff;
}

Header {
    background: #0d1420;
    color: #e7f3ff;
}

Footer {
    background: #0d1420;
}

#shell {
    height: 1fr;
}

#sidebar {
    width: 30;
    min-width: 26;
    background: #0b1018;
    border-right: solid #26374d;
    padding: 1;
}

.brand {
    height: 4;
    padding: 1 1;
    color: #9ad8ff;
    text-style: bold;
}

.section-title {
    color: #6c8baa;
    text-style: bold;
    margin-top: 1;
    margin-bottom: 1;
}

#project-list,
#session-list {
    border: none;
    background: transparent;
}

ListItem {
    padding: 1 1;
    margin-bottom: 1;
    background: #0f1723;
}

ListItem:hover {
    background: #162439;
}

ListItem.-highlight {
    background: #18314d;
    border-left: thick #4ab8ff;
}


#session-list {
    height: 1fr;
    min-height: 8;
    padding: 0;
}

#session-list > SessionItem {
    height: 5;
    min-height: 5;
    width: 1fr;
    padding: 0 1;
    margin: 0 0 1 0;
    background: #101a28;
    border-left: solid #28405d;
}

#session-list > SessionItem:hover {
    background: #16263a;
    border-left: solid #4ab8ff;
}

#session-list > SessionItem.-highlight {
    background: #18314d;
    border-left: thick #4ab8ff;
}

.session-card-content {
    width: 1fr;
    height: 4;
    min-height: 4;
    color: #edf4ff;
    padding: 0;
}

#main {
    width: 1fr;
    padding: 2 3;
}

.hero {
    height: 8;
    background: #0d1521;
    border: solid #243a56;
    padding: 1 2;
    margin-bottom: 1;
}

.hero-title {
    text-style: bold;
    color: #dff3ff;
}

.hero-path {
    color: #6688aa;
}

.ready {
    color: #67e8a5;
    text-style: bold;
}

#stats {
    height: 7;
    margin-bottom: 1;
}

.stat {
    width: 1fr;
    margin-right: 1;
    padding: 1 2;
    background: #0e1723;
    border: solid #1e324a;
}

.stat-number {
    color: #72c8ff;
    text-style: bold;
}

#sessions-panel {
    height: 1fr;
    background: #0c121c;
    border: solid #24364f;
    padding: 1 2;
}


#sessions-toolbar {
    height: 4;
    min-height: 4;
    width: 1fr;
    layout: horizontal;
    align-vertical: middle;
}

#sessions-title {
    width: 1fr;
    height: 3;
    content-align: left middle;
    margin: 0;
}

#new-session-btn {
    width: 20;
    min-width: 20;
    height: 3;
    min-height: 3;
}

#add-project-btn {
    width: 1fr;
    min-height: 3;
}

Button {
    margin-right: 1;
}

Button.primary {
    background: #1479b8;
    color: white;
}

Button.success {
    background: #17734d;
    color: white;
}

.modal {
    width: 70;
    height: auto;
    max-height: 30;
    background: #0d1521;
    border: solid #3f6d98;
    padding: 2 3;
}

.modal-title {
    color: #9ad8ff;
    text-style: bold;
    margin-bottom: 1;
}

Input {
    margin-bottom: 1;
}

#empty {
    color: #60758c;
    padding: 2;
}
"""


class AddProjectScreen(
    ModalScreen,
):
    def compose(
        self,
    ) -> ComposeResult:
        with Container(
            classes="modal"
        ):
            yield Label(
                "Add Project",
                classes="modal-title",
            )

            yield Label(
                "Choose a folder or type a path."
            )

            yield Input(
                placeholder=(
                    "~/Projects/MyProject"
                ),
                id="project-path",
            )

            yield Input(
                placeholder=(
                    "Optional display name"
                ),
                id="project-name",
            )

            with Horizontal():
                yield Button(
                    "Choose Folder",
                    id="choose-folder",
                )

                yield Button(
                    "Add Project",
                    id="add-project",
                    classes="primary",
                )

                yield Button(
                    "Cancel",
                    id="cancel",
                )

    @on(
        Button.Pressed,
        "#choose-folder",
    )
    def choose_folder(
        self,
    ):
        registry = (
            ProjectRegistry()
        )

        path = (
            registry
            .choose_folder_macos()
        )

        if path:
            self.query_one(
                "#project-path",
                Input,
            ).value = path

    @on(
        Button.Pressed,
        "#add-project",
    )
    def add_project(
        self,
    ):
        path = (
            self.query_one(
                "#project-path",
                Input,
            )
            .value
            .strip()
        )

        name = (
            self.query_one(
                "#project-name",
                Input,
            )
            .value
            .strip()
        )

        if not path:
            return

        try:
            project = (
                ProjectRegistry()
                .add(
                    path,
                    name or None,
                )
            )

        except Exception as exc:
            self.notify(
                str(exc),
                severity="error",
            )
            return

        self.dismiss(
            project.id
        )

    @on(
        Button.Pressed,
        "#cancel",
    )
    def cancel(
        self,
    ):
        self.dismiss(
            None
        )


class NewSessionScreen(
    ModalScreen,
):
    def compose(
        self,
    ) -> ComposeResult:
        with Container(
            classes="modal"
        ):
            yield Label(
                "New Session",
                classes="modal-title",
            )

            yield Input(
                placeholder=(
                    "What should Nexus do?"
                ),
                id="objective",
            )

            yield Input(
                placeholder=(
                    "Optional session title"
                ),
                id="session-title",
            )

            with Horizontal():
                yield Button(
                    "Create & Run",
                    id="create",
                    classes="success",
                )

                yield Button(
                    "Cancel",
                    id="cancel",
                )

    @on(
        Button.Pressed,
        "#create",
    )
    def create(
        self,
    ):
        objective = (
            self.query_one(
                "#objective",
                Input,
            )
            .value
            .strip()
        )

        title = (
            self.query_one(
                "#session-title",
                Input,
            )
            .value
            .strip()
        )

        if not objective:
            return

        self.dismiss(
            {
                "objective": objective,
                "title": title or None,
            }
        )

    @on(
        Button.Pressed,
        "#cancel",
    )
    def cancel(
        self,
    ):
        self.dismiss(
            None
        )


class SessionDetailScreen(
    ModalScreen,
):
    def __init__(
        self,
        session,
    ):
        super().__init__()
        self.session = session

    def compose(
        self,
    ) -> ComposeResult:
        history = (
            self.session.history
            or []
        )

        history_text = []

        for item in history[-12:]:
            history_text.append(
                f"### {str(item.get('type', 'event')).upper()}\n"
                f"{str(item.get('text', ''))}"
            )

        if not history_text:
            history_text = [
                "No session history yet."
            ]

        with Container(
            classes="modal"
        ):
            yield Label(
                self.session.title,
                classes="modal-title",
            )

            yield Static(
                f"Status: {self.session.status}\n"
                f"Session: {self.session.id}"
            )

            yield Markdown(
                "\n\n".join(
                    history_text
                ),
                id="session-history",
            )

            yield Input(
                placeholder=(
                    "Continue with..."
                ),
                id="continue-instruction",
            )

            with Horizontal():
                yield Button(
                    "Open Agent Shell",
                    id="open-agent-shell",
                    classes="primary",
                )

                yield Button(
                    "Continue Session",
                    id="continue-session",
                    classes="success",
                )

                yield Button(
                    "Close",
                    id="close-session",
                )

    @on(
        Button.Pressed,
        "#open-agent-shell",
    )
    def open_agent_shell_pressed(
        self,
    ):
        self.dismiss(
            {
                "action": "open_shell",
            }
        )

    @on(
        Button.Pressed,
        "#continue-session",
    )
    def continue_pressed(
        self,
    ):
        instruction = (
            self.query_one(
                "#continue-instruction",
                Input,
            )
            .value
            .strip()
        )

        if not instruction:
            return

        self.dismiss(
            {
                "action": "continue",
                "instruction": instruction,
            }
        )

    @on(
        Button.Pressed,
        "#close-session",
    )
    def close_pressed(
        self,
    ):
        self.dismiss(
            None
        )


class ProjectItem(
    ListItem,
):
    def __init__(
        self,
        project,
    ):
        super().__init__()

        self.project = project

    def compose(
        self,
    ):
        sessions = SessionStore(
            self.project.path
        ).list()

        yield Static(
            f"[b]{self.project.name}[/b]\n"
            f"[dim]{len(sessions)} sessions[/dim]"
        )


class SessionItem(
    ListItem,
):
    def __init__(
        self,
        session,
    ):
        super().__init__()

        self.session = session

    def compose(
        self,
    ):
        status_icon = {
            "COMPLETED": "✓",
            "RUNNING": "▶",
            "FAILED": "✗",
            "NEW": "●",
        }.get(
            self.session.status,
            "•",
        )

        objective = str(
            self.session.objective
            or ""
        ).replace(
            "\n",
            " ",
        ).strip()

        if len(objective) > 88:
            objective = (
                objective[:85]
                + "..."
            )

        yield Static(
            f"{status_icon} "
            f"[b]{self.session.title}[/b]\n"
            f"[dim]{objective}[/dim]\n"
            f"[b]{self.session.status}[/b]",
            classes="session-card-content",
        )


class NexusApp(
    App,
):
    CSS = CSS

    TITLE = "NEXUS"

    SUB_TITLE = (
        "Autonomous Agent Runtime"
    )

    BINDINGS = [
        Binding(
            "n",
            "new_session",
            "New Session",
        ),
        Binding(
            "a",
            "add_project",
            "Add Project",
        ),
        Binding(
            "r",
            "refresh",
            "Refresh",
        ),
        Binding(
            "enter",
            "open_selected",
            "Open",
        ),
        Binding(
            "q",
            "quit",
            "Quit",
        ),
    ]

    def __init__(
        self,
    ):
        super().__init__()

        self.registry = (
            ProjectRegistry()
        )

        self.active_project = (
            self.registry.active()
        )

    def compose(
        self,
    ) -> ComposeResult:
        yield Header(
            show_clock=True
        )

        with Horizontal(
            id="shell"
        ):
            with Vertical(
                id="sidebar"
            ):
                yield Static(
                    "◆ NEXUS\n"
                    "[dim]AGENT OS / 1.6[/dim]",
                    classes="brand",
                )

                yield Static(
                    "PROJECTS",
                    classes="section-title",
                )

                yield ListView(
                    id="project-list"
                )

                yield Button(
                    "+ Add Project",
                    id="add-project-btn",
                    classes="primary",
                )

            with Vertical(
                id="main"
            ):
                yield Static(
                    id="hero",
                    classes="hero",
                )

                with Horizontal(
                    id="stats"
                ):
                    yield Static(
                        id="stat-sessions",
                        classes="stat",
                    )

                    yield Static(
                        id="stat-running",
                        classes="stat",
                    )

                    yield Static(
                        id="stat-completed",
                        classes="stat",
                    )

                with Vertical(
                    id="sessions-panel"
                ):
                    with Horizontal(
                        id="sessions-toolbar"
                    ):
                        yield Static(
                            "SESSIONS",
                            id="sessions-title",
                            classes="section-title",
                        )

                        yield Button(
                            "+ New Session",
                            id="new-session-btn",
                            classes="success",
                        )

                    yield ListView(
                        id="session-list"
                    )

        yield Static("READY", id="ui-ready-marker")

        yield Footer()

    def on_mount(
        self,
    ):
        self.refresh_projects()
        self.refresh_main()

        self.query_one(
            "#ui-ready-marker",
            Static,
        ).update(
            "UI_MOUNT_COMPLETE"
        )

    def refresh_projects(
        self,
    ):
        view = self.query_one(
            "#project-list",
            ListView,
        )

        view.clear()

        projects = (
            self.registry.list()
        )

        for project in projects:
            view.append(
                ProjectItem(
                    project
                )
            )

    def refresh_main(
        self,
    ):
        hero = self.query_one(
            "#hero",
            Static,
        )

        session_view = self.query_one(
            "#session-list",
            ListView,
        )

        session_view.clear()

        if not self.active_project:
            hero.update(
                "[b]Welcome to Nexus[/b]\n\n"
                "[dim]Add a project to begin.[/dim]"
            )

            self.query_one(
                "#stat-sessions",
                Static,
            ).update(
                "[b]0[/b]\nSessions"
            )

            self.query_one(
                "#stat-running",
                Static,
            ).update(
                "[b]0[/b]\nRunning"
            )

            self.query_one(
                "#stat-completed",
                Static,
            ).update(
                "[b]0[/b]\nCompleted"
            )

            return

        store = SessionStore(
            self.active_project.path
        )

        sessions = store.list()

        running = sum(
            1
            for s in sessions
            if s.status == "RUNNING"
        )

        completed = sum(
            1
            for s in sessions
            if s.status == "COMPLETED"
        )

        hero.update(
            f"[b]{self.active_project.name}[/b]\n"
            f"[dim]{self.active_project.path}[/dim]\n\n"
            "[green]● Runtime Ready[/green]"
        )

        self.query_one(
            "#stat-sessions",
            Static,
        ).update(
            f"[b]{len(sessions)}[/b]\nSessions"
        )

        self.query_one(
            "#stat-running",
            Static,
        ).update(
            f"[b]{running}[/b]\nRunning"
        )

        self.query_one(
            "#stat-completed",
            Static,
        ).update(
            f"[b]{completed}[/b]\nCompleted"
        )

        for session in sessions:
            session_view.append(
                SessionItem(
                    session
                )
            )

    @on(
        ListView.Selected,
        "#project-list",
    )
    def project_selected(
        self,
        event,
    ):
        item = event.item

        if not isinstance(
            item,
            ProjectItem,
        ):
            return

        self.active_project = (
            self.registry.use(
                item.project.id
            )
        )

        self.refresh_main()

    def on_button_pressed(
        self,
        event: Button.Pressed,
    ):
        """Route home-screen buttons through canonical actions."""

        button_id = event.button.id

        if button_id == "add-project-btn":
            self.action_add_project()
            event.stop()
            return

        if button_id == "new-session-btn":
            self.action_new_session()
            event.stop()
            return

    def action_add_project(
        self,
    ):
        """Open Add Project from button or keyboard binding."""

        self.run_worker(
            self._add_project_flow(),
            name="add-project-modal",
            group="modal",
            exclusive=True,
        )

    async def _add_project_flow(
        self,
    ):
        result = await self.push_screen_wait(
            AddProjectScreen()
        )

        if not result:
            return

        self.active_project = (
            self.registry.get(
                result
            )
        )

        self.refresh_projects()
        self.refresh_main()

    def action_new_session(
        self,
    ):
        """Open New Session from button or keyboard binding."""

        if not self.active_project:
            self.notify(
                "Choose a project first.",
                severity="warning",
            )
            return

        self.run_worker(
            self._new_session_flow(),
            name="new-session-modal",
            group="modal",
            exclusive=True,
        )

    async def _new_session_flow(
        self,
    ):
        data = await self.push_screen_wait(
            NewSessionScreen()
        )

        if not data:
            return

        store = SessionStore(
            self.active_project.path
        )

        session = store.create(
            data["objective"],
            data.get("title"),
        )

        self.refresh_main()

        self.notify(
            "Session created. Launching Nexus..."
        )

        self.exit(
            result={
                "action": "run_session",
                "project_path": (
                    self.active_project.path
                ),
                "session_id": session.id,
            }
        )






    @on(
        ListView.Selected,
        "#session-list",
    )
    def session_selected(
        self,
        event,
    ):
        item = event.item

        if not isinstance(
            item,
            SessionItem,
        ):
            return

        if not self.active_project:
            return

        self.run_worker(
            self._session_detail_flow(
                item.session.id
            ),
            name="session-detail",
            group="modal",
            exclusive=True,
        )

    async def _session_detail_flow(
        self,
        session_id,
    ):
        store = SessionStore(
            self.active_project.path
        )

        session = store.get(
            session_id
        )

        if session is None:
            self.notify(
                "Session not found.",
                severity="error",
            )
            return

        result = await self.push_screen_wait(
            SessionDetailScreen(
                session
            )
        )

        if not result:
            return

        action = result.get(
            "action"
        )

        if action == "open_shell":
            self.exit(
                result={
                    "action": "open_agent_shell",
                    "project_path": (
                        self.active_project.path
                    ),
                    "session_id": session.id,
                }
            )
            return

        if action != "continue":
            return

        instruction = result.get(
            "instruction",
            "",
        ).strip()

        if not instruction:
            return

        self.exit(
            result={
                "action": "continue_session",
                "project_path": (
                    self.active_project.path
                ),
                "session_id": session.id,
                "instruction": instruction,
            }
        )

    def action_refresh(
        self,
    ):
        self.active_project = (
            self.registry.active()
        )

        self.refresh_projects()
        self.refresh_main()

    def action_open_selected(
        self,
    ):
        pass


def launch_home():
    """
    Nexus application loop.

    The Textual UI selects a project/session. Session work runs
    in the persistent Agent Shell. Escape from the Agent Shell
    returns here and immediately reopens the Nexus UI.
    """

    while True:
        app = NexusApp()
        result = app.run()

        if not isinstance(
            result,
            dict,
        ):
            return result

        action = result.get(
            "action"
        )

        if action not in (
            "run_session",
            "continue_session",
            "open_agent_shell",
        ):
            return result

        project_path = result.get(
            "project_path"
        )

        session_id = result.get(
            "session_id"
        )

        if not project_path or not session_id:
            print(
                "NEXUS_SESSION_LAUNCH_INVALID"
            )
            continue

        if action == "run_session":
            run_agent_shell(
                project_path,
                session_id,
                initial_run=True,
            )

        elif action == "continue_session":
            run_agent_shell(
                project_path,
                session_id,
                initial_instruction=result.get(
                    "instruction",
                    "",
                ),
            )

        else:
            run_agent_shell(
                project_path,
                session_id,
            )
