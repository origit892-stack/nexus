from __future__ import annotations

import json
import re
from pathlib import Path

from nexus.runtime.vision import (
    OllamaVisionProvider,
)
from nexus.runtime.visual_candidates import (
    annotate_candidates,
    detect_candidates,
)


def _json_object(
    text,
):
    text = str(
        text or ""
    ).strip()

    try:
        result = json.loads(
            text
        )

        if isinstance(
            result,
            dict,
        ):
            return result

    except Exception:
        pass

    match = re.search(
        r"\{.*\}",
        text,
        re.S,
    )

    if not match:
        raise ValueError(
            "CANDIDATE_JSON_MISSING"
        )

    return json.loads(
        match.group(0)
    )


def select_visual_candidate(
    image_path,
    model,
    target,
    annotation_path,
):
    (
        candidates,
        width,
        height,
    ) = detect_candidates(
        image_path
    )

    if not candidates:
        raise RuntimeError(
            "NO_VISUAL_CANDIDATES"
        )

    annotated = annotate_candidates(
        image_path,
        candidates,
        annotation_path,
    )

    provider = OllamaVisionProvider(
        model
    )

    descriptions = "\n".join(
        (
            f"C{x.candidate_id}: "
            f"box=({x.left},{x.top})-"
            f"({x.right},{x.bottom})"
        )
        for x in candidates
    )

    prompt = f"""
/no_think
Do not provide reasoning.

This screenshot contains visible red boxes labelled
C1, C2, C3, etc.

Choose which labelled visual candidate corresponds to:

{target}

Available candidates:
{descriptions}

Return JSON ONLY:

{{
  "candidate_id": <integer>,
  "confidence": <0 to 1>,
  "visible_label": "<text you see on/in the target>"
}}

Do not return x/y coordinates.
Do not select a candidate unless its visible appearance
matches the requested target.
"""

    finding = None

    errors = []

    for budget in (
        512,
        1024,
        1536,
    ):
        try:
            finding = provider.analyze(
                annotated,
                prompt,
                num_predict=budget,
            )

            if str(
                finding.summary
            ).strip():
                break

        except RuntimeError as exc:
            errors.append(
                str(exc)
            )

            if (
                "VISION_EMPTY_RESPONSE"
                not in str(exc)
            ):
                raise

    if finding is None:
        raise RuntimeError(
            "CANDIDATE_VISION_FINAL_RESPONSE_MISSING="
            + ";".join(
                errors
            )
        )

    data = _json_object(
        finding.summary
    )

    candidate_id = int(
        data[
            "candidate_id"
        ]
    )

    confidence = float(
        data.get(
            "confidence",
            0,
        )
    )

    if confidence < 0.40:
        raise RuntimeError(
            "CANDIDATE_SELECTION_LOW_CONFIDENCE="
            + str(
                confidence
            )
        )

    selected = next(
        (
            item
            for item in candidates
            if (
                item.candidate_id
                == candidate_id
            )
        ),
        None,
    )

    if selected is None:
        raise RuntimeError(
            "INVALID_CANDIDATE_ID="
            + str(
                candidate_id
            )
        )

    return {
        "candidate": selected,
        "confidence": confidence,
        "visible_label": str(
            data.get(
                "visible_label",
                "",
            )
        ),
        "raw": finding.summary,
        "annotated_path": annotated,
        "image_width": width,
        "image_height": height,
        "candidate_count": len(
            candidates
        ),
    }
