from __future__ import annotations

from pathlib import Path

import pytest

from nexus.tools.texture_engine.engine import (
    TextureEngine,
    TextureEngineError,
)
from nexus.tools.texture_engine.schema import (
    generate_texture_schema,
)


def test_schema_contract():
    schema = generate_texture_schema()

    assert schema["type"] == "object"

    assert schema["required"] == [
        "mesh",
        "prompt",
    ]

    assert (
        schema["additionalProperties"]
        is False
    )


def test_workspace_escape_rejected(
    tmp_path,
):
    workspace = (
        tmp_path
        / "workspace"
    )

    workspace.mkdir()

    outside = (
        tmp_path
        / "outside.obj"
    )

    outside.write_text(
        "v 0 0 0\n",
        encoding="utf-8",
    )

    engine = TextureEngine(
        workspace
    )

    with pytest.raises(
        TextureEngineError,
        match="MESH_OUTSIDE_WORKSPACE",
    ):
        engine.resolve_mesh(
            "../outside.obj"
        )


def test_missing_mesh_rejected(
    tmp_path,
):
    engine = TextureEngine(
        tmp_path
    )

    with pytest.raises(
        TextureEngineError,
        match="MESH_NOT_FOUND",
    ):
        engine.resolve_mesh(
            "missing.obj"
        )


def test_unsupported_mesh_rejected(
    tmp_path,
):
    path = (
        tmp_path
        / "asset.txt"
    )

    path.write_text(
        "x",
        encoding="utf-8",
    )

    engine = TextureEngine(
        tmp_path
    )

    with pytest.raises(
        TextureEngineError,
        match="UNSUPPORTED_MESH_FORMAT",
    ):
        engine.resolve_mesh(
            "asset.txt"
        )


def test_output_contained(
    tmp_path,
):
    mesh = (
        tmp_path
        / "asset.obj"
    )

    mesh.write_text(
        "v 0 0 0\n",
        encoding="utf-8",
    )

    engine = TextureEngine(
        tmp_path
    )

    output = engine.output_directory(
        mesh
    )

    output.resolve().relative_to(
        tmp_path.resolve()
    )

    assert "generated" in output.parts
    assert "textures" in output.parts


def test_bound_handler_injects_workspace(
    tmp_path,
    monkeypatch,
):
    from nexus.tools.texture_engine import (
        bind_generate_texture,
    )
    from nexus.tools.texture_engine.engine import (
        TextureEngine,
    )

    captured = {}

    def fake_generate(
        self,
        **kwargs,
    ):
        captured["workspace"] = (
            self.workspace
        )
        captured["kwargs"] = kwargs

        return {
            "ok": True,
            "tool": "generate_texture",
            "stage": "TEST_DOUBLE",
            "source_mesh": str(
                self.workspace
                / kwargs["mesh"]
            ),
            "source_mutated": False,
        }

    monkeypatch.setattr(
        TextureEngine,
        "generate",
        fake_generate,
    )

    handler = bind_generate_texture(
        str(tmp_path)
    )

    result = handler(
        mesh="bound.obj",
        prompt="aged steel",
        resolution=1024,
        quality="fast",
        seed=1,
        pbr=False,
    )

    assert result["ok"] is True

    assert (
        captured["workspace"]
        == tmp_path.resolve()
    )

    assert (
        captured["kwargs"]["mesh"]
        == "bound.obj"
    )

    assert (
        captured["kwargs"]["prompt"]
        == "aged steel"
    )

    assert (
        captured["kwargs"]["resolution"]
        == 1024
    )

    assert (
        captured["kwargs"]["quality"]
        == "fast"
    )

    assert (
        captured["kwargs"]["seed"]
        == 1
    )

    assert (
        captured["kwargs"]["pbr"]
        is False
    )



def test_real_registry_injects_workspace(
    tmp_path,
    monkeypatch,
):
    from nexus.runtime.tool_factory import (
        build_registry,
    )
    from nexus.tools.texture_engine.engine import (
        TextureEngine,
    )

    captured = {}

    def fake_generate(
        self,
        **kwargs,
    ):
        captured["workspace"] = (
            self.workspace
        )
        captured["kwargs"] = kwargs

        return {
            "ok": True,
            "tool": "generate_texture",
            "stage": "TEST_DOUBLE",
            "source_mesh": str(
                self.workspace
                / kwargs["mesh"]
            ),
            "source_mutated": False,
        }

    monkeypatch.setattr(
        TextureEngine,
        "generate",
        fake_generate,
    )

    registry, _permissions = (
        build_registry(
            str(tmp_path),
            "coder",
            "texture-workspace-test",
        )
    )

    result = registry.execute(
        "generate_texture",
        {
            "mesh":
                "registry.obj",

            "prompt":
                "aged steel",

            "resolution":
                1024,

            "quality":
                "fast",

            "seed":
                1,

            "pbr":
                False,
        },
    )

    assert isinstance(
        result,
        dict,
    )

    assert result["ok"] is True

    assert (
        captured["workspace"]
        == tmp_path.resolve()
    )

    assert (
        captured["kwargs"]["mesh"]
        == "registry.obj"
    )

    assert (
        captured["kwargs"]["prompt"]
        == "aged steel"
    )



def test_subprocess_traceback_with_zero_exit_is_failure(
    monkeypatch,
):
    import subprocess

    from nexus.tools.texture_engine import (
        engine as engine_module,
    )

    class Result:
        returncode = 0
        stdout = ""
        stderr = (
            "Traceback (most recent call last):\n"
            "RuntimeError: synthetic blender failure\n"
        )

    def fake_run(
        *args,
        **kwargs,
    ):
        return Result()

    monkeypatch.setattr(
        subprocess,
        "run",
        fake_run,
    )

    with pytest.raises(
        engine_module.TextureEngineError,
        match="SUBPROCESS_FAILED",
    ):
        engine_module._run(
            [
                "blender",
                "--background",
            ],
            timeout=10,
        )
