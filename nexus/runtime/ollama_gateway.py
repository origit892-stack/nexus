from __future__ import annotations

import json
import urllib.error
import urllib.request

from dataclasses import dataclass
from typing import Any

from .reliability import RetryPolicy, retry_call
from .structured_output import (
    parse_json_resilient,
    pydantic_schema,
    pydantic_validate,
)


class OllamaGatewayError(RuntimeError):
    pass


@dataclass
class OllamaGateway:
    model: str
    base_url: str = "http://127.0.0.1:11434"
    timeout: float = 120.0
    retry_policy: RetryPolicy = RetryPolicy(
        attempts=3,
        base_delay=0.35,
        max_delay=2.0,
    )

    def _post(
        self,
        path: str,
        payload: dict,
    ) -> dict:
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
        ).encode("utf-8")

        def operation():
            request = urllib.request.Request(
                self.base_url.rstrip("/")
                + path,
                data=encoded,
                headers={
                    "Content-Type":
                    "application/json"
                },
            )

            try:
                with urllib.request.urlopen(
                    request,
                    timeout=self.timeout,
                ) as response:
                    return json.load(response)
            except urllib.error.HTTPError as exc:
                body = exc.read().decode(
                    "utf-8",
                    errors="replace",
                )

                raise OllamaGatewayError(
                    f"Ollama HTTP {exc.code}: "
                    f"{body[:1000]}"
                ) from exc
            except urllib.error.URLError as exc:
                raise OllamaGatewayError(
                    f"Ollama transport error: {exc}"
                ) from exc

        return retry_call(
            operation,
            policy=self.retry_policy,
            retry_if=lambda exc: isinstance(
                exc,
                (
                    OllamaGatewayError,
                    TimeoutError,
                ),
            ),
        )

    def chat(
        self,
        messages: list[dict],
        *,
        tools: list[dict] | None = None,
        format: Any | None = None,
        temperature: float = 0.1,
        keep_alive: str = "15m",
    ) -> dict:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "keep_alive": keep_alive,
            "options": {
                "temperature":
                temperature,
            },
        }

        if tools:
            payload["tools"] = tools

        if format is not None:
            payload["format"] = format

        return self._post(
            "/api/chat",
            payload,
        )

    def structured(
        self,
        messages: list[dict],
        model_cls: Any,
        *,
        temperature: float = 0.0,
    ):
        schema = pydantic_schema(
            model_cls
        )

        response = self.chat(
            messages,
            format=schema,
            temperature=temperature,
        )

        content = (
            response.get(
                "message",
                {},
            )
            .get(
                "content",
                "",
            )
        )

        value = parse_json_resilient(
            content
        )

        return pydantic_validate(
            model_cls,
            value,
        )
