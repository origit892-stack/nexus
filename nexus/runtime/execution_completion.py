from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import json

from nexus.runtime.understanding import (
    _generate_final_answer,
    _load_model_cached,
    extract_json_object,
    load_understanding_config,
)


class ExecutionCompletionError(
    RuntimeError
):
    pass


@dataclass(frozen=True)
class ExecutionCompletionDecision:
    allow: bool
    verdict: str
    summary: str
    unmet_conditions: tuple[str, ...]
    next_focus: tuple[str, ...]


def _clean_list(
    value: Any,
) -> list[str]:
    if value is None:
        return []

    if isinstance(
        value,
        str,
    ):
        value = [value]

    if not isinstance(
        value,
        (list, tuple),
    ):
        return []

    result: list[str] = []

    for item in value:
        text = str(
            item
        ).strip()

        if text:
            result.append(
                text
            )

    return result


def completion_contract(
    plan: dict[str, Any] | None,
) -> dict[str, Any]:
    if not isinstance(
        plan,
        dict,
    ):
        return {}

    return {
        "current_phase": str(
            plan.get(
                "current_phase",
                "",
            )
        ).strip(),
        "authorized_now": _clean_list(
            plan.get(
                "authorized_now"
            )
        ),
        "evidence_plan": _clean_list(
            plan.get(
                "evidence_plan"
            )
        ),
        "evaluation_plan": _clean_list(
            plan.get(
                "evaluation_plan"
            )
        ),
        "selection_strategy": _clean_list(
            plan.get(
                "selection_strategy"
            )
        ),
        "stop_conditions": _clean_list(
            plan.get(
                "stop_conditions"
            )
        ),
    }


def evidence_for_completion(
    evidence_ledger: Any,
    *,
    max_items: int = 24,
    max_output_chars: int = 1800,
) -> dict[str, Any]:
    if evidence_ledger is None:
        return {
            "summary": {},
            "recent_successful_evidence": [],
        }

    try:
        summary = evidence_ledger.summary()
    except Exception:
        summary = {}

    try:
        successful = list(
            evidence_ledger.successful()
        )
    except Exception:
        successful = []

    recent = successful[
        -max_items:
    ]

    items = []

    for item in recent:
        output = str(
            getattr(
                item,
                "output",
                "",
            )
        )

        if len(output) > max_output_chars:
            output = (
                output[
                    :max_output_chars
                ]
                + "...[truncated]"
            )

        args = getattr(
            item,
            "args",
            {},
        )

        if not isinstance(
            args,
            dict,
        ):
            args = {
                "value": str(args)
            }

        items.append(
            {
                "tool": str(
                    getattr(
                        item,
                        "tool",
                        "",
                    )
                ),
                "args": args,
                "output": output,
            }
        )

    return {
        "summary": summary,
        "recent_successful_evidence": items,
    }


def _validate_payload(
    payload: dict[str, Any],
) -> ExecutionCompletionDecision:
    verdict = str(
        payload.get(
            "verdict",
            "",
        )
    ).strip().upper()

    if verdict not in {
        "PASS",
        "CONTINUE",
    }:
        raise ExecutionCompletionError(
            "Invalid execution completion verdict: "
            + repr(verdict)
        )

    summary = str(
        payload.get(
            "summary",
            "",
        )
    ).strip()

    unmet = tuple(
        _clean_list(
            payload.get(
                "unmet_conditions"
            )
        )
    )

    next_focus = tuple(
        _clean_list(
            payload.get(
                "next_focus"
            )
        )
    )

    if verdict == "CONTINUE":
        if not unmet:
            raise ExecutionCompletionError(
                "CONTINUE verdict requires "
                "unmet_conditions."
            )

        if not next_focus:
            raise ExecutionCompletionError(
                "CONTINUE verdict requires "
                "next_focus."
            )

    return ExecutionCompletionDecision(
        allow=(
            verdict == "PASS"
        ),
        verdict=verdict,
        summary=summary,
        unmet_conditions=unmet,
        next_focus=next_focus,
    )


def evaluate_execution_completion(
    *,
    task: str,
    plan: dict[str, Any] | None,
    proposed_final: str,
    evidence_ledger: Any,
    progress=None,
) -> ExecutionCompletionDecision:
    contract = completion_contract(
        plan
    )

    # No Planner contract means there is nothing for this
    # gate to enforce. Preserve legacy behavior.
    if not contract:
        return ExecutionCompletionDecision(
            allow=True,
            verdict="PASS",
            summary=(
                "No execution plan contract is active."
            ),
            unmet_conditions=(),
            next_focus=(),
        )

    cfg = load_understanding_config()

    # NEXUS700_NORMALIZE_MODEL_LOADER_RESULT
    _loaded_model = (
        _load_model_cached(
                    str(
                        cfg[
                            "local_path"
                        ]
                    )
                )
    )

    if not isinstance(
        _loaded_model,
        (tuple, list),
    ):
        raise ExecutionCompletionError(
            "Model loader returned an invalid result type: "
            + type(_loaded_model).__name__
        )

    if len(_loaded_model) == 2:
        model, tokenizer = _loaded_model
        _model_metadata = None

    elif len(_loaded_model) >= 3:
        model = _loaded_model[0]
        tokenizer = _loaded_model[1]
        _model_metadata = _loaded_model[2]

    else:
        raise ExecutionCompletionError(
            "Model loader returned too few values: "
            + str(len(_loaded_model))
        )

    evidence = evidence_for_completion(
        evidence_ledger
    )

    system = (
        "You are the Nexus Execution Completion Critic.\n"
        "Judge whether the executor may finish the CURRENT "
        "approved phase.\n\n"
        "You are not planning new work and you are not "
        "rewriting the user's request.\n"
        "Use only the supplied task, approved plan, proposed "
        "final answer, and execution evidence.\n\n"
        "Return PASS only when the proposed final answer and "
        "evidence support completion of the current plan's "
        "required evidence, evaluation, selection, and stop "
        "conditions.\n"
        "A large number of tool calls is not evidence of "
        "completion by itself.\n"
        "Directory traversal alone does not prove evaluation "
        "or selection when those are required.\n"
        "Do not require deferred or forbidden work.\n"
        "Do not invent project facts.\n"
        "If important current-phase requirements remain "
        "unsupported, return CONTINUE and identify the "
        "smallest focused next work needed.\n\n"
        "Return JSON only with exactly these fields:\n"
        "{\n"
        '  "verdict": "PASS" | "CONTINUE",\n'
        '  "summary": "short explanation",\n'
        '  "unmet_conditions": ["..."],\n'
        '  "next_focus": ["..."]\n'
        "}\n"
    )

    user = (
        "USER TASK:\n"
        + task
        + "\n\nAPPROVED CURRENT-PHASE CONTRACT:\n"
        + json.dumps(
            contract,
            ensure_ascii=False,
            indent=2,
        )
        + "\n\nPROPOSED FINAL ANSWER:\n"
        + proposed_final
        + "\n\nEXECUTION EVIDENCE:\n"
        + json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
            default=str,
        )
    )

    if progress is not None:
        progress(
            "EXECUTION COMPLETION: CHECKING PLAN"
        )

    raw, _metrics = _generate_final_answer(
        model=model,
        tokenizer=tokenizer,
        messages=[
            {
                "role": "system",
                "content": system,
            },
            {
                "role": "user",
                "content": user,
            },
        ],
        max_tokens=int(
            cfg.get(
                "finalizer_max_tokens",
                768,
            )
        ),
    )

    try:
        payload = extract_json_object(
            raw
        )
    except Exception as exc:
        raise ExecutionCompletionError(
            "Execution completion critic did not "
            "return valid JSON: "
            + str(exc)
        ) from exc

    if not isinstance(
        payload,
        dict,
    ):
        raise ExecutionCompletionError(
            "Execution completion critic returned "
            "a non-object payload."
        )

    decision = _validate_payload(
        payload
    )

    if progress is not None:
        progress(
            "EXECUTION COMPLETION: "
            + decision.verdict
        )

    return decision


def render_continue_instruction(
    decision: ExecutionCompletionDecision,
) -> str:
    unmet = "\n".join(
        "- " + item
        for item in decision.unmet_conditions
    )

    focus = "\n".join(
        "- " + item
        for item in decision.next_focus
    )

    return (
        "NEXUS EXECUTION COMPLETION GATE: CONTINUE\n"
        "The approved current-phase plan is not yet "
        "supported as complete.\n\n"
        "UNMET CONDITIONS:\n"
        + unmet
        + "\n\nNEXT FOCUS:\n"
        + focus
        + "\n\nContinue with focused work that closes these "
        "specific gaps. Reuse existing evidence. Do not "
        "restart broad discovery, do not repeat completed "
        "work, do not broaden the task, and do not perform "
        "deferred or forbidden actions."
    )

# NEXUS_700_COMPLETION_OBSERVABILITY
# Completion decisions are observed by nexus.runtime.completion_observability. This marker intentionally changes no completion semantics.
