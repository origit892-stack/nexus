from nexus.runtime.model_capabilities import (
    ModelCapability,
    select_model,
)


def test_select_structured_reasoning_model():
    models = [
        ModelCapability(
            provider="mlx-local",
            model="small",
            local=True,
            available=True,
            reasoning=True,
        ),
        ModelCapability(
            provider="ollama",
            model="reasoner",
            local=True,
            available=True,
            structured_output=True,
            tool_calling=True,
            reasoning=True,
        ),
    ]

    selected = select_model(
        models,
        require_structured=True,
        prefer_reasoning=True,
    )

    assert selected is not None
    assert selected.model == "reasoner"


def test_no_hardcoded_model_required():
    models = [
        ModelCapability(
            provider="mlx-local",
            model="whatever-is-installed",
            local=True,
            available=True,
            reasoning=True,
        )
    ]

    selected = select_model(
        models,
        prefer_reasoning=True,
    )

    assert selected.model == (
        "whatever-is-installed"
    )
