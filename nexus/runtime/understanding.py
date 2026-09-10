from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Callable

import json
import time


class UnderstandingError(
    RuntimeError
):
    pass


FORM_FIELDS = (
    "user_goal",
    "desired_end_state",
    "current_requested_phase",
    "explicit_requests",
    "explicit_restrictions",
    "implicit_requirements",
    "relevant_game_context",
    "known_project_facts",
    "unknowns_requiring_discovery",
    "mutation_policy",
    "evidence_needed",
    "recommended_plan",
    "completion_definition",
    "response_expected",
    "confidence",
)


FORM_LABELS = (
    (
        "Q1",
        "What is the user's actual goal?",
    ),
    (
        "Q2",
        "What end state does the user want?",
    ),
    (
        "Q3",
        "What phase is requested right now?",
    ),
    (
        "Q4",
        "What was explicitly requested?",
    ),
    (
        "Q5",
        "What was explicitly restricted?",
    ),
    (
        "Q6",
        "What requirements are implicit?",
    ),
    (
        "Q7",
        "What game context matters?",
    ),
    (
        "Q8",
        "What project facts are known?",
    ),
    (
        "Q9",
        "What still requires discovery?",
    ),
    (
        "Q10",
        "What mutation policy applies?",
    ),
    (
        "Q11",
        "What evidence is needed?",
    ),
    (
        "Q12",
        "What is the recommended plan?",
    ),
    (
        "Q13",
        "When is the task complete?",
    ),
    (
        "Q14",
        "What response does the user expect?",
    ),
    (
        "Q15",
        "How confident is this interpretation?",
    ),
)


LIST_FIELDS = (
    "explicit_requests",
    "explicit_restrictions",
    "implicit_requirements",
    "relevant_game_context",
    "known_project_facts",
    "unknowns_requiring_discovery",
    "evidence_needed",
    "recommended_plan",
    "completion_definition",
)


STRING_FIELDS = (
    "user_goal",
    "desired_end_state",
    "current_requested_phase",
    "mutation_policy",
    "response_expected",
)


def _nexus_root() -> Path:
    return (
        Path(__file__)
        .resolve()
        .parents[1]
    )


def load_understanding_config(
) -> dict[str, Any]:
    path = (
        _nexus_root()
        / "config"
        / "understanding_model.json"
    )

    if not path.exists():
        raise UnderstandingError(
            f"Missing understanding config: {path}"
        )

    try:
        cfg = json.loads(
            path.read_text()
        )
    except Exception as exc:
        raise UnderstandingError(
            "Invalid understanding config: "
            + str(exc)
        ) from exc

    required = (
        "enabled",
        "required",
        "backend",
        "local_path",
        "initial_max_tokens",
        "repair_max_tokens",
        "critic_max_tokens",
        "max_repairs",
    )

    missing = [
        key
        for key in required
        if key not in cfg
    ]

    if missing:
        raise UnderstandingError(
            "Understanding config missing keys: "
            + ", ".join(missing)
        )

    return cfg


def load_project_context(
    project_path: str | Path | None = None,
) -> str:
    project = (
        Path(project_path)
        .expanduser()
        .resolve()
        if project_path is not None
        else Path.cwd().resolve()
    )

    if (
        project.name.casefold()
        == "bunkergame"
    ):
        path = (
            _nexus_root()
            / "config"
            / "bunkergame_context.md"
        )

        if not path.exists():
            raise UnderstandingError(
                f"Missing BunkerGame context: {path}"
            )

        return path.read_text()

    return (
        "# Generic Project Context\n\n"
        "No canonical project-specific context pack "
        "is registered. Treat unstated project facts "
        "as UNKNOWN and requiring discovery."
    )


@lru_cache(maxsize=1)
def _load_model_cached(
    model_path: str,
):
    from mlx_lm import load

    path = (
        Path(model_path)
        .expanduser()
        .resolve()
    )

    if not path.exists():
        raise UnderstandingError(
            f"Required local model missing: {path}"
        )

    started = time.perf_counter()

    model, tokenizer = load(
        str(path)
    )

    elapsed = (
        time.perf_counter()
        - started
    )

    return (
        model,
        tokenizer,
        elapsed,
    )



def understanding_enabled() -> bool:
    """
    Deep understanding is ON by default in real Nexus.

    Tests may explicitly set:
      NEXUS_UNDERSTANDING_MODE=OFF

    This avoids loading a real local LLM in unrelated
    deterministic unit tests.
    """
    import os

    return (
        os.environ.get(
            "NEXUS_UNDERSTANDING_MODE",
            "ON",
        )
        .strip()
        .upper()
        != "OFF"
    )


def model_is_warm() -> bool:
    return (
        _load_model_cached
        .cache_info()
        .currsize
        > 0
    )


def _schema_description(
) -> dict[str, Any]:
    return {
        "user_goal": "string",
        "desired_end_state": "string",
        "current_requested_phase": "string",
        "explicit_requests": [
            "string"
        ],
        "explicit_restrictions": [
            "string"
        ],
        "implicit_requirements": [
            "string"
        ],
        "relevant_game_context": [
            "string"
        ],
        "known_project_facts": [
            "string"
        ],
        "unknowns_requiring_discovery": [
            "string"
        ],
        "mutation_policy": (
            "READ_ONLY | MUTATING | UNSURE"
        ),
        "evidence_needed": [
            "string"
        ],
        "recommended_plan": [
            "string"
        ],
        "completion_definition": [
            "string"
        ],
        "response_expected": "string",
        "confidence": (
            "number from 0.0 to 1.0"
        ),
    }


def _system_prompt(
    context_pack: str,
) -> str:
    return (
        "You are the Nexus Understanding Model.\n\n"
        "Your job is NOT to execute the user's task.\n"
        "Your job is to understand it deeply before a "
        "separate execution agent begins.\n\n"
        "You have NO tools and cannot inspect files.\n\n"
        "Use the user's natural language as written. "
        "Do not depend on keyword matching.\n\n"
        "Reason carefully and for as long as genuinely "
        "needed, but avoid repetitive or decorative "
        "reasoning.\n\n"
        "Priorities:\n"
        "1. faithful understanding of user intent\n"
        "2. correct use of project context\n"
        "3. distinction between known and unknown facts\n"
        "4. correct scope and current phase\n"
        "5. correct mutation interpretation\n"
        "6. useful execution planning\n"
        "7. speed only after correctness\n\n"
        "Never invent project content that is absent "
        "from the user's request and project context.\n\n"
        "A future desired action is NOT automatically "
        "authorized in the current phase.\n\n"
        "If mutation permission cannot be determined "
        "reliably, use UNSURE.\n\n"
        "Do not treat examples, filenames, systems, "
        "assets, or game mechanics as existing unless "
        "they are actually stated in the request or "
        "project context.\n\n"
        "After reasoning, output one JSON object using "
        "the schema below. Markdown fences are tolerated. "
        "Do not put prose after the JSON.\n\n"
        "UNDERSTANDING FORM SCHEMA:\n"
        + json.dumps(
            _schema_description(),
            ensure_ascii=False,
            indent=2,
        )
        + "\n\n"
        "CANONICAL PROJECT CONTEXT:\n"
        + context_pack
    )



def _build_final_answer_prompt(
    *,
    tokenizer: Any,
    messages: list[dict[str, str]],
) -> str:
    """
    Build a DeepSeek-R1 prompt that begins generation in
    final-answer mode rather than opening another reasoning loop.

    Normal Understanding/Planner calls continue using the
    ordinary chat template and retain full reasoning.

    This helper is used only by schema finalizers.
    """
    prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True,
    )

    stripped = prompt.rstrip()

    # DeepSeek-R1 chat templates may finish the assistant
    # generation prefix inside an open <think> section.
    #
    # Closing that section before sampling tells the model that
    # reasoning is already complete and that it should emit the
    # requested final representation.
    if stripped.endswith(
        "<think>"
    ):
        return (
            stripped
            + "\n</think>\n"
        )

    if stripped.endswith(
        "<think>\n"
    ):
        return (
            stripped
            + "</think>\n"
        )

    # Some tokenizer revisions encode the reasoning prefix using
    # special tokens rather than a literal final <think> suffix.
    # Appending a closing marker is harmless for the dedicated
    # formatter instruction and prevents a fresh visible reasoning
    # section from consuming the formatter budget.
    if not stripped.endswith(
        "</think>"
    ):
        return (
            stripped
            + "\n</think>\n"
        )

    return (
        stripped
        + "\n"
    )


def _generate_final_answer(
    *,
    model: Any,
    tokenizer: Any,
    messages: list[dict[str, str]],
    max_tokens: int,
) -> tuple[str, dict[str, Any]]:
    """
    Generate a compact final representation without starting
    another R1 reasoning pass.
    """
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import (
        make_sampler,
    )

    prompt = _build_final_answer_prompt(
        tokenizer=tokenizer,
        messages=messages,
    )

    sampler = make_sampler(
        temp=0.0,
        top_p=0.0,
    )

    pieces: list[str] = []
    first_token = None
    last = None

    started = time.perf_counter()

    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=int(
            max_tokens
        ),
        sampler=sampler,
    ):
        if first_token is None:
            first_token = (
                time.perf_counter()
                - started
            )

        pieces.append(
            response.text
        )

        last = response

    total = (
        time.perf_counter()
        - started
    )

    metrics: dict[str, Any] = {
        "ttft_seconds": (
            first_token
            if first_token is not None
            else total
        ),
        "total_seconds": total,
    }

    if last is not None:
        mappings = (
            (
                "prompt_tokens",
                "prompt_tokens",
            ),
            (
                "prompt_tps",
                "prompt_tps",
            ),
            (
                "generation_tokens",
                "generation_tokens",
            ),
            (
                "generation_tps",
                "generation_tps",
            ),
            (
                "peak_memory",
                "peak_memory_gb",
            ),
        )

        for source, target in mappings:
            if hasattr(
                last,
                source,
            ):
                metrics[
                    target
                ] = getattr(
                    last,
                    source,
                )

    return (
        "".join(
            pieces
        ).strip(),
        metrics,
    )


def _generate(
    *,
    model: Any,
    tokenizer: Any,
    messages: list[dict[str, str]],
    max_tokens: int,
    temperature: float,
    top_p: float,
) -> tuple[str, dict[str, Any]]:
    from mlx_lm import stream_generate
    from mlx_lm.sample_utils import (
        make_sampler,
    )

    prompt = (
        tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
    )

    sampler = make_sampler(
        temp=float(temperature),
        top_p=float(top_p),
    )

    pieces: list[str] = []
    first_token = None
    last = None

    started = time.perf_counter()

    for response in stream_generate(
        model,
        tokenizer,
        prompt=prompt,
        max_tokens=int(max_tokens),
        sampler=sampler,
    ):
        if first_token is None:
            first_token = (
                time.perf_counter()
                - started
            )

        pieces.append(
            response.text
        )

        last = response

    total = (
        time.perf_counter()
        - started
    )

    metrics: dict[str, Any] = {
        "ttft_seconds": (
            first_token
            if first_token is not None
            else total
        ),
        "total_seconds": total,
    }

    if last is not None:
        mappings = (
            (
                "prompt_tokens",
                "prompt_tokens",
            ),
            (
                "prompt_tps",
                "prompt_tps",
            ),
            (
                "generation_tokens",
                "generation_tokens",
            ),
            (
                "generation_tps",
                "generation_tps",
            ),
            (
                "peak_memory",
                "peak_memory_gb",
            ),
        )

        for source, target in mappings:
            if hasattr(
                last,
                source,
            ):
                metrics[target] = getattr(
                    last,
                    source,
                )

    return (
        "".join(pieces).strip(),
        metrics,
    )


def _remove_reasoning_prefix(
    raw: str,
) -> str:
    text = raw.strip()

    if "</think>" in text:
        text = text.split(
            "</think>",
            1,
        )[1].strip()

    return text


def _remove_code_fence(
    text: str,
) -> str:
    value = text.strip()

    if not value.startswith("```"):
        return value

    first_newline = value.find("\n")

    if first_newline >= 0:
        value = value[
            first_newline + 1:
        ]

    closing = value.rfind("```")

    if closing >= 0:
        value = value[:closing]

    return value.strip()


def extract_json_object(
    raw: str,
) -> dict[str, Any]:
    """
    Extract a JSON object robustly.

    First prefer content after </think>, when present.
    If that contains no valid object, scan the complete raw
    model output as a fallback.

    This changes representation handling only; it does not
    infer or invent semantic content.
    """
    decoder = json.JSONDecoder()

    candidates: list[str] = []

    post_reasoning = _remove_code_fence(
        _remove_reasoning_prefix(
            raw
        )
    ).strip()

    if post_reasoning:
        candidates.append(
            post_reasoning
        )

    complete = _remove_code_fence(
        raw
    ).strip()

    if (
        complete
        and complete not in candidates
    ):
        candidates.append(
            complete
        )

    for candidate in candidates:
        for index, character in enumerate(
            candidate
        ):
            if character != "{":
                continue

            try:
                payload, _ = decoder.raw_decode(
                    candidate[index:]
                )
            except json.JSONDecodeError:
                continue

            if isinstance(
                payload,
                dict,
            ):
                return payload

    raise UnderstandingError(
        "No valid JSON object found in "
        "Understanding Model output."
    )


def normalize_understanding_structure(
    payload: dict[str, Any],
) -> dict[str, Any]:
    """
    Normalize representation only.

    This function does not infer user intent and does not
    invent missing semantic content.

    A model may express a one-item list field as a string.
    Convert that representation to a one-item list so that
    structurally equivalent answers validate consistently.
    """
    result = dict(
        payload
    )

    for field in LIST_FIELDS:
        if field not in result:
            continue

        value = result[
            field
        ]

        if isinstance(
            value,
            str,
        ):
            result[
                field
            ] = [
                value
            ]

    return result


def validate_understanding(
    payload: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    for field in FORM_FIELDS:
        if field not in payload:
            errors.append(
                f"missing field: {field}"
            )

    for field in STRING_FIELDS:
        if (
            field in payload
            and not isinstance(
                payload[field],
                str,
            )
        ):
            errors.append(
                f"{field} must be string"
            )

    for field in LIST_FIELDS:
        if (
            field in payload
            and not isinstance(
                payload[field],
                list,
            )
        ):
            errors.append(
                f"{field} must be list"
            )

    if (
        "mutation_policy"
        in payload
        and payload[
            "mutation_policy"
        ]
        not in {
            "READ_ONLY",
            "MUTATING",
            "UNSURE",
        }
    ):
        errors.append(
            "mutation_policy must be READ_ONLY, "
            "MUTATING, or UNSURE"
        )

    if "confidence" in payload:
        confidence = payload[
            "confidence"
        ]

        if not isinstance(
            confidence,
            (int, float),
        ):
            errors.append(
                "confidence must be numeric"
            )
        elif not (
            0.0
            <= float(confidence)
            <= 1.0
        ):
            errors.append(
                "confidence must be between 0 and 1"
            )

    return errors


def _repair_messages(
    *,
    system: str,
    request: str,
    raw: str,
    errors: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                system
                + "\n\n"
                "SCHEMA REPAIR MODE.\n"
                "Do not redo the task.\n"
                "Do not add new project facts.\n"
                "Correct only the understanding form.\n"
                "Return JSON only."
            ),
        },
        {
            "role": "user",
            "content": (
                "ORIGINAL REQUEST:\n"
                + request
                + "\n\n"
                "PREVIOUS OUTPUT:\n"
                + raw
                + "\n\n"
                "VALIDATION ERRORS:\n"
                + "\n".join(
                    "- " + error
                    for error in errors
                )
            ),
        },
    ]


def _clean_payload(
    payload: dict[str, Any],
) -> dict[str, Any]:
    return {
        key: value
        for key, value in payload.items()
        if not key.startswith("_")
    }



def validate_critic_result(
    result: dict[str, Any],
) -> list[str]:
    errors: list[str] = []

    required = (
        "verdict",
        "issues",
        "unsupported_claims",
        "contradictions",
        "summary",
    )

    for field in required:
        if field not in result:
            errors.append(
                f"missing critic field: {field}"
            )

    if (
        "verdict"
        in result
        and result[
            "verdict"
        ]
        not in {
            "PASS",
            "FAIL",
        }
    ):
        errors.append(
            "critic verdict must be PASS or FAIL"
        )

    for field in (
        "issues",
        "unsupported_claims",
        "contradictions",
    ):
        if field not in result:
            continue

        value = result[
            field
        ]

        if isinstance(
            value,
            str,
        ):
            result[
                field
            ] = [
                value
            ]

        elif not isinstance(
            value,
            list,
        ):
            errors.append(
                f"{field} must be list"
            )

    if (
        "summary"
        in result
        and not isinstance(
            result[
                "summary"
            ],
            str,
        )
    ):
        errors.append(
            "critic summary must be string"
        )

    return errors


def _critic_repair_messages(
    *,
    user_request: str,
    proposed_understanding: dict[str, Any],
    invalid_output: str,
    errors: list[str],
) -> list[dict[str, str]]:
    return [
        {
            "role": "system",
            "content": (
                "You are repairing the STRUCTURE of a "
                "Nexus Understanding critic result.\n"
                "Do not redo long reasoning.\n"
                "Do not invent a predetermined answer.\n"
                "Return JSON only with exactly these fields:\n"
                "{\n"
                '  "verdict": "PASS | FAIL",\n'
                '  "issues": ["string"],\n'
                '  "unsupported_claims": ["string"],\n'
                '  "contradictions": ["string"],\n'
                '  "summary": "string"\n'
                "}"
            ),
        },
        {
            "role": "user",
            "content": (
                "USER REQUEST:\n"
                + user_request
                + "\n\n"
                "PROPOSED UNDERSTANDING:\n"
                + json.dumps(
                    proposed_understanding,
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n\n"
                "INVALID CRITIC OUTPUT:\n"
                + invalid_output
                + "\n\n"
                "STRUCTURAL ERRORS:\n"
                + "\n".join(
                    "- " + error
                    for error in errors
                )
            ),
        },
    ]


def critique_understanding(
    *,
    user_request: str,
    payload: dict[str, Any],
    project_path: str | Path | None = None,
) -> dict[str, Any]:
    cfg = load_understanding_config()

    context = load_project_context(
        project_path
    )

    model, tokenizer, _ = (
        _load_model_cached(
            str(
                cfg["local_path"]
            )
        )
    )

    critic_system = (
        "You are an independent Nexus Understanding "
        "critic.\n\n"
        "You are NOT told what the correct answer is.\n"
        "Judge only whether the proposed understanding "
        "faithfully follows the user's request and the "
        "provided canonical project context.\n\n"
        "Check for:\n"
        "- invented project facts\n"
        "- misunderstood user intent\n"
        "- current phase confused with future plans\n"
        "- restrictions that were ignored\n"
        "- permissions that were invented\n"
        "- important requested outcomes omitted\n"
        "- contradictions between fields\n"
        "- execution plans that go beyond the request\n\n"
        "Do NOT reward specific wording.\n"
        "Do NOT require a predetermined route or label.\n\n"
        "Return JSON only:\n"
        "{\n"
        '  "verdict": "PASS | FAIL",\n'
        '  "issues": ["string"],\n'
        '  "unsupported_claims": ["string"],\n'
        '  "contradictions": ["string"],\n'
        '  "summary": "string"\n'
        "}\n\n"
        "CANONICAL PROJECT CONTEXT:\n"
        + context
    )

    critic_user = (
        "USER REQUEST:\n"
        + user_request
        + "\n\n"
        "PROPOSED UNDERSTANDING:\n"
        + json.dumps(
            _clean_payload(
                payload
            ),
            ensure_ascii=False,
            indent=2,
        )
    )

    raw, metrics = _generate(
        model=model,
        tokenizer=tokenizer,
        messages=[
            {
                "role": "system",
                "content": critic_system,
            },
            {
                "role": "user",
                "content": critic_user,
            },
        ],
        max_tokens=int(
            cfg["critic_max_tokens"]
        ),
        temperature=0.0,
        top_p=0.0,
    )

    result = None
    errors: list[str] = []

    try:
        result = extract_json_object(
            raw
        )

        errors = validate_critic_result(
            result
        )

    except UnderstandingError as exc:
        errors = [
            str(exc)
        ]

    repairs = 0

    while errors:
        if repairs >= int(
            cfg.get(
                "critic_max_repairs",
                1,
            )
        ):
            raise UnderstandingError(
                "Critic validation failed: "
                + "; ".join(
                    errors
                )
            )

        repairs += 1

        repair_raw, repair_metrics = _generate(
            model=model,
            tokenizer=tokenizer,
            messages=_critic_repair_messages(
                user_request=user_request,
                proposed_understanding=(
                    _clean_payload(
                        payload
                    )
                ),
                invalid_output=raw,
                errors=errors,
            ),
            max_tokens=int(
                cfg.get(
                    "critic_repair_max_tokens",
                    512,
                )
            ),
            temperature=0.0,
            top_p=0.0,
        )

        metrics[
            f"critic_repair_{repairs}"
        ] = repair_metrics

        raw = repair_raw

        try:
            result = extract_json_object(
                raw
            )

            errors = validate_critic_result(
                result
            )

        except UnderstandingError as exc:
            errors = [
                str(exc)
            ]

    if result is None:
        raise UnderstandingError(
            "Critic result unavailable."
        )

    result["_metrics"] = metrics
    result["_repairs_used"] = repairs

    return result



def _finalizer_system_prompt() -> str:
    return (
        "You are the Nexus Understanding Form Finalizer.\n\n"
        "A reasoning model already analyzed the user's request.\n"
        "Your job is ONLY to produce the final structured form.\n\n"
        "Do not execute the user's task.\n"
        "Do not add project facts.\n"
        "Do not add restrictions that belong only to the "
        "Understanding Model itself.\n"
        "Do not explain your reasoning.\n"
        "Do not output markdown fences.\n"
        "Do not output prose before or after the JSON.\n\n"
        "Preserve the semantic meaning of the original request "
        "and the supplied reasoning/output.\n"
        "If a fact remains uncertain, represent it as uncertain "
        "rather than inventing certainty.\n\n"
        "Return exactly one JSON object matching this schema:\n"
        + json.dumps(
            _schema_description(),
            ensure_ascii=False,
            indent=2,
        )
    )


def _finalize_understanding_payload(
    *,
    model: Any,
    tokenizer: Any,
    user_request: str,
    previous_output: str,
    cfg: dict[str, Any],
    progress: Callable[[str], None] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    attempts = int(
        cfg.get(
            "finalizer_attempts",
            2,
        )
    )

    max_tokens = int(
        cfg.get(
            "finalizer_max_tokens",
            1024,
        )
    )

    last_error = (
        "No finalization attempt completed."
    )

    all_metrics: dict[str, Any] = {}

    for attempt in range(
        1,
        attempts + 1,
    ):
        if progress is not None:
            progress(
                "UNDERSTANDING: "
                f"FINALIZING FORM {attempt}/{attempts}"
            )

        raw, metrics = _generate_final_answer(
            model=model,
            tokenizer=tokenizer,
            messages=[
                {
                    "role": "system",
                    "content": (
                        _finalizer_system_prompt()
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "ORIGINAL USER REQUEST:\n"
                        + user_request
                        + "\n\n"
                        "PREVIOUS UNDERSTANDING OUTPUT:\n"
                        + previous_output
                        + "\n\n"
                        "Produce the structured understanding "
                        "form now."
                    ),
                },
            ],
            max_tokens=max_tokens,
        )

        all_metrics[
            f"attempt_{attempt}"
        ] = metrics

        try:
            payload = extract_json_object(
                raw
            )

            payload = (
                normalize_understanding_structure(
                    payload
                )
            )

            errors = validate_understanding(
                payload
            )

            if not errors:
                return (
                    payload,
                    all_metrics,
                )

            last_error = (
                "; ".join(errors)
            )

            previous_output = (
                previous_output
                + "\n\nFINALIZER INVALID OUTPUT:\n"
                + raw
                + "\n\nVALIDATION ERRORS:\n"
                + last_error
            )

        except UnderstandingError as exc:
            last_error = str(
                exc
            )

            previous_output = (
                previous_output
                + "\n\nFINALIZER INVALID OUTPUT:\n"
                + raw
                + "\n\nERROR:\n"
                + last_error
            )

    raise UnderstandingError(
        "Understanding finalizer failed: "
        + last_error
    )


def understand_task(
    instruction: str,
    *,
    project_path: str | Path | None = None,
    progress: (
        Callable[[str], None]
        | None
    ) = None,
    run_critic: bool = True,
) -> dict[str, Any]:
    cfg = load_understanding_config()

    if not cfg.get(
        "enabled",
        True,
    ):
        raise UnderstandingError(
            "Understanding Model is disabled."
        )

    context = load_project_context(
        project_path
    )

    system = _system_prompt(
        context
    )

    if progress is not None:
        progress(
            "UNDERSTANDING MODEL: "
            + (
                "WARM"
                if model_is_warm()
                else "LOADING"
            )
        )

    model, tokenizer, load_seconds = (
        _load_model_cached(
            str(
                cfg["local_path"]
            )
        )
    )

    if progress is not None:
        progress(
            "UNDERSTANDING: REASONING"
        )

    raw, metrics = _generate(
        model=model,
        tokenizer=tokenizer,
        messages=[
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": instruction,
            },
        ],
        max_tokens=int(
            cfg[
                "initial_max_tokens"
            ]
        ),
        temperature=float(
            cfg.get(
                "temperature",
                0.0,
            )
        ),
        top_p=float(
            cfg.get(
                "top_p",
                0.95,
            )
        ),
    )

    payload: dict[str, Any] | None = None

    try:
        payload = extract_json_object(
            raw
        )

        payload = normalize_understanding_structure(
            payload
        )

        errors = validate_understanding(
            payload
        )
    except UnderstandingError as exc:
        errors = [
            str(exc)
        ]

    repairs = 0

    while errors:
        if repairs >= int(
            cfg.get(
                "max_repairs",
                2,
            )
        ):
            if progress is not None:
                progress(
                    "UNDERSTANDING: "
                    "NORMAL REPAIRS EXHAUSTED"
                )

            payload, finalizer_metrics = (
                _finalize_understanding_payload(
                    model=model,
                    tokenizer=tokenizer,
                    user_request=instruction,
                    previous_output=raw,
                    cfg=cfg,
                    progress=progress,
                )
            )

            metrics[
                "finalizer"
            ] = finalizer_metrics

            errors = []

            break

        repairs += 1

        if progress is not None:
            progress(
                "UNDERSTANDING: "
                f"SCHEMA REPAIR {repairs}"
            )

        repaired_raw, repair_metrics = (
            _generate(
                model=model,
                tokenizer=tokenizer,
                messages=_repair_messages(
                    system=system,
                    request=instruction,
                    raw=raw,
                    errors=errors,
                ),
                max_tokens=int(
                    cfg[
                        "repair_max_tokens"
                    ]
                ),
                temperature=0.0,
                top_p=0.0,
            )
        )

        metrics[
            f"repair_{repairs}"
        ] = repair_metrics

        raw = repaired_raw

        try:
            payload = extract_json_object(
                raw
            )

            payload = normalize_understanding_structure(
                payload
            )

            errors = (
                validate_understanding(
                    payload
                )
            )
        except UnderstandingError as exc:
            errors = [
                str(exc)
            ]

    if payload is None:
        raise UnderstandingError(
            "Understanding payload unavailable."
        )

    payload[
        "_nexus_understanding_meta"
    ] = {
        "model": cfg.get(
            "model_id"
        ),
        "backend": cfg.get(
            "backend"
        ),
        "model_load_seconds": load_seconds,
        "repairs_used": repairs,
        "metrics": metrics,
    }

    if progress is not None:
        for index, (
            question,
            label,
        ) in enumerate(
            FORM_LABELS,
            start=1,
        ):
            field = FORM_FIELDS[
                index - 1
            ]

            value = payload.get(
                field
            )

            short_value = (
                json.dumps(
                    value,
                    ensure_ascii=False,
                )
                if not isinstance(
                    value,
                    str,
                )
                else value
            )

            if len(
                short_value
            ) > 110:
                short_value = (
                    short_value[:107]
                    + "..."
                )

            progress(
                "FILLING FORM "
                f"{question} "
                f"({index}/{len(FORM_LABELS)}): "
                f"{label} -> {short_value}"
            )

    if run_critic:
        if progress is not None:
            progress(
                "UNDERSTANDING: "
                "INDEPENDENT CRITIC"
            )

        critic = critique_understanding(
            user_request=instruction,
            payload=payload,
            project_path=project_path,
        )

        payload[
            "_nexus_understanding_critic"
        ] = critic

        if critic[
            "verdict"
        ] != "PASS":
            raise UnderstandingError(
                "Understanding critic rejected "
                "the interpretation: "
                + json.dumps(
                    critic,
                    ensure_ascii=False,
                )
            )

    if progress is not None:
        progress(
            "UNDERSTANDING COMPLETE"
        )

    return payload


def render_executor_brief(
    payload: dict[str, Any],
) -> str:
    clean = _clean_payload(
        payload
    )

    return (
        "\n\n"
        "NEXUS UNDERSTANDING BRIEF\n"
        "This brief was generated before tool execution "
        "by the dedicated Understanding Model and "
        "validated for structural consistency.\n"
        "Use it as the planning interpretation of the "
        "user's request. User instructions remain "
        "authoritative.\n"
        + json.dumps(
            clean,
            ensure_ascii=False,
            indent=2,
        )
        + "\nEND NEXUS UNDERSTANDING BRIEF\n"
    )
