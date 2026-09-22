from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .engine import (
    TextureEngine,
    TextureEngineError,
)
from .schema import (
    generate_texture_schema,
)


def generate_texture(
    *,
    workspace: str,
    mesh: str,
    prompt: str,
    reference_image: str | None = None,
    resolution: int = 2048,
    quality: str = "standard",
    seed: int = 1701,
    pbr: bool = True,
    **_: Any,
) -> dict[str, Any]:
    try:
        engine = TextureEngine(
            Path(workspace)
        )

        return engine.generate(
            mesh=mesh,
            prompt=prompt,
            reference_image=reference_image,
            resolution=resolution,
            quality=quality,
            seed=seed,
            pbr=pbr,
        )

    except TextureEngineError as exc:
        return {
            "ok": False,
            "tool": "generate_texture",
            "error": str(exc),
        }

    except Exception as exc:
        return {
            "ok": False,
            "tool": "generate_texture",
            "error": (
                "UNEXPECTED_TEXTURE_ENGINE_ERROR: "
                + repr(exc)
            ),
        }


def bind_generate_texture(
    workspace: str,
) -> Callable[..., dict[str, Any]]:
    resolved_workspace = str(
        Path(workspace).resolve()
    )

    def handler(
        **args: Any,
    ) -> dict[str, Any]:
        return generate_texture(
            workspace=resolved_workspace,
            **args,
        )

    handler.__name__ = (
        "generate_texture_bound"
    )

    handler.__qualname__ = (
        "generate_texture_bound"
    )

    return handler
