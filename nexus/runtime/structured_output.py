from __future__ import annotations

import json
import re

from dataclasses import dataclass
from typing import Any, Callable, Mapping, TypeVar


T = TypeVar("T")


class StructuredOutputError(ValueError):
    pass


@dataclass(frozen=True)
class StructuredAttempt:
    raw: str
    parsed: Any | None
    error: str | None


_FENCE = re.compile(
    r"```(?:json)?\s*(.*?)```",
    re.I | re.S,
)


def _balanced_candidates(text: str):
    starts = []

    for index, char in enumerate(text):
        if char in "[{":
            starts.append(index)

    for start in starts:
        opening = text[start]
        closing = "}" if opening == "{" else "]"

        depth = 0
        in_string = False
        escaped = False

        for index in range(
            start,
            len(text),
        ):
            char = text[index]

            if in_string:
                if escaped:
                    escaped = False
                elif char == "\\":
                    escaped = True
                elif char == '"':
                    in_string = False
                continue

            if char == '"':
                in_string = True
                continue

            if char == opening:
                depth += 1
            elif char == closing:
                depth -= 1

                if depth == 0:
                    yield text[
                        start:index + 1
                    ]
                    break


def json_candidates(text: str):
    seen = set()

    stripped = text.strip()

    for candidate in (
        stripped,
        *(
            match.group(1).strip()
            for match in _FENCE.finditer(text)
        ),
        *_balanced_candidates(text),
    ):
        if not candidate:
            continue

        if candidate in seen:
            continue

        seen.add(candidate)
        yield candidate


def parse_json_resilient(
    text: str,
) -> Any:
    errors = []

    for candidate in json_candidates(text):
        try:
            return json.loads(candidate)
        except Exception as exc:
            errors.append(
                f"{type(exc).__name__}: {exc}"
            )

    raise StructuredOutputError(
        "No valid JSON payload found. "
        + " | ".join(errors[-4:])
    )


def validate_mapping(
    value: Any,
    *,
    required: tuple[str, ...] = (),
) -> Mapping[str, Any]:
    if not isinstance(value, dict):
        raise StructuredOutputError(
            "Expected JSON object"
        )

    missing = [
        key
        for key in required
        if key not in value
    ]

    if missing:
        raise StructuredOutputError(
            "Missing required fields: "
            + ", ".join(missing)
        )

    return value


def parse_with_validator(
    raw: str,
    validator: Callable[[Any], T],
) -> T:
    value = parse_json_resilient(raw)

    try:
        return validator(value)
    except StructuredOutputError:
        raise
    except Exception as exc:
        raise StructuredOutputError(
            f"schema validation failed: {exc}"
        ) from exc


def pydantic_schema(model_cls: Any) -> dict:
    if hasattr(
        model_cls,
        "model_json_schema",
    ):
        return model_cls.model_json_schema()

    if hasattr(
        model_cls,
        "schema",
    ):
        return model_cls.schema()

    raise TypeError(
        "Object does not expose a Pydantic JSON schema"
    )


def pydantic_validate(
    model_cls: Any,
    value: Any,
):
    if hasattr(
        model_cls,
        "model_validate",
    ):
        return model_cls.model_validate(value)

    if hasattr(
        model_cls,
        "parse_obj",
    ):
        return model_cls.parse_obj(value)

    raise TypeError(
        "Object does not expose Pydantic validation"
    )
