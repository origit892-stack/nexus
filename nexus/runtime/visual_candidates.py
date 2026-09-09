from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from pathlib import Path

from PIL import (
    Image,
    ImageDraw,
    ImageFont,
)


@dataclass
class VisualCandidate:
    candidate_id: int
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self):
        return (
            self.right
            - self.left
        )

    @property
    def height(self):
        return (
            self.bottom
            - self.top
        )

    @property
    def center_x(self):
        return (
            self.left
            + self.right
        ) / 2

    @property
    def center_y(self):
        return (
            self.top
            + self.bottom
        ) / 2


def _bright_mask(
    image,
):
    """
    Pixel-only UI candidate detection.

    The V9.1 sandbox deliberately uses large, high-contrast
    interactive controls. No DOM/accessibility information
    participates in candidate generation.
    """

    rgb = image.convert(
        "RGB"
    )

    width, height = rgb.size

    pixels = rgb.load()

    mask = bytearray(
        width * height
    )

    for y in range(
        height
    ):
        row = y * width

        for x in range(
            width
        ):
            r, g, b = pixels[
                x,
                y,
            ]

            luminance = (
                0.2126 * r
                + 0.7152 * g
                + 0.0722 * b
            )

            # The button / input are intentionally bright
            # relative to the dark sandbox.
            if luminance >= 145:
                mask[
                    row + x
                ] = 1

    return (
        mask,
        width,
        height,
    )


def _components(
    mask,
    width,
    height,
):
    visited = bytearray(
        len(mask)
    )

    components = []

    # 4-neighbour flood-fill.
    for y in range(
        height
    ):
        for x in range(
            width
        ):
            index = (
                y * width
                + x
            )

            if (
                not mask[index]
                or visited[index]
            ):
                continue

            queue = deque(
                [
                    (
                        x,
                        y,
                    )
                ]
            )

            visited[
                index
            ] = 1

            min_x = max_x = x
            min_y = max_y = y
            count = 0

            while queue:
                cx, cy = (
                    queue.popleft()
                )

                count += 1

                min_x = min(
                    min_x,
                    cx,
                )

                max_x = max(
                    max_x,
                    cx,
                )

                min_y = min(
                    min_y,
                    cy,
                )

                max_y = max(
                    max_y,
                    cy,
                )

                for nx, ny in (
                    (
                        cx - 1,
                        cy,
                    ),
                    (
                        cx + 1,
                        cy,
                    ),
                    (
                        cx,
                        cy - 1,
                    ),
                    (
                        cx,
                        cy + 1,
                    ),
                ):
                    if not (
                        0 <= nx < width
                        and
                        0 <= ny < height
                    ):
                        continue

                    ni = (
                        ny * width
                        + nx
                    )

                    if (
                        mask[ni]
                        and not visited[ni]
                    ):
                        visited[
                            ni
                        ] = 1

                        queue.append(
                            (
                                nx,
                                ny,
                            )
                        )

            components.append(
                {
                    "left": min_x,
                    "top": min_y,
                    "right": (
                        max_x + 1
                    ),
                    "bottom": (
                        max_y + 1
                    ),
                    "pixels": count,
                }
            )

    return components


def detect_candidates(
    image_path,
):
    image = Image.open(
        image_path
    ).convert(
        "RGB"
    )

    mask, width, height = (
        _bright_mask(
            image
        )
    )

    raw = _components(
        mask,
        width,
        height,
    )

    candidates = []

    for item in raw:
        w = (
            item["right"]
            - item["left"]
        )

        h = (
            item["bottom"]
            - item["top"]
        )

        area = (
            w * h
        )

        fill = (
            item["pixels"]
            / max(
                1,
                area,
            )
        )

        # Large visible controls only.
        if w < 120:
            continue

        if h < 35:
            continue

        if w > (
            width * 0.90
        ):
            continue

        if h > (
            height * 0.40
        ):
            continue

        # Connected bright structure should occupy a
        # meaningful portion of the box.
        if fill < 0.10:
            continue

        candidates.append(
            item
        )

    # Larger candidates first, then top-to-bottom.
    candidates.sort(
        key=lambda x: (
            x["top"],
            x["left"],
            -(
                (
                    x["right"]
                    - x["left"]
                )
                * (
                    x["bottom"]
                    - x["top"]
                )
            ),
        )
    )

    result = []

    for candidate_id, item in enumerate(
        candidates,
        start=1,
    ):
        result.append(
            VisualCandidate(
                candidate_id=(
                    candidate_id
                ),
                left=item[
                    "left"
                ],
                top=item[
                    "top"
                ],
                right=item[
                    "right"
                ],
                bottom=item[
                    "bottom"
                ],
            )
        )

    return (
        result,
        width,
        height,
    )


def annotate_candidates(
    image_path,
    candidates,
    output_path,
):
    image = Image.open(
        image_path
    ).convert(
        "RGB"
    )

    draw = ImageDraw.Draw(
        image
    )

    for candidate in candidates:
        # No custom colors are semantically relevant here;
        # annotation exists only for machine grounding.
        draw.rectangle(
            (
                candidate.left,
                candidate.top,
                candidate.right,
                candidate.bottom,
            ),
            outline=(
                255,
                0,
                0,
            ),
            width=5,
        )

        label = (
            f"C{candidate.candidate_id}"
        )

        x = (
            candidate.left + 5
        )

        y = max(
            0,
            candidate.top - 24,
        )

        draw.rectangle(
            (
                x,
                y,
                x + 55,
                y + 23,
            ),
            fill=(
                255,
                255,
                0,
            ),
        )

        draw.text(
            (
                x + 4,
                y + 3,
            ),
            label,
            fill=(
                0,
                0,
                0,
            ),
        )

    output = Path(
        output_path
    )

    image.save(
        output
    )

    return str(
        output
    )
