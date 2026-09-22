from __future__ import annotations

import bpy
import json
import math
from pathlib import Path
import sys

SOURCE = Path(sys.argv[-3]).resolve()
OUTPUT = Path(sys.argv[-2]).resolve()
REPORT = Path(sys.argv[-1]).resolve()


def clear_scene():
    bpy.ops.object.select_all(action="SELECT")
    bpy.ops.object.delete(use_global=False)


def load_source():
    suffix = SOURCE.suffix.lower()

    if suffix == ".obj":
        bpy.ops.wm.obj_import(
            filepath=str(SOURCE)
        )
        return

    if suffix in {".glb", ".gltf"}:
        bpy.ops.import_scene.gltf(
            filepath=str(SOURCE)
        )
        return

    raise RuntimeError(
        "UNSUPPORTED_MESH_FORMAT="
        + suffix
    )


def mesh_objects():
    return [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    ]


def join_meshes(objects):
    if not objects:
        raise RuntimeError("NO_MESH_OBJECTS")

    bpy.ops.object.select_all(
        action="DESELECT"
    )

    for obj in objects:
        obj.select_set(True)

    bpy.context.view_layer.objects.active = (
        objects[0]
    )

    if len(objects) > 1:
        bpy.ops.object.join()

    return bpy.context.view_layer.objects.active


def uv_valid(obj):
    layer = obj.data.uv_layers.active

    if layer is None:
        return False

    if len(layer.data) != len(
        obj.data.loops
    ):
        return False

    if len(layer.data) == 0:
        return False

    for item in layer.data:
        u = float(item.uv.x)
        v = float(item.uv.y)

        if not (
            math.isfinite(u)
            and math.isfinite(v)
        ):
            return False

    return True


def create_uv(obj):
    bpy.context.view_layer.objects.active = obj

    bpy.ops.object.select_all(
        action="DESELECT"
    )

    obj.select_set(True)

    bpy.ops.object.mode_set(
        mode="EDIT"
    )

    bpy.ops.mesh.select_all(
        action="SELECT"
    )

    bpy.ops.uv.smart_project(
        angle_limit=math.radians(66.0),
        island_margin=0.025,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=True,
    )

    bpy.ops.object.mode_set(
        mode="OBJECT"
    )


clear_scene()
load_source()

obj = join_meshes(
    mesh_objects()
)

source_uv_valid = uv_valid(obj)
uv_generated = False

if not source_uv_valid:
    create_uv(obj)
    uv_generated = True

if not uv_valid(obj):
    raise RuntimeError(
        "UV_GENERATION_FAILED"
    )

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

bpy.ops.object.select_all(
    action="DESELECT"
)

obj.select_set(True)

bpy.context.view_layer.objects.active = obj

bpy.ops.export_scene.gltf(
    filepath=str(OUTPUT),
    export_format="GLB",
    use_selection=True,
)

report = {
    "source": str(SOURCE),
    "output": str(OUTPUT),
    "objects": 1,
    "vertices": len(obj.data.vertices),
    "faces": len(obj.data.polygons),
    "loops": len(obj.data.loops),
    "uv_layers": len(obj.data.uv_layers),
    "uv_loops": len(
        obj.data.uv_layers.active.data
    ),
    "source_uv_valid": source_uv_valid,
    "uv_generated": uv_generated,
    "output_exists": OUTPUT.is_file(),
}

REPORT.write_text(
    json.dumps(
        report,
        indent=2,
    ),
    encoding="utf-8",
)

print(json.dumps(report, indent=2))
print("PREPROCESS=PASS")
