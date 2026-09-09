from __future__ import annotations


class ModelRouter:
    """
    V8 starts conservatively:
    all roles fall back to the configured Nexus model.

    Workspace/global configuration can override individual roles
    later without changing the execution engine.
    """

    def __init__(self, config):
        self.config = config

    def for_role(self, role):
        routes = self.config.get(
            "model_routes",
            {},
        )

        return routes.get(
            role,
            self.config["model"],
        )
