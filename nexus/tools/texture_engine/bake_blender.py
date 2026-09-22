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
    sys.argv[-6]
).resolve()

REFERENCE = Path(
    sys.argv[-5]
).resolve()

VIEWS = Path(
    sys.argv[-4]
).resolve()

OUTPUT = Path(
    sys.argv[-3]
).resolve()

RESOLUTION = int(
    sys.argv[-2]
)

REPORT = Path(
    sys.argv[-1]
).resolve()


views = json.loads(
    VIEWS.read_text(
        encoding="utf-8"
    )
)

hero = views[
    "views"
][
    "hero"
]


def clear_scene() -> None:
    bpy.ops.object.select_all(
        action="SELECT"
    )

    bpy.ops.object.delete(
        use_global=False
    )


def load_mesh() -> bpy.types.Object:
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
    scene: bpy.types.Scene,
) -> bpy.types.Object:
    data = bpy.data.cameras.new(
        "NexusProjectionCamera"
    )

    camera = bpy.data.objects.new(
        "NexusProjectionCamera",
        data,
    )

    bpy.context.collection.objects.link(
        camera
    )

    camera.location = Vector(
        hero[
            "camera_location"
        ]
    )

    target = Vector(
        hero[
            "target"
        ]
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
        hero[
            "ortho_scale"
        ]
    )

    scene.camera = camera

    bpy.context.view_layer.update()

    return camera


def create_projection_uv(
    scene: bpy.types.Scene,
    obj: bpy.types.Object,
    camera: bpy.types.Object,
) -> tuple[
    bpy.types.MeshUVLoopLayer,
    dict,
]:
    old = obj.data.uv_layers.get(
        "NexusProjectionUV"
    )

    if old is not None:
        obj.data.uv_layers.remove(
            old
        )

    projection = (
        obj.data.uv_layers.new(
            name="NexusProjectionUV"
        )
    )

    raw = []

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

            raw.append(
                (
                    loop_index,
                    float(
                        projected.x
                    ),
                    float(
                        projected.y
                    ),
                    float(
                        projected.z
                    ),
                )
            )

    if not raw:
        raise RuntimeError(
            "PROJECTION_HAS_NO_LOOPS"
        )

    u_min = min(
        item[1]
        for item in raw
    )

    u_max = max(
        item[1]
        for item in raw
    )

    v_min = min(
        item[2]
        for item in raw
    )

    v_max = max(
        item[2]
        for item in raw
    )

    depth_min = min(
        item[3]
        for item in raw
    )

    depth_max = max(
        item[3]
        for item in raw
    )

    u_span = (
        u_max - u_min
    )

    v_span = (
        v_max - v_min
    )

    if u_span <= 1e-12:
        raise RuntimeError(
            "PROJECTION_U_SPAN_ZERO"
        )

    if v_span <= 1e-12:
        raise RuntimeError(
            "PROJECTION_V_SPAN_ZERO"
        )

    front = sum(
        1
        for item in raw
        if item[3] > 0.0
    )

    front_ratio = (
        front
        / len(raw)
    )

    if front_ratio < 0.999999:
        raise RuntimeError(
            "PROJECTION_DEPTH_FAILED="
            + str(
                front_ratio
            )
        )

    margin = 0.03

    fitted_inside = 0

    fitted_u_min = float(
        "inf"
    )

    fitted_u_max = float(
        "-inf"
    )

    fitted_v_min = float(
        "inf"
    )

    fitted_v_max = float(
        "-inf"
    )

    raw_inside = 0

    for (
        loop_index,
        raw_u,
        raw_v,
        depth,
    ) in raw:
        if (
            0.0 <= raw_u <= 1.0
            and
            0.0 <= raw_v <= 1.0
        ):
            raw_inside += 1

        normalized_u = (
            raw_u - u_min
        ) / u_span

        normalized_v = (
            raw_v - v_min
        ) / v_span

        u = (
            margin
            + normalized_u
            * (
                1.0
                - 2.0 * margin
            )
        )

        v = (
            margin
            + normalized_v
            * (
                1.0
                - 2.0 * margin
            )
        )

        projection.data[
            loop_index
        ].uv = (
            u,
            v,
        )

        fitted_u_min = min(
            fitted_u_min,
            u,
        )

        fitted_u_max = max(
            fitted_u_max,
            u,
        )

        fitted_v_min = min(
            fitted_v_min,
            v,
        )

        fitted_v_max = max(
            fitted_v_max,
            v,
        )

        if (
            0.0 <= u <= 1.0
            and
            0.0 <= v <= 1.0
        ):
            fitted_inside += 1

    raw_inside_ratio = (
        raw_inside
        / len(raw)
    )

    fitted_inside_ratio = (
        fitted_inside
        / len(raw)
    )

    diagnostics = {
        "count":
            len(raw),

        "front":
            front,

        "front_ratio":
            front_ratio,

        "depth_min":
            depth_min,

        "depth_max":
            depth_max,

        "raw_u_min":
            u_min,

        "raw_u_max":
            u_max,

        "raw_v_min":
            v_min,

        "raw_v_max":
            v_max,

        "raw_inside":
            raw_inside,

        "raw_inside_ratio":
            raw_inside_ratio,

        "fit_margin":
            margin,

        "fitted_u_min":
            fitted_u_min,

        "fitted_u_max":
            fitted_u_max,

        "fitted_v_min":
            fitted_v_min,

        "fitted_v_max":
            fitted_v_max,

        "fitted_inside":
            fitted_inside,

        "fitted_inside_ratio":
            fitted_inside_ratio,

        "fit_method":
            "CANONICAL_CAMERA_AFFINE_FRAME_FIT",
    }

    print(
        "PROJECTION_DIAGNOSTICS="
        + json.dumps(
            diagnostics,
            sort_keys=True,
        )
    )

    if fitted_inside_ratio < 0.999999:
        raise RuntimeError(
            "PROJECTION_FIT_FAILED="
            + json.dumps(
                diagnostics,
                sort_keys=True,
            )
        )

    return (
        projection,
        diagnostics,
    )



def configure_material(
    obj: bpy.types.Object,
    projection: bpy.types.MeshUVLoopLayer,
    reference: bpy.types.Image,
    target_image: bpy.types.Image,
) -> None:
    material = (
        bpy.data.materials.new(
            "NexusBakeMaterial"
        )
    )

    material.use_nodes = True

    nodes = (
        material
        .node_tree
        .nodes
    )

    links = (
        material
        .node_tree
        .links
    )

    for node in list(nodes):
        nodes.remove(
            node
        )

    output_node = nodes.new(
        "ShaderNodeOutputMaterial"
    )

    emission = nodes.new(
        "ShaderNodeEmission"
    )

    reference_node = nodes.new(
        "ShaderNodeTexImage"
    )

    reference_node.image = (
        reference
    )

    reference_node.extension = (
        "CLIP"
    )

    projection_node = nodes.new(
        "ShaderNodeUVMap"
    )

    projection_node.uv_map = (
        projection.name
    )

    target_node = nodes.new(
        "ShaderNodeTexImage"
    )

    target_node.image = (
        target_image
    )

    target_node.select = True

    nodes.active = (
        target_node
    )

    links.new(
        projection_node.outputs[
            "UV"
        ],
        reference_node.inputs[
            "Vector"
        ],
    )

    links.new(
        reference_node.outputs[
            "Color"
        ],
        emission.inputs[
            "Color"
        ],
    )

    links.new(
        emission.outputs[
            "Emission"
        ],
        output_node.inputs[
            "Surface"
        ],
    )

    obj.data.materials.clear()

    obj.data.materials.append(
        material
    )


def select_bake_engine(
    scene: bpy.types.Scene,
) -> str:
    available = [
        item.identifier
        for item in (
            bpy.types.RenderSettings
            .bl_rna
            .properties[
                "engine"
            ]
            .enum_items
        )
    ]

    if "BLENDER_EEVEE" in available:
        scene.render.engine = (
            "BLENDER_EEVEE"
        )

        return (
            "BLENDER_EEVEE"
        )

    if "CYCLES" in available:
        scene.render.engine = (
            "CYCLES"
        )

        return "CYCLES"

    raise RuntimeError(
        "NO_BAKE_ENGINE="
        + repr(
            available
        )
    )


def save_image(
    image: bpy.types.Image,
    scene: bpy.types.Scene,
) -> None:
    OUTPUT.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    image.filepath_raw = str(
        OUTPUT
    )

    image.file_format = (
        "PNG"
    )

    primary_error = None

    try:
        image.save()

    except Exception as exc:
        primary_error = repr(
            exc
        )

        print(
            "IMAGE_SAVE_PRIMARY_ERROR="
            + primary_error
        )

    if not OUTPUT.is_file():
        scene.render.image_settings.file_format = (
            "PNG"
        )

        try:
            image.save_render(
                filepath=str(
                    OUTPUT
                ),
                scene=scene,
            )

        except Exception as exc:
            print(
                "IMAGE_SAVE_RENDER_ERROR="
                + repr(
                    exc
                )
            )

    if not OUTPUT.is_file():
        raise RuntimeError(
            "BAKED_IMAGE_SAVE_FAILED="
            + str(
                OUTPUT
            )
            + " PRIMARY_ERROR="
            + str(
                primary_error
            )
        )

    if OUTPUT.stat().st_size <= 0:
        raise RuntimeError(
            "BAKED_IMAGE_EMPTY="
            + str(
                OUTPUT
            )
        )


clear_scene()

scene = bpy.context.scene

obj = load_mesh()

if not obj.data.uv_layers:
    raise RuntimeError(
        "SOURCE_UV_MISSING"
    )

source_uv = (
    obj.data
    .uv_layers
    .active
)

camera = create_camera(
    scene
)

projection, projection_report = (
    create_projection_uv(
        scene,
        obj,
        camera,
    )
)

reference = bpy.data.images.load(
    str(
        REFERENCE
    )
)

target_image = (
    bpy.data.images.new(
        "NexusBaseColor",
        width=RESOLUTION,
        height=RESOLUTION,
        alpha=False,
    )
)

target_image.generated_color = (
    0.18,
    0.18,
    0.18,
    1.0,
)

configure_material(
    obj,
    projection,
    reference,
    target_image,
)

obj.data.uv_layers.active = (
    source_uv
)

try:
    source_uv.active_render = True
except Exception:
    pass

engine = select_bake_engine(
    scene
)

scene.render.bake.margin = 32
scene.render.bake.use_clear = True

bpy.ops.object.select_all(
    action="DESELECT"
)

obj.select_set(
    True
)

bpy.context.view_layer.objects.active = (
    obj
)

bpy.ops.object.bake(
    type="EMIT"
)

save_image(
    target_image,
    scene,
)

report = {
    "mesh":
        str(
            MESH
        ),

    "reference":
        str(
            REFERENCE
        ),

    "output":
        str(
            OUTPUT
        ),

    "resolution":
        RESOLUTION,

    "source_uv":
        source_uv.name,

    "projection_uv":
        projection.name,

    "projection":
        projection_report,

    "engine":
        engine,

    "output_exists":
        OUTPUT.is_file(),

    "output_bytes":
        (
            OUTPUT.stat().st_size
            if OUTPUT.is_file()
            else 0
        ),

    "image_filepath_raw":
        target_image.filepath_raw,

    "image_file_format":
        target_image.file_format,

    "image_size": [
        int(
            target_image.size[0]
        ),
        int(
            target_image.size[1]
        ),
    ],
}

REPORT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

REPORT.write_text(
    json.dumps(
        report,
        indent=2,
    ),
    encoding="utf-8",
)

print(
    json.dumps(
        report,
        indent=2,
    )
)

print(
    "TEXTURE_BAKE=PASS"
)
