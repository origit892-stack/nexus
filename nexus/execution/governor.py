from __future__ import annotations

import psutil


class ResourceGovernor:
    def snapshot(self):
        vm = psutil.virtual_memory()

        return {
            "memory_total_gb": round(
                vm.total / 1024**3,
                2,
            ),
            "memory_available_gb": round(
                vm.available / 1024**3,
                2,
            ),
            "memory_percent": vm.percent,
            "cpu_percent": psutil.cpu_percent(
                interval=0.1
            ),
        }

    def parallel_limit(
        self,
        configured,
    ):
        state = self.snapshot()

        if state["memory_percent"] >= 90:
            return 1

        if state["memory_percent"] >= 80:
            return min(
                2,
                int(configured),
            )

        return max(
            1,
            int(configured),
        )
