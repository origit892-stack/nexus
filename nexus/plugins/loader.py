from __future__ import annotations

import importlib.util
from pathlib import Path


def plugin_paths():
    return [
        Path.home()
        / ".nexus"
        / "plugins",

        Path(__file__)
        .resolve()
        .parent,
    ]


def discover():
    found = []

    for root in plugin_paths():
        if not root.exists():
            continue

        for path in sorted(
            root.glob("*.py")
        ):
            if path.name.startswith("_"):
                continue

            if path.name == "loader.py":
                continue

            found.append(path)

    return found


def load_plugin(path):
    name = (
        "nexus_plugin_"
        + path.stem
    )

    spec = (
        importlib.util
        .spec_from_file_location(
            name,
            path,
        )
    )

    module = (
        importlib.util
        .module_from_spec(spec)
    )

    spec.loader.exec_module(
        module
    )

    return module


def register_plugins(
    registry,
    context,
):
    loaded = []

    for path in discover():
        try:
            module = load_plugin(
                path
            )

            register = getattr(
                module,
                "register",
                None,
            )

            if register:
                register(
                    registry,
                    context,
                )

                loaded.append(
                    str(path)
                )

        except Exception as e:
            loaded.append(
                f"ERROR {path}: "
                f"{type(e).__name__}: {e}"
            )

    return loaded
