from __future__ import annotations

from pathlib import Path
from PIL import (
    Image,
    ImageEnhance,
    ImageFilter,
    ImageOps,
)


def derive_pbr(
    base_color: Path,
    output: Path,
) -> dict[str, str]:
    image = Image.open(
        base_color
    ).convert("RGB")

    gray = ImageOps.grayscale(
        image
    )

    roughness = (
        ImageEnhance.Contrast(
            gray
        )
        .enhance(0.65)
        .filter(
            ImageFilter.GaussianBlur(
                radius=1.2
            )
        )
    )

    roughness = ImageOps.autocontrast(
        roughness
    )

    metallic = Image.new(
        "L",
        image.size,
        72,
    )

    height = ImageEnhance.Contrast(
        gray
    ).enhance(1.35)

    normal = Image.new(
        "RGB",
        image.size,
        (
            128,
            128,
            255,
        ),
    )

    roughness_path = (
        output
        / "roughness.png"
    )

    metallic_path = (
        output
        / "metallic.png"
    )

    height_path = (
        output
        / "height_proxy.png"
    )

    normal_path = (
        output
        / "normal_neutral.png"
    )

    roughness.save(
        roughness_path
    )

    metallic.save(
        metallic_path
    )

    height.save(
        height_path
    )

    normal.save(
        normal_path
    )

    return {
        "roughness":
            str(roughness_path),

        "metallic":
            str(metallic_path),

        "height_proxy":
            str(height_path),

        "normal":
            str(normal_path),

        "normal_classification":
            "NEUTRAL_SAFE_FALLBACK",

        "pbr_classification":
            "DERIVED_NOT_GROUND_TRUTH",
    }
