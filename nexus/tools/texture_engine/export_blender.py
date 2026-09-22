from __future__ import annotations

import bpy
import json
from pathlib import Path
import sys

MESH = Path(sys.argv[-7]).resolve()
BASE = Path(sys.argv[-6]).resolve()
ROUGHNESS = Path(sys.argv[-5]).resolve()
METALLIC = Path(sys.argv[-4]).resolve()
NORMAL = Path(sys.argv[-3]).resolve()
OUTPUT = Path(sys.argv[-2]).resolve()
REPORT = Path(sys.argv[-1]).resolve()

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

obj = bpy.context.view_layer.objects.active

if not obj.data.uv_layers:
    raise RuntimeError("NO_UV")

uv = obj.data.uv_layers.active

material = bpy.data.materials.new(
    "NexusGeneratedPBR"
)

material.use_nodes = True

nodes = material.node_tree.nodes
links = material.node_tree.links

for node in list(nodes):
    nodes.remove(node)

output_node = nodes.new(
    "ShaderNodeOutputMaterial"
)

principled = nodes.new(
    "ShaderNodeBsdfPrincipled"
)

uv_node = nodes.new(
    "ShaderNodeUVMap"
)

uv_node.uv_map = uv.name

base_node = nodes.new(
    "ShaderNodeTexImage"
)

base_node.image = bpy.data.images.load(
    str(BASE)
)

roughness_node = nodes.new(
    "ShaderNodeTexImage"
)

roughness_node.image = bpy.data.images.load(
    str(ROUGHNESS)
)

roughness_node.image.colorspace_settings.name = (
    "Non-Color"
)

metallic_node = nodes.new(
    "ShaderNodeTexImage"
)

metallic_node.image = bpy.data.images.load(
    str(METALLIC)
)

metallic_node.image.colorspace_settings.name = (
    "Non-Color"
)

normal_node = nodes.new(
    "ShaderNodeTexImage"
)

normal_node.image = bpy.data.images.load(
    str(NORMAL)
)

normal_node.image.colorspace_settings.name = (
    "Non-Color"
)

normal_map = nodes.new(
    "ShaderNodeNormalMap"
)

for texture in (
    base_node,
    roughness_node,
    metallic_node,
    normal_node,
):
    links.new(
        uv_node.outputs["UV"],
        texture.inputs["Vector"],
    )

links.new(
    base_node.outputs["Color"],
    principled.inputs["Base Color"],
)

links.new(
    roughness_node.outputs["Color"],
    principled.inputs["Roughness"],
)

links.new(
    metallic_node.outputs["Color"],
    principled.inputs["Metallic"],
)

links.new(
    normal_node.outputs["Color"],
    normal_map.inputs["Color"],
)

links.new(
    normal_map.outputs["Normal"],
    principled.inputs["Normal"],
)

links.new(
    principled.outputs["BSDF"],
    output_node.inputs["Surface"],
)

obj.data.materials.clear()
obj.data.materials.append(material)

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
    "mesh": str(MESH),
    "base_color": str(BASE),
    "roughness": str(ROUGHNESS),
    "metallic": str(METALLIC),
    "normal": str(NORMAL),
    "output": str(OUTPUT),
    "vertices": len(obj.data.vertices),
    "faces": len(obj.data.polygons),
    "loops": len(obj.data.loops),
    "uv": uv.name,
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
print("TEXTURED_GLB_EXPORT=PASS")
