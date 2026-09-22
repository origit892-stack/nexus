from __future__ import annotations


def generate_texture_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "mesh": {
                "type": "string",
                "description": (
                    "Workspace-relative OBJ, GLB, "
                    "or GLTF mesh path."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Desired materials, wear, surface "
                    "appearance, and art direction."
                ),
            },
            "reference_image": {
                "type": "string",
                "description": (
                    "Optional workspace-relative "
                    "appearance reference image."
                ),
            },
            "resolution": {
                "type": "integer",
                "enum": [
                    1024,
                    2048,
                    4096,
                ],
                "default": 2048,
            },
            "quality": {
                "type": "string",
                "enum": [
                    "fast",
                    "standard",
                    "high",
                ],
                "default": "standard",
            },
            "seed": {
                "type": "integer",
                "default": 1701,
            },
            "pbr": {
                "type": "boolean",
                "default": True,
            },
        },
        "required": [
            "mesh",
            "prompt",
        ],
        "additionalProperties": False,
    }
