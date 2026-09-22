from pathlib import Path
import hashlib

import nexus.cli as cli
import nexus.ui.app as ui_app


def test_bare_nexus_forwards_current_directory():
    source = Path(
        cli.__file__
    ).read_text(
        encoding="utf-8"
    )

    assert "initial_project_path=str(" in source
    assert "Path.cwd().resolve()" in source


def test_unregistered_launch_directory_is_transient(
    tmp_path,
):
    app = ui_app.NexusApp()

    before = [
        (p.id, p.path)
        for p in app.registry.list()
    ]

    before_active = getattr(
        app.registry.active(),
        "id",
        None,
    )

    app.initial_project_path = str(
        tmp_path
    )

    app._apply_initial_project_path()

    after = [
        (p.id, p.path)
        for p in app.registry.list()
    ]

    after_active = getattr(
        app.registry.active(),
        "id",
        None,
    )

    assert (
        Path(app.active_project.path)
        .resolve()
        == tmp_path.resolve()
    )

    expected = (
        "launch-"
        + hashlib.sha256(
            str(
                tmp_path.resolve()
            ).encode("utf-8")
        ).hexdigest()[:12]
    )

    assert app.active_project.id == expected
    assert before == after
    assert before_active == after_active


def test_registered_launch_directory_reuses_project():
    app = ui_app.NexusApp()
    projects = app.registry.list()

    assert projects

    target = projects[0]

    app.initial_project_path = target.path
    app._apply_initial_project_path()

    assert (
        app.active_project.id
        == target.id
    )


def test_mount_applies_hint_before_main_refresh():
    source = Path(
        ui_app.__file__
    ).read_text(
        encoding="utf-8"
    )

    start = source.index(
        "    def on_mount("
    )

    end = source.index(
        "    def refresh_projects(",
        start,
    )

    segment = source[start:end]

    assert (
        segment.index(
            "self.refresh_projects()"
        )
        < segment.index(
            "self._apply_initial_project_path()"
        )
        < segment.index(
            "self.refresh_main()"
        )
    )


def test_every_launch_home_call_forwards_cwd():
    import ast

    source = Path(
        cli.__file__
    ).read_text(
        encoding="utf-8"
    )

    tree = ast.parse(source)

    calls = []

    for node in ast.walk(tree):
        if not isinstance(
            node,
            ast.Call,
        ):
            continue

        if not (
            isinstance(
                node.func,
                ast.Name,
            )
            and node.func.id
            == "launch_home"
        ):
            continue

        calls.append(
            ast.get_source_segment(
                source,
                node,
            )
            or ""
        )

    assert len(calls) == 2

    for call in calls:
        assert (
            "initial_project_path"
            in call
        )
        assert (
            "Path.cwd().resolve()"
            in call
        )
