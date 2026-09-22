from __future__ import annotations

import bpy
import json
from bpy_extras.object_utils import (
    world_to_camera_view,
)
from mathutils import Vector
from pathlib import Path
import sys


MESH = Path(
    sys.argv[-3]
).resolve()

VIEWS = Path(
    sys.argv[-2]
).resolve()

OUTPUT = Path(
    sys.argv[-1]
).resolve()

MARGIN = 0.03


def clear_scene():
    bpy.ops.object.select_all(
        action="SELECT"
    )

    bpy.ops.object.delete(
        use_global=False
    )


def load_mesh():
    bpy.ops.import_scene.gltf(
        filepath=str(MESH)
    )

    objects = [
        obj
        for obj in bpy.context.scene.objects
        if obj.type == "MESH"
    ]

    if not objects:
        raise RuntimeError(
            "NO_MESH_OBJECTS"
        )

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

    return (
        bpy.context.view_layer
        .objects.active
    )


def create_camera(
    scene,
    hero,
):
    data = bpy.data.cameras.new(
        "NexusCPUProjectionCamera"
    )

    camera = bpy.data.objects.new(
        "NexusCPUProjectionCamera",
        data,
    )

    bpy.context.collection.objects.link(
        camera
    )

    camera.location = Vector(
        hero["camera_location"]
    )

    target = Vector(
        hero["target"]
    )

    direction = (
        target
        - camera.location
    )

    camera.rotation_euler = (
        direction
        .to_track_quat(
            "-Z",
            "Y",
        )
        .to_euler()
    )

    data.type = "ORTHO"

    data.ortho_scale = float(
        hero["ortho_scale"]
    )

    scene.camera = camera

    bpy.context.view_layer.update()

    return camera


clear_scene()

view_data = json.loads(
    VIEWS.read_text(
        encoding="utf-8"
    )
)

hero = view_data[
    "views"
][
    "hero"
]

scene = bpy.context.scene

obj = load_mesh()

if not obj.data.uv_layers:
    raise RuntimeError(
        "SOURCE_UV_MISSING"
    )

source_uv = (
    obj.data.uv_layers.active
)

if source_uv is None:
    raise RuntimeError(
        "ACTIVE_SOURCE_UV_MISSING"
    )

camera = create_camera(
    scene,
    hero,
)

raw_projection = {}

u_values = []
v_values = []
depth_values = []

for polygon in obj.data.polygons:
    for loop_index in polygon.loop_indices:
        loop = obj.data.loops[
            loop_index
        ]

        vertex = obj.data.vertices[
            loop.vertex_index
        ]

        world = (
            obj.matrix_world
            @ vertex.co
        )

        projected = (
            world_to_camera_view(
                scene,
                camera,
                world,
            )
        )

        u = float(projected.x)
        v = float(projected.y)
        depth = float(projected.z)

        raw_projection[
            loop_index
        ] = (
            u,
            v,
            depth,
        )

        u_values.append(u)
        v_values.append(v)
        depth_values.append(depth)

if not u_values:
    raise RuntimeError(
        "NO_PROJECTED_LOOPS"
    )

u_min = min(u_values)
u_max = max(u_values)
v_min = min(v_values)
v_max = max(v_values)

u_span = u_max - u_min
v_span = v_max - v_min

if u_span <= 1e-12:
    raise RuntimeError(
        "PROJECTION_U_SPAN_ZERO"
    )

if v_span <= 1e-12:
    raise RuntimeError(
        "PROJECTION_V_SPAN_ZERO"
    )


def fit_u(value):
    return (
        MARGIN
        + (
            (value - u_min)
            / u_span
        )
        * (
            1.0
            - 2.0 * MARGIN
        )
    )


def fit_v(value):
    return (
        MARGIN
        + (
            (value - v_min)
            / v_span
        )
        * (
            1.0
            - 2.0 * MARGIN
        )
    )


triangles = []

for polygon in obj.data.polygons:
    if len(
        polygon.loop_indices
    ) != 3:
        raise RuntimeError(
            "NON_TRIANGULATED_POLYGON="
            + str(
                polygon.index
            )
        )

    dst = []
    src = []
    depth = []

    for loop_index in (
        polygon.loop_indices
    ):
        uv = source_uv.data[
            loop_index
        ].uv

        dst.append([
            float(uv.x),
            float(uv.y),
        ])

        raw_u, raw_v, raw_depth = (
            raw_projection[
                loop_index
            ]
        )

        src.append([
            float(
                fit_u(
                    raw_u
                )
            ),
            float(
                fit_v(
                    raw_v
                )
            ),
        ])

        depth.append(
            float(
                raw_depth
            )
        )

    triangles.append({
        "polygon":
            int(
                polygon.index
            ),

        "destination_uv":
            dst,

        "source_uv":
            src,

        "depth":
            depth,
    })

front = sum(
    1
    for value in depth_values
    if value > 0.0
)

report = {
    "mesh":
        str(MESH),

    "source_uv_layer":
        source_uv.name,

    "triangle_count":
        len(triangles),

    "loop_count":
        len(
            obj.data.loops
        ),

    "projection": {
        "raw_u_min":
            u_min,

        "raw_u_max":
            u_max,

        "raw_v_min":
            v_min,

        "raw_v_max":
            v_max,

        "margin":
            MARGIN,

        "fitted_u_min":
            MARGIN,

        "fitted_u_max":
            1.0 - MARGIN,

        "fitted_v_min":
            MARGIN,

        "fitted_v_max":
            1.0 - MARGIN,

        "front_ratio":
            (
                front
                / len(
                    depth_values
                )
            ),

        "fit_method":
            (
                "CANONICAL_CAMERA_"
                "AFFINE_FRAME_FIT"
            ),
    },

    "triangles":
        triangles,
}

if report[
    "projection"
][
    "front_ratio"
] < 0.999999:
    raise RuntimeError(
        "DEPTH_GATE_FAILED"
    )

OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

OUTPUT.write_text(
    json.dumps(
        report,
        separators=(
            ",",
            ":",
        ),
    ),
    encoding="utf-8",
)

print(
    "TRIANGLE_COUNT="
    + str(
        len(triangles)
    )
)

print(
    "LOOP_COUNT="
    + str(
        len(
            obj.data.loops
        )
    )
)

print(
    "FRONT_RATIO="
    + str(
        report[
            "projection"
        ][
            "front_ratio"
        ]
    )
)

print(
    "UV_CORRESPONDENCE_EXPORT=PASS"
)
