from __future__ import annotations

from pathlib import Path
from typing import Any

import hashlib
import json
import os
import shutil
import subprocess
import time
import uuid

from PIL import Image, ImageFilter

from .pbr import derive_pbr


class TextureEngineError(RuntimeError):
    pass


def _inside(
    root: Path,
    candidate: Path,
) -> bool:
    try:
        candidate.resolve().relative_to(
            root.resolve()
        )
        return True
    except ValueError:
        return False


def _sha256(
    path: Path,
) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as handle:
        while True:
            chunk = handle.read(
                1024 * 1024
            )

            if not chunk:
                break

            digest.update(chunk)

    return digest.hexdigest()


def _run(
    command: list[str],
    *,
    timeout: int,
) -> dict[str, Any]:
    started = time.perf_counter()

    process = subprocess.run(
        command,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
        check=False,
    )

    seconds = round(
        time.perf_counter()
        - started,
        3,
    )

    result = {
        "returncode":
            process.returncode,

        "seconds":
            seconds,

        "stdout":
            process.stdout[-12000:],

        "stderr":
            process.stderr[-12000:],
    }

    stderr_lower = (
        process.stderr.lower()
    )

    stdout_lower = (
        process.stdout.lower()
    )

    fatal_markers = (
        "traceback (most recent call last)",
        "runtimeerror:",
        "syntaxerror:",
        "modulenotfounderror:",
        "attributeerror:",
        "typeerror:",
        "nameerror:",
    )

    marker_hits = [
        marker
        for marker in fatal_markers
        if (
            marker in stderr_lower
            or marker in stdout_lower
        )
    ]

    if (
        process.returncode != 0
        or marker_hits
    ):
        result[
            "fatal_markers"
        ] = marker_hits

        raise TextureEngineError(
            "SUBPROCESS_FAILED="
            + json.dumps(
                result,
                ensure_ascii=False,
            )
        )

    return result


class TextureEngine:
    def __init__(
        self,
        workspace: str | Path,
    ) -> None:
        self.workspace = Path(
            workspace
        ).resolve()

        self.package = Path(
            __file__
        ).resolve().parent

        self.blender = Path(
            os.environ.get(
                "NEXUS_TEXTURE_BLENDER",
                (
                    "/Applications/"
                    "Blender.app/"
                    "Contents/MacOS/"
                    "Blender"
                ),
            )
        )

        self.mflux = Path(
            os.environ.get(
                "NEXUS_TEXTURE_MFLUX",
                str(
                    Path.home()
                    / ".nexus"
                    / "labs"
                    / "texture_engine_v1_20260919_142722"
                    / "mflux-venv"
                    / "bin"
                    / "mflux-generate-flux2"
                ),
            )
        )

    def resolve_mesh(
        self,
        mesh: str,
    ) -> Path:
        candidate = (
            self.workspace
            / mesh
        ).resolve()

        if not _inside(
            self.workspace,
            candidate,
        ):
            raise TextureEngineError(
                "MESH_OUTSIDE_WORKSPACE"
            )

        if not candidate.is_file():
            raise TextureEngineError(
                "MESH_NOT_FOUND="
                + mesh
            )

        if candidate.suffix.lower() not in {
            ".obj",
            ".glb",
            ".gltf",
        }:
            raise TextureEngineError(
                "UNSUPPORTED_MESH_FORMAT="
                + candidate.suffix
            )

        return candidate

    def _resolve_reference(
        self,
        reference: str,
    ) -> Path:
        candidate = (
            self.workspace
            / reference
        ).resolve()

        if not _inside(
            self.workspace,
            candidate,
        ):
            raise TextureEngineError(
                "REFERENCE_OUTSIDE_WORKSPACE"
            )

        if not candidate.is_file():
            raise TextureEngineError(
                "REFERENCE_NOT_FOUND"
            )

        return candidate

    def output_directory(
        self,
        source: Path,
    ) -> Path:
        job_id = (
            uuid.uuid4()
            .hex[:12]
        )

        root = (
            self.workspace
            / ".nexus"
            / "generated"
            / "textures"
            / (
                source.stem
                + "_"
                + job_id
            )
        )

        root.mkdir(
            parents=True,
            exist_ok=False,
        )

        return root

    def _resolve_model(
        self,
    ) -> Path:
        root = (
            Path.home()
            / ".cache"
            / "huggingface"
            / "hub"
            / (
                "models--mlx-community--"
                "flux2-klein-4b-4bit"
            )
            / "snapshots"
        )

        if not root.is_dir():
            raise TextureEngineError(
                "FLUX4B_CACHE_MISSING"
            )

        candidates = []

        for snapshot in root.iterdir():
            if not snapshot.is_dir():
                continue

            required = (
                "text_encoder",
                "tokenizer",
                "transformer",
                "vae",
            )

            if not all(
                (snapshot / item).is_dir()
                for item in required
            ):
                continue

            size = sum(
                path.stat().st_size
                for path in snapshot.rglob(
                    "*.safetensors"
                )
            )

            if (
                3_000_000_000
                < size
                < 7_000_000_000
            ):
                candidates.append(
                    (
                        size,
                        snapshot,
                    )
                )

        if not candidates:
            raise TextureEngineError(
                "FLUX4B_SNAPSHOT_MISSING"
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        return candidates[0][1]

    def _validate_png(
        self,
        path: Path,
    ) -> dict[str, Any]:
        if not path.is_file():
            raise TextureEngineError(
                "PNG_MISSING="
                + str(path)
            )

        image = Image.open(
            path
        ).convert("RGB")

        extrema = image.getextrema()

        dynamic = sum(
            high - low
            for low, high
            in extrema
        )

        valid = (
            image.width > 0
            and image.height > 0
            and path.stat().st_size > 1000
            and dynamic > 20
        )

        if not valid:
            raise TextureEngineError(
                "PNG_QA_FAILED="
                + str(path)
            )

        return {
            "width": image.width,
            "height": image.height,
            "bytes": path.stat().st_size,
            "dynamic_range": dynamic,
            "valid": True,
        }

    def _dilate(
        self,
        source: Path,
        output: Path,
    ) -> None:
        image = Image.open(
            source
        ).convert("RGB")

        current = image

        for _ in range(3):
            blurred = current.filter(
                ImageFilter.BoxBlur(1)
            )

            current = Image.blend(
                current,
                blurred,
                0.08,
            )

        current.save(output)

    def generate(
        self,
        *,
        mesh: str,
        prompt: str,
        reference_image: str | None = None,
        resolution: int = 2048,
        quality: str = "standard",
        seed: int = 1701,
        pbr: bool = True,
    ) -> dict[str, Any]:
        if not prompt.strip():
            raise TextureEngineError(
                "EMPTY_PROMPT"
            )

        if resolution not in {
            1024,
            2048,
            4096,
        }:
            raise TextureEngineError(
                "INVALID_RESOLUTION"
            )

        if quality not in {
            "fast",
            "standard",
            "high",
        }:
            raise TextureEngineError(
                "INVALID_QUALITY"
            )

        if not self.blender.is_file():
            raise TextureEngineError(
                "BLENDER_NOT_FOUND"
            )

        if not self.mflux.is_file():
            raise TextureEngineError(
                "MFLUX_NOT_FOUND"
            )

        source = self.resolve_mesh(
            mesh
        )

        original_hash = _sha256(
            source
        )

        output = self.output_directory(
            source
        )

        working_source = (
            output
            / (
                "source"
                + source.suffix.lower()
            )
        )

        shutil.copy2(
            source,
            working_source,
        )

        if _sha256(
            working_source
        ) != original_hash:
            raise TextureEngineError(
                "SOURCE_COPY_HASH_MISMATCH"
            )

        logs = (
            output
            / "logs"
        )

        logs.mkdir()

        views = (
            output
            / "geometry_views"
        )

        views.mkdir()

        qa_views = (
            output
            / "qa_views"
        )

        qa_views.mkdir()

        preprocessed = (
            output
            / "preprocessed.glb"
        )

        reference = (
            output
            / "appearance_reference.png"
        )

        raw_base = (
            output
            / "base_color_raw.png"
        )

        base_color = (
            output
            / "base_color.png"
        )

        textured_glb = (
            output
            / "textured.glb"
        )

        timings: dict[str, float] = {}

        total_started = (
            time.perf_counter()
        )

        preprocess = _run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(
                    self.package
                    / "preprocess_blender.py"
                ),
                "--",
                str(working_source),
                str(preprocessed),
                str(
                    output
                    / "preprocess.json"
                ),
            ],
            timeout=600,
        )

        timings["preprocess"] = (
            preprocess["seconds"]
        )

        (
            logs
            / "preprocess.json"
        ).write_text(
            json.dumps(
                preprocess,
                indent=2,
            ),
            encoding="utf-8",
        )

        render = _run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(
                    self.package
                    / "render_views_blender.py"
                ),
                "--",
                str(preprocessed),
                str(views),
            ],
            timeout=600,
        )

        timings["geometry_views"] = (
            render["seconds"]
        )

        (
            logs
            / "geometry_views.json"
        ).write_text(
            json.dumps(
                render,
                indent=2,
            ),
            encoding="utf-8",
        )

        for name in (
            "front",
            "back",
            "left",
            "right",
            "top",
            "bottom",
            "hero",
        ):
            self._validate_png(
                views
                / (
                    name
                    + ".png"
                )
            )

        if reference_image:
            supplied = (
                self._resolve_reference(
                    reference_image
                )
            )

            shutil.copy2(
                supplied,
                reference,
            )

            backend = (
                "USER_REFERENCE"
            )

            timings[
                "appearance_generation"
            ] = 0.0

        else:
            model = (
                self._resolve_model()
            )

            steps = {
                "fast": 2,
                "standard": 4,
                "high": 6,
            }[
                quality
            ]

            appearance_prompt = (
                "Create one clean square material "
                "appearance reference for a 3D asset. "
                "The final texture will be projected "
                "onto the exact source mesh. "
                "Do not add readable text, logos, "
                "numbers, watermarks, frames, people, "
                "or unrelated objects. "
                "Use physically plausible material "
                "detail, wear, color variation and "
                "surface character. "
                "Requested appearance: "
                + prompt
            )

            generation = _run(
                [
                    str(self.mflux),
                    "--model",
                    str(model),
                    "--prompt",
                    appearance_prompt,
                    "--steps",
                    str(steps),
                    "--seed",
                    str(seed),
                    "--width",
                    "768",
                    "--height",
                    "768",
                    "--output",
                    str(reference),
                ],
                timeout=1200,
            )

            timings[
                "appearance_generation"
            ] = generation[
                "seconds"
            ]

            (
                logs
                / "appearance_generation.json"
            ).write_text(
                json.dumps(
                    generation,
                    indent=2,
                ),
                encoding="utf-8",
            )

            backend = (
                "FLUX2_KLEIN_4B_MFLUX"
            )

        reference_qa = (
            self._validate_png(
                reference
            )
        )

        correspondence = (
            output
            / "uv-correspondence.json"
        )

        correspondence_run = _run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(
                    self.package
                    / "export_uv_correspondence_blender.py"
                ),
                "--",
                str(preprocessed),
                str(
                    views
                    / "views.json"
                ),
                str(correspondence),
            ],
            timeout=600,
        )

        timings[
            "uv_correspondence"
        ] = correspondence_run[
            "seconds"
        ]

        (
            logs
            / "uv_correspondence.json"
        ).write_text(
            json.dumps(
                correspondence_run,
                indent=2,
            ),
            encoding="utf-8",
        )

        if not correspondence.is_file():
            raise TextureEngineError(
                "UV_CORRESPONDENCE_MISSING"
            )

        cpu_bake = _run(
            [
                str(
                    Path(
                        os.environ.get(
                            "NEXUS_TEXTURE_PYTHON",
                            os.sys.executable,
                        )
                    )
                ),
                str(
                    self.package
                    / "cpu_uv_bake.py"
                ),
                str(reference),
                str(correspondence),
                str(raw_base),
                str(resolution),
            ],
            timeout=900,
        )

        timings["bake"] = (
            cpu_bake[
                "seconds"
            ]
        )

        (
            logs
            / "bake.json"
        ).write_text(
            json.dumps(
                cpu_bake,
                indent=2,
            ),
            encoding="utf-8",
        )

        raw_base_qa = (
            self._validate_png(
                raw_base
            )
        )

        self._dilate(
            raw_base,
            base_color,
        )

        base_color_qa = (
            self._validate_png(
                base_color
            )
        )

        if pbr:
            pbr_maps = derive_pbr(
                base_color,
                output,
            )

        else:
            neutral = Image.new(
                "L",
                (
                    resolution,
                    resolution,
                ),
                128,
            )

            roughness = (
                output
                / "roughness.png"
            )

            metallic = (
                output
                / "metallic.png"
            )

            normal = (
                output
                / "normal_neutral.png"
            )

            neutral.save(
                roughness
            )

            Image.new(
                "L",
                (
                    resolution,
                    resolution,
                ),
                0,
            ).save(
                metallic
            )

            Image.new(
                "RGB",
                (
                    resolution,
                    resolution,
                ),
                (
                    128,
                    128,
                    255,
                ),
            ).save(
                normal
            )

            pbr_maps = {
                "roughness":
                    str(roughness),

                "metallic":
                    str(metallic),

                "normal":
                    str(normal),

                "normal_classification":
                    "NEUTRAL_SAFE_FALLBACK",

                "pbr_classification":
                    "DISABLED_NEUTRAL",
            }

        export = _run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(
                    self.package
                    / "export_blender.py"
                ),
                "--",
                str(preprocessed),
                str(base_color),
                str(
                    pbr_maps[
                        "roughness"
                    ]
                ),
                str(
                    pbr_maps[
                        "metallic"
                    ]
                ),
                str(
                    pbr_maps[
                        "normal"
                    ]
                ),
                str(textured_glb),
                str(
                    output
                    / "export.json"
                ),
            ],
            timeout=600,
        )

        timings["export"] = (
            export["seconds"]
        )

        if not textured_glb.is_file():
            raise TextureEngineError(
                "TEXTURED_GLB_MISSING"
            )

        qa_render = _run(
            [
                str(self.blender),
                "--background",
                "--factory-startup",
                "--python",
                str(
                    self.package
                    / "render_qa_blender.py"
                ),
                "--",
                str(textured_glb),
                str(qa_views),
            ],
            timeout=600,
        )

        timings["qa_render"] = (
            qa_render["seconds"]
        )

        qa_records = {}

        for name in (
            "front",
            "back",
            "left",
            "right",
            "top",
            "bottom",
            "hero",
        ):
            qa_records[name] = (
                self._validate_png(
                    qa_views
                    / (
                        name
                        + ".png"
                    )
                )
            )

        final_hash = _sha256(
            source
        )

        if final_hash != original_hash:
            raise TextureEngineError(
                "SOURCE_MESH_MUTATED"
            )

        total_seconds = round(
            time.perf_counter()
            - total_started,
            3,
        )

        result = {
            "ok": True,

            "tool":
                "generate_texture",

            "stage":
                "TEXTURE_COMPLETE",

            "source_mesh":
                str(source),

            "source_sha256":
                original_hash,

            "source_mutated":
                False,

            "working_source":
                str(working_source),

            "preprocessed_mesh":
                str(preprocessed),

            "geometry_views":
                str(views),

            "appearance_reference":
                str(reference),

            "base_color":
                str(base_color),

            "roughness":
                pbr_maps[
                    "roughness"
                ],

            "metallic":
                pbr_maps[
                    "metallic"
                ],

            "normal":
                pbr_maps[
                    "normal"
                ],

            "pbr_classification":
                pbr_maps[
                    "pbr_classification"
                ],

            "normal_classification":
                pbr_maps[
                    "normal_classification"
                ],

            "textured_glb":
                str(textured_glb),

            "qa_views":
                str(qa_views),

            "reference_qa":
                reference_qa,

            "raw_base_color_qa":
                raw_base_qa,

            "base_color_qa":
                base_color_qa,

            "qa_render_records":
                qa_records,

            "backend":
                backend,

            "resolution":
                resolution,

            "quality":
                quality,

            "seed":
                seed,

            "pbr_requested":
                bool(pbr),

            "timings":
                timings,

            "total_seconds":
                total_seconds,

            "output_directory":
                str(output),

            "texture_method":
                "CPU_BARYCENTRIC_UV_RASTERIZATION_V2",

            "known_limitations": [
                (
                    "Current production fallback uses "
                    "one generated appearance reference "
                    "projected from the hero camera."
                ),
                (
                    "PBR maps are derived proxies, not "
                    "physically measured ground truth."
                ),
                (
                    "Multi-view image-conditioned fusion "
                    "remains the next quality upgrade."
                ),
            ],

            "next_quality_upgrade":
                (
                    "MULTIVIEW_IMAGE_CONDITIONED_"
                    "EDIT_AND_VISIBILITY_FUSION"
                ),
        }

        (
            output
            / "result.json"
        ).write_text(
            json.dumps(
                result,
                indent=2,
            ),
            encoding="utf-8",
        )

        return result
