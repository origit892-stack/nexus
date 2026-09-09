from __future__ import annotations

import base64
import json
import time
import urllib.request
from dataclasses import dataclass, asdict
from pathlib import Path


@dataclass
class ScreenshotEvidence:
    path: str
    timestamp: float
    width: int | None = None
    height: int | None = None
    source: str = "computer"


@dataclass
class VisionFinding:
    summary: str
    confidence: float
    raw: str
    provider: str
    model: str
    screenshot: str


def _post_json(
    url: str,
    payload: dict,
    timeout: int = 600,
):
    body = json.dumps(
        payload
    ).encode(
        "utf-8"
    )

    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json"
        },
        method="POST",
    )

    with urllib.request.urlopen(
        req,
        timeout=timeout,
    ) as response:
        return json.loads(
            response.read().decode(
                "utf-8"
            )
        )


def image_to_base64(
    path: str,
) -> str:
    p = Path(
        path
    ).expanduser().resolve()

    if not p.exists():
        raise FileNotFoundError(
            str(p)
        )

    if p.stat().st_size <= 0:
        raise RuntimeError(
            "VISION_IMAGE_EMPTY"
        )

    return base64.b64encode(
        p.read_bytes()
    ).decode(
        "ascii"
    )


class OllamaVisionProvider:
    def __init__(
        self,
        model: str,
        base_url: str = (
            "http://127.0.0.1:11434"
        ),
    ):
        self.model = str(
            model
        )

        self.base_url = (
            base_url.rstrip("/")
        )

    def _chat(
        self,
        encoded: str,
        prompt: str,
        num_predict: int,
    ):
        return _post_json(
            self.base_url
            + "/api/chat",
            {
                "model": self.model,
                "messages": [
                    {
                        "role": "user",
                        "content": prompt,
                        "images": [
                            encoded
                        ],
                    }
                ],
                "stream": False,

                # Thinking-capable Qwen models can consume the
                # entire generation budget in hidden reasoning.
                # Vision grounding needs a concise final answer.
                "think": False,

                "keep_alive": "30m",
                "options": {
                    "temperature": 0,
                    "num_predict": int(
                        num_predict
                    ),
                },
            },
        )

    def _generate(
        self,
        encoded: str,
        prompt: str,
        num_predict: int,
    ):
        return _post_json(
            self.base_url
            + "/api/generate",
            {
                "model": self.model,
                "prompt": prompt,
                "images": [
                    encoded
                ],
                "stream": False,
                "think": False,
                "keep_alive": "30m",
                "options": {
                    "temperature": 0,
                    "num_predict": int(
                        num_predict
                    ),
                },
            },
        )

    def analyze(
        self,
        image_path: str,
        prompt: str,
        *,
        num_predict: int = 512,
    ) -> VisionFinding:
        encoded = image_to_base64(
            image_path
        )

        # ----------------------------------------------------
        # Primary: Ollama chat multimodal API.
        # ----------------------------------------------------

        chat = self._chat(
            encoded,
            prompt,
            max(
                int(
                    num_predict
                ),
                256,
            ),
        )

        message = chat.get(
            "message",
            {}
        )

        text = str(
            message.get(
                "content",
                ""
            )
        ).strip()

        if text:
            return VisionFinding(
                summary=text,
                confidence=1.0,
                raw=json.dumps(
                    chat,
                    ensure_ascii=False,
                ),
                provider="ollama-chat",
                model=self.model,
                screenshot=str(
                    Path(
                        image_path
                    ).resolve()
                ),
            )

        # ----------------------------------------------------
        # Do NOT treat hidden thinking as visual evidence.
        # A final answer is required.
        #
        # Fallback: Ollama generate multimodal API.
        # ----------------------------------------------------

        generated = self._generate(
            encoded,
            prompt,
            max(
                int(
                    num_predict
                ),
                256,
            ),
        )

        text = str(
            generated.get(
                "response",
                ""
            )
        ).strip()

        if text:
            return VisionFinding(
                summary=text,
                confidence=1.0,
                raw=json.dumps(
                    generated,
                    ensure_ascii=False,
                ),
                provider="ollama-generate",
                model=self.model,
                screenshot=str(
                    Path(
                        image_path
                    ).resolve()
                ),
            )

        chat_thinking = str(
            message.get(
                "thinking",
                ""
            )
        ).strip()

        generate_thinking = str(
            generated.get(
                "thinking",
                ""
            )
        ).strip()

        raise RuntimeError(
            "VISION_EMPTY_RESPONSE"
            + f" model={self.model}"
            + f" chat_done_reason={chat.get('done_reason', '')}"
            + f" chat_content_chars={len(str(message.get('content', '')))}"
            + f" chat_thinking_chars={len(chat_thinking)}"
            + f" generate_done_reason={generated.get('done_reason', '')}"
            + f" generate_response_chars={len(str(generated.get('response', '')))}"
            + f" generate_thinking_chars={len(generate_thinking)}"
        )


def finding_json(
    finding: VisionFinding,
):
    return json.dumps(
        asdict(
            finding
        ),
        ensure_ascii=False,
        indent=2,
    )
