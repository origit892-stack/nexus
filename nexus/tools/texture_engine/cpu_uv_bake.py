from __future__ import annotations

from pathlib import Path
from PIL import (
    Image,
    ImageFilter,
)
import json
import math
import sys


REFERENCE = Path(
    sys.argv[1]
).resolve()

CORRESPONDENCE = Path(
    sys.argv[2]
).resolve()

OUTPUT = Path(
    sys.argv[3]
).resolve()

RESOLUTION = int(
    sys.argv[4]
)


reference = Image.open(
    REFERENCE
).convert("RGB")

mapping = json.loads(
    CORRESPONDENCE.read_text(
        encoding="utf-8"
    )
)

triangles = mapping[
    "triangles"
]

src_width = (
    reference.width
)

src_height = (
    reference.height
)

src_pixels = (
    reference.load()
)

target = Image.new(
    "RGB",
    (
        RESOLUTION,
        RESOLUTION,
    ),
    (
        0,
        0,
        0,
    ),
)

target_pixels = (
    target.load()
)

coverage = Image.new(
    "L",
    (
        RESOLUTION,
        RESOLUTION,
    ),
    0,
)

coverage_pixels = (
    coverage.load()
)


def clamp(
    value,
    low,
    high,
):
    return max(
        low,
        min(
            high,
            value,
        ),
    )


def barycentric(
    px,
    py,
    a,
    b,
    c,
):
    denominator = (
        (
            b[1] - c[1]
        )
        * (
            a[0] - c[0]
        )
        + (
            c[0] - b[0]
        )
        * (
            a[1] - c[1]
        )
    )

    if abs(
        denominator
    ) <= 1e-12:
        return None

    w0 = (
        (
            b[1] - c[1]
        )
        * (
            px - c[0]
        )
        + (
            c[0] - b[0]
        )
        * (
            py - c[1]
        )
    ) / denominator

    w1 = (
        (
            c[1] - a[1]
        )
        * (
            px - c[0]
        )
        + (
            a[0] - c[0]
        )
        * (
            py - c[1]
        )
    ) / denominator

    w2 = (
        1.0
        - w0
        - w1
    )

    return (
        w0,
        w1,
        w2,
    )


def uv_to_target(
    uv,
):
    u = float(
        uv[0]
    )

    v = float(
        uv[1]
    )

    return (
        u
        * (
            RESOLUTION - 1
        ),
        (
            1.0 - v
        )
        * (
            RESOLUTION - 1
        ),
    )


def uv_to_source(
    uv,
):
    u = clamp(
        float(
            uv[0]
        ),
        0.0,
        1.0,
    )

    v = clamp(
        float(
            uv[1]
        ),
        0.0,
        1.0,
    )

    return (
        u
        * (
            src_width - 1
        ),
        (
            1.0 - v
        )
        * (
            src_height - 1
        ),
    )


def sample_bilinear(
    x,
    y,
):
    x = clamp(
        x,
        0.0,
        src_width - 1.0,
    )

    y = clamp(
        y,
        0.0,
        src_height - 1.0,
    )

    x0 = int(
        math.floor(x)
    )

    y0 = int(
        math.floor(y)
    )

    x1 = min(
        x0 + 1,
        src_width - 1,
    )

    y1 = min(
        y0 + 1,
        src_height - 1,
    )

    tx = x - x0
    ty = y - y0

    c00 = src_pixels[
        x0,
        y0,
    ]

    c10 = src_pixels[
        x1,
        y0,
    ]

    c01 = src_pixels[
        x0,
        y1,
    ]

    c11 = src_pixels[
        x1,
        y1,
    ]

    result = []

    for channel in range(3):
        top = (
            c00[channel]
            * (
                1.0 - tx
            )
            + c10[channel]
            * tx
        )

        bottom = (
            c01[channel]
            * (
                1.0 - tx
            )
            + c11[channel]
            * tx
        )

        value = (
            top
            * (
                1.0 - ty
            )
            + bottom
            * ty
        )

        result.append(
            int(
                round(
                    clamp(
                        value,
                        0.0,
                        255.0,
                    )
                )
            )
        )

    return tuple(
        result
    )


rasterized = 0
degenerate = 0
written_pixels = 0

for triangle in triangles:
    destination = [
        uv_to_target(
            uv
        )
        for uv in triangle[
            "destination_uv"
        ]
    ]

    source = [
        uv_to_source(
            uv
        )
        for uv in triangle[
            "source_uv"
        ]
    ]

    min_x = max(
        0,
        int(
            math.floor(
                min(
                    point[0]
                    for point
                    in destination
                )
            )
        ),
    )

    max_x = min(
        RESOLUTION - 1,
        int(
            math.ceil(
                max(
                    point[0]
                    for point
                    in destination
                )
            )
        ),
    )

    min_y = max(
        0,
        int(
            math.floor(
                min(
                    point[1]
                    for point
                    in destination
                )
            )
        ),
    )

    max_y = min(
        RESOLUTION - 1,
        int(
            math.ceil(
                max(
                    point[1]
                    for point
                    in destination
                )
            )
        ),
    )

    center_test = barycentric(
        (
            destination[0][0]
            + destination[1][0]
            + destination[2][0]
        ) / 3.0,
        (
            destination[0][1]
            + destination[1][1]
            + destination[2][1]
        ) / 3.0,
        destination[0],
        destination[1],
        destination[2],
    )

    if center_test is None:
        degenerate += 1
        continue

    rasterized += 1

    for y in range(
        min_y,
        max_y + 1,
    ):
        py = y + 0.5

        for x in range(
            min_x,
            max_x + 1,
        ):
            px = x + 0.5

            weights = barycentric(
                px,
                py,
                destination[0],
                destination[1],
                destination[2],
            )

            if weights is None:
                continue

            w0, w1, w2 = weights

            epsilon = -1e-7

            if (
                w0 < epsilon
                or w1 < epsilon
                or w2 < epsilon
            ):
                continue

            source_x = (
                w0
                * source[0][0]
                + w1
                * source[1][0]
                + w2
                * source[2][0]
            )

            source_y = (
                w0
                * source[0][1]
                + w1
                * source[1][1]
                + w2
                * source[2][1]
            )

            target_pixels[
                x,
                y,
            ] = sample_bilinear(
                source_x,
                source_y,
            )

            if coverage_pixels[
                x,
                y
            ] == 0:
                written_pixels += 1

            coverage_pixels[
                x,
                y,
            ] = 255


if rasterized <= 0:
    raise RuntimeError(
        "NO_TRIANGLES_RASTERIZED"
    )

if written_pixels <= 0:
    raise RuntimeError(
        "NO_PIXELS_WRITTEN"
    )


for _ in range(8):
    expanded_mask = (
        coverage.filter(
            ImageFilter.MaxFilter(
                size=3
            )
        )
    )

    blurred = target.filter(
        ImageFilter.BoxBlur(
            radius=1
        )
    )

    old_mask = coverage

    new_pixels = (
        expanded_mask.load()
    )

    old_pixels = (
        old_mask.load()
    )

    blur_pixels = (
        blurred.load()
    )

    target_pixels = (
        target.load()
    )

    changed = 0

    for y in range(
        RESOLUTION
    ):
        for x in range(
            RESOLUTION
        ):
            if (
                old_pixels[
                    x,
                    y
                ] == 0
                and new_pixels[
                    x,
                    y
                ] > 0
            ):
                target_pixels[
                    x,
                    y
                ] = blur_pixels[
                    x,
                    y
                ]

                changed += 1

    coverage = expanded_mask

    if changed == 0:
        break


OUTPUT.parent.mkdir(
    parents=True,
    exist_ok=True,
)

target.save(
    OUTPUT
)

coverage_path = (
    OUTPUT.parent
    / "cpu_bake_coverage.png"
)

coverage.save(
    coverage_path
)

total_pixels = (
    RESOLUTION
    * RESOLUTION
)

report = {
    "reference":
        str(
            REFERENCE
        ),

    "correspondence":
        str(
            CORRESPONDENCE
        ),

    "output":
        str(
            OUTPUT
        ),

    "resolution":
        RESOLUTION,

    "triangle_count":
        len(
            triangles
        ),

    "rasterized_triangles":
        rasterized,

    "degenerate_triangles":
        degenerate,

    "written_pixels":
        written_pixels,

    "written_ratio":
        (
            written_pixels
            / total_pixels
        ),

    "coverage":
        str(
            coverage_path
        ),

    "method":
        "CPU_BARYCENTRIC_UV_RASTERIZATION",
}

report_path = (
    OUTPUT.parent
    / "cpu_bake.json"
)

report_path.write_text(
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
    "CPU_UV_BAKE=PASS"
)
