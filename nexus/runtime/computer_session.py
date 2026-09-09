from __future__ import annotations

from pathlib import Path

from nexus.runtime.computer_contract import (
    ComputerActionBudget,
)
from nexus.runtime.computer_evidence import (
    ComputerEvidenceLedger,
)
from nexus.runtime.screenshot import (
    capture_screenshot,
)
from nexus.runtime.vision import (
    OllamaVisionProvider,
)
from nexus.runtime.vision_verify import (
    verify_visual_change,
)


class VisionComputerSession:
    def __init__(
        self,
        vision_model,
        evidence_dir,
        *,
        max_actions=12,
    ):
        self.provider = (
            OllamaVisionProvider(
                vision_model
            )
        )

        self.evidence_dir = Path(
            evidence_dir
        ).resolve()

        self.evidence_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        self.budget = (
            ComputerActionBudget(
                max_actions=max_actions
            )
        )

        self.ledger = (
            ComputerEvidenceLedger()
        )

    def screenshot_before(
        self,
        prompt,
    ):
        path = capture_screenshot(
            self.evidence_dir
            / "before.png"
        )

        finding = self.provider.analyze(
            path,
            prompt,
        )

        self.ledger.record(
            "screenshot_before",
            path=path,
            finding=finding.summary,
        )

        return finding

    def screenshot_after(
        self,
        prompt,
    ):
        path = capture_screenshot(
            self.evidence_dir
            / "after.png"
        )

        finding = self.provider.analyze(
            path,
            prompt,
        )

        self.ledger.record(
            "screenshot_after",
            path=path,
            finding=finding.summary,
        )

        return finding

    def verify(
        self,
        before,
        after,
        expected,
    ):
        result = verify_visual_change(
            before.summary,
            after.summary,
            expected,
        )

        self.ledger.record(
            "verification",
            passed=result.passed,
            reason=result.reason,
            expected=expected,
        )

        return result
