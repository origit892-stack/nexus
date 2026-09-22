from __future__ import annotations

import bpy
import json
from mathutils import Vector
from pathlib import Path
import sys

MESH = Path(sys.argv[-2]).resolve()
OUTPUT = Path(sys.argv[-1]).resolve()

OUTPUT.mkdir(
    parents=True,
    exist_ok=True,
)

bpy.ops.object.select_all(action="SELECT")
bpy.ops.object.delete(use_global=False)

bpy.ops.import_scene.gltf(
    filepath=str(MESH)
)

objects = [
    obj
    for obj in bpy.context.scene.objects
    if obj.type == "MESH"
]

if not objects:
    raise RuntimeError("NO_MESH_OBJECTS")

minimum = Vector((
    float("inf"),
    float("inf"),
    float("inf"),
))

maximum = Vector((
    float("-inf"),
    float("-inf"),
    float("-inf"),
))

for obj in objects:
    for corner in obj.bound_box:
        point = (
            obj.matrix_world
            @ Vector(corner)
        )

        minimum.x = min(
            minimum.x,
            point.x,
        )
        minimum.y = min(
            minimum.y,
            point.y,
        )
        minimum.z = min(
            minimum.z,
            point.z,
        )

        maximum.x = max(
            maximum.x,
            point.x,
        )
        maximum.y = max(
            maximum.y,
            point.y,
        )
        maximum.z = max(
            maximum.z,
            point.z,
        )

center = (
    minimum + maximum
) * 0.5

dimensions = (
    maximum - minimum
)

longest = max(
    dimensions.x,
    dimensions.y,
    dimensions.z,
)

if longest <= 0:
    raise RuntimeError(
        "DEGENERATE_MESH"
    )

distance = longest * 2.8
ortho_scale = longest * 1.35

scene = bpy.context.scene

available = [
    item.identifier
    for item in (
        bpy.types.RenderSettings
        .bl_rna
        .properties["engine"]
        .enum_items
    )
]

if "BLENDER_EEVEE" not in available:
    raise RuntimeError(
        "BLENDER_EEVEE_UNAVAILABLE="
        + repr(available)
    )

scene.render.engine = "BLENDER_EEVEE"

scene.render.resolution_x = 768
scene.render.resolution_y = 768
scene.render.resolution_percentage = 100

scene.render.image_settings.file_format = (
    "PNG"
)

scene.render.film_transparent = False

world = bpy.data.worlds.new(
    "NexusTextureWorld"
)

world.use_nodes = True
scene.world = world

background = (
    world.node_tree.nodes.get(
        "Background"
    )
)

if background is not None:
    background.inputs[
        "Color"
    ].default_value = (
        0.07,
        0.07,
        0.07,
        1.0,
    )

    background.inputs[
        "Strength"
    ].default_value = 0.55


def look_at(obj):
    direction = (
        center - obj.location
    )

    obj.rotation_euler = (
        direction
        .to_track_quat(
            "-Z",
            "Y",
        )
        .to_euler()
    )


def add_light(
    name,
    location,
    energy,
    size,
):
    data = bpy.data.lights.new(
        name,
        "AREA",
    )

    data.energy = energy
    data.size = size

    light = bpy.data.objects.new(
        name,
        data,
    )

    bpy.context.collection.objects.link(
        light
    )

    light.location = location

    look_at(light)


add_light(
    "Key",
    center + Vector((
        distance,
        -distance,
        distance,
    )),
    1100,
    longest * 3.0,
)

add_light(
    "Fill",
    center + Vector((
        -distance,
        -distance * 0.5,
        distance * 0.5,
    )),
    550,
    longest * 2.5,
)

add_light(
    "Rim",
    center + Vector((
        0,
        distance,
        distance,
    )),
    450,
    longest * 2.0,
)

directions = {
    "front":
        Vector((0, -1, 0)),

    "back":
        Vector((0, 1, 0)),

    "left":
        Vector((-1, 0, 0)),

    "right":
        Vector((1, 0, 0)),

    "top":
        Vector((0, 0, 1)),

    "bottom":
        Vector((0, 0, -1)),

    "hero":
        Vector((
            1,
            -1,
            0.75,
        )).normalized(),
}

records = {}

for name, direction in directions.items():
    camera_data = bpy.data.cameras.new(
        "Camera_" + name
    )

    camera = bpy.data.objects.new(
        "Camera_" + name,
        camera_data,
    )

    bpy.context.collection.objects.link(
        camera
    )

    camera.location = (
        center
        + direction * distance
    )

    camera_data.type = "ORTHO"
    camera_data.ortho_scale = ortho_scale

    look_at(camera)

    scene.camera = camera

    target = (
        OUTPUT
        / (
            name + ".png"
        )
    )

    scene.render.filepath = str(
        target
    )

    bpy.ops.render.render(
        write_still=True
    )

    if not target.is_file():
        raise RuntimeError(
            "RENDER_MISSING="
            + name
        )

    records[name] = {
        "path":
            str(target),

        "camera_location": [
            float(value)
            for value
            in camera.location
        ],

        "target": [
            float(value)
            for value
            in center
        ],

        "direction": [
            float(value)
            for value
            in direction
        ],

        "ortho_scale":
            float(ortho_scale),
    }

    bpy.data.objects.remove(
        camera,
        do_unlink=True,
    )

report = {
    "mesh": str(MESH),

    "center": [
        float(value)
        for value
        in center
    ],

    "dimensions": [
        float(value)
        for value
        in dimensions
    ],

    "longest":
        float(longest),

    "views":
        records,

    "all_exist":
        all(
            Path(
                item["path"]
            ).is_file()
            for item
            in records.values()
        ),
}

(
    OUTPUT
    / "views.json"
).write_text(
    json.dumps(
        report,
        indent=2,
    ),
    encoding="utf-8",
)

print(json.dumps(report, indent=2))
print("MULTIVIEW_RENDER=PASS")
