from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw

from nexus.runtime.vision import (
    OllamaVisionProvider,
)


@dataclass
class GroundedTarget:
    x: float
    y: float
    confidence: float
    label: str
    raw: str


def _json_object(text):
    text = str(
        text or ""
    ).strip()

    try:
        value = json.loads(
            text
        )

        if isinstance(
            value,
            dict,
        ):
            return value

    except Exception:
        pass

    fenced = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```",
        text,
        re.S | re.I,
    )

    if fenced:
        return json.loads(
            fenced.group(1)
        )

    loose = re.search(
        r"\{.*\}",
        text,
        re.S,
    )

    if loose:
        return json.loads(
            loose.group(0)
        )

    raise ValueError(
        "VISION_GROUNDING_JSON_MISSING"
    )


def _analyze(
    image_path,
    model,
    prompt,
):
    provider = OllamaVisionProvider(
        model
    )

    final_prompt = (
        "/no_think\n"
        "Do not show reasoning. "
        "Return only the requested JSON.\n\n"
        + prompt
    )

    failures = []

    for budget in (
        512,
        1024,
        1536,
    ):
        try:
            finding = provider.analyze(
                str(image_path),
                final_prompt,
                num_predict=budget,
            )

            if str(
                finding.summary
            ).strip():
                return (
                    finding,
                    budget,
                )

        except RuntimeError as exc:
            text = str(exc)

            failures.append(
                f"{budget}:{text}"
            )

            if (
                "VISION_EMPTY_RESPONSE"
                not in text
            ):
                raise

    raise RuntimeError(
        "VISION_FINAL_ANSWER_EXHAUSTED="
        + ";".join(
            failures
        )
    )


def _coarse_box(
    image_path,
    model,
    target,
    width,
    height,
):
    finding, budget = _analyze(
        image_path,
        model,
        f"""
Locate this visible UI target:

{target}

Image dimensions:
width={int(width)}
height={int(height)}

Return JSON only:

{{
  "left": <pixel x>,
  "top": <pixel y>,
  "right": <pixel x>,
  "bottom": <pixel y>,
  "confidence": <0 to 1>,
  "label": "<visible label>"
}}

Give the visible target's bounding rectangle.
Coordinates must be absolute image pixels.
If the target is not visible, confidence must be 0.
""",
    )

    data = _json_object(
        finding.summary
    )

    return (
        {
            "left": float(
                data["left"]
            ),
            "top": float(
                data["top"]
            ),
            "right": float(
                data["right"]
            ),
            "bottom": float(
                data["bottom"]
            ),
            "confidence": float(
                data.get(
                    "confidence",
                    0,
                )
            ),
            "label": str(
                data.get(
                    "label",
                    "",
                )
            ),
        },
        finding.summary,
        budget,
    )


def _make_refinement_crop(
    image_path,
    box,
):
    source = Path(
        image_path
    ).resolve()

    image = Image.open(
        source
    ).convert(
        "RGB"
    )

    width, height = (
        image.size
    )

    box_width = max(
        1,
        box["right"]
        - box["left"],
    )

    box_height = max(
        1,
        box["bottom"]
        - box["top"],
    )

    margin_x = max(
        120,
        box_width * 1.25,
    )

    margin_y = max(
        120,
        box_height * 1.25,
    )

    left = max(
        0,
        int(
            box["left"]
            - margin_x
        ),
    )

    top = max(
        0,
        int(
            box["top"]
            - margin_y
        ),
    )

    right = min(
        width,
        int(
            box["right"]
            + margin_x
        ),
    )

    bottom = min(
        height,
        int(
            box["bottom"]
            + margin_y
        ),
    )

    # Guarantee a useful refinement region.
    if (
        right - left
        < 350
    ):
        center = (
            left + right
        ) // 2

        left = max(
            0,
            center - 175,
        )

        right = min(
            width,
            center + 175,
        )

    if (
        bottom - top
        < 300
    ):
        center = (
            top + bottom
        ) // 2

        top = max(
            0,
            center - 150,
        )

        bottom = min(
            height,
            center + 150,
        )

    crop = image.crop(
        (
            left,
            top,
            right,
            bottom,
        )
    )

    crop_path = (
        source.parent
        / (
            source.stem
            + "_refinement.png"
        )
    )

    crop.save(
        crop_path
    )

    return (
        str(crop_path),
        left,
        top,
        crop.width,
        crop.height,
    )


def _fine_point(
    crop_path,
    model,
    target,
    crop_width,
    crop_height,
):
    finding, budget = _analyze(
        crop_path,
        model,
        f"""
This is a cropped screenshot containing or surrounding
the requested UI target.

Target:
{target}

Crop dimensions:
width={int(crop_width)}
height={int(crop_height)}

Return JSON only:

{{
  "x": <center pixel x inside this crop>,
  "y": <center pixel y inside this crop>,
  "confidence": <0 to 1>,
  "label": "<visible label>"
}}

Point to the CENTER of the requested visible control.
Coordinates are relative to this cropped image.
If the target is not visible, confidence must be 0.
""",
    )

    data = _json_object(
        finding.summary
    )

    return (
        {
            "x": float(
                data["x"]
            ),
            "y": float(
                data["y"]
            ),
            "confidence": float(
                data.get(
                    "confidence",
                    0,
                )
            ),
            "label": str(
                data.get(
                    "label",
                    "",
                )
            ),
        },
        finding.summary,
        budget,
    )


def ground_target(
    image_path,
    model,
    target,
    width,
    height,
):
    coarse, coarse_raw, coarse_budget = (
        _coarse_box(
            image_path,
            model,
            target,
            width,
            height,
        )
    )

    if (
        coarse["confidence"]
        < 0.35
    ):
        raise ValueError(
            "VISION_COARSE_GROUNDING_LOW_CONFIDENCE="
            + str(
                coarse[
                    "confidence"
                ]
            )
        )

    if not (
        0
        <= coarse["left"]
        < coarse["right"]
        <= float(width)
        and
        0
        <= coarse["top"]
        < coarse["bottom"]
        <= float(height)
    ):
        raise ValueError(
            "VISION_COARSE_BOX_OUT_OF_BOUNDS"
        )

    (
        crop_path,
        offset_x,
        offset_y,
        crop_width,
        crop_height,
    ) = _make_refinement_crop(
        image_path,
        coarse,
    )

    fine, fine_raw, fine_budget = (
        _fine_point(
            crop_path,
            model,
            target,
            crop_width,
            crop_height,
        )
    )

    if (
        fine["confidence"]
        < 0.40
    ):
        raise ValueError(
            "VISION_FINE_GROUNDING_LOW_CONFIDENCE="
            + str(
                fine[
                    "confidence"
                ]
            )
        )

    if not (
        0
        <= fine["x"]
        <= crop_width
        and
        0
        <= fine["y"]
        <= crop_height
    ):
        raise ValueError(
            "VISION_FINE_POINT_OUT_OF_BOUNDS"
        )

    final_x = (
        offset_x
        + fine["x"]
    )

    final_y = (
        offset_y
        + fine["y"]
    )

    if not (
        0 <= final_x <= width
        and
        0 <= final_y <= height
    ):
        raise ValueError(
            "VISION_FINAL_POINT_OUT_OF_BOUNDS"
        )

    raw = json.dumps(
        {
            "coarse": coarse,
            "coarse_budget": coarse_budget,
            "crop": {
                "path": crop_path,
                "offset_x": offset_x,
                "offset_y": offset_y,
                "width": crop_width,
                "height": crop_height,
            },
            "fine": fine,
            "fine_budget": fine_budget,
            "final": {
                "x": final_x,
                "y": final_y,
            },
            "coarse_raw": coarse_raw,
            "fine_raw": fine_raw,
        },
        ensure_ascii=False,
        indent=2,
    )

    return GroundedTarget(
        x=float(
            final_x
        ),
        y=float(
            final_y
        ),
        confidence=min(
            coarse["confidence"],
            fine["confidence"],
        ),
        label=(
            fine["label"]
            or coarse["label"]
        ),
        raw=raw,
    )


def verify_visual_state(
    image_path,
    model,
):
    finding, budget = _analyze(
        image_path,
        model,
        """
Inspect this visible UI screenshot.

Return JSON only:

{
  "armed": true or false,
  "typed_text": "<visible input text>",
  "success_visible": true or false
}

armed=true only if ARMED=YES is visibly displayed.
typed_text must be exactly what is visibly shown in the input.
success_visible=true only if SUCCESS is visibly shown.
Use pixels only. Do not infer hidden DOM state.
""",
    )

    data = _json_object(
        finding.summary
    )

    data[
        "_vision_token_budget"
    ] = budget

    return (
        data,
        finding.summary,
    )
