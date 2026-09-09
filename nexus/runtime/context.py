from __future__ import annotations


class ContextEngine:
    def __init__(
        self,
        max_chars=90000,
        tool_result_chars=18000,
    ):
        self.max_chars = max_chars
        self.tool_result_chars = tool_result_chars

    def trim_tool_result(self, text):
        text = str(text)

        if len(text) <= self.tool_result_chars:
            return text

        half = self.tool_result_chars // 2

        return (
            text[:half]
            + "\n\n...[NEXUS TOOL OUTPUT TRUNCATED]...\n\n"
            + text[-half:]
        )

    def compact_messages(self, messages):
        total = sum(
            len(str(m.get("content", "")))
            for m in messages
        )

        if total <= self.max_chars:
            return messages

        system = [
            m
            for m in messages
            if m.get("role") == "system"
        ]

        recent = []

        budget = self.max_chars

        for msg in reversed(messages):
            if msg.get("role") == "system":
                continue

            size = len(
                str(
                    msg.get(
                        "content",
                        "",
                    )
                )
            )

            if size > budget:
                continue

            recent.append(msg)
            budget -= size

            if budget <= 0:
                break

        return (
            system
            + list(reversed(recent))
        )
