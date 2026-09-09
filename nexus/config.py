from pathlib import Path
import copy
import yaml

GLOBAL_ROOT = Path.home() / ".nexus"
GLOBAL_CONFIG = GLOBAL_ROOT / "config.yaml"

DEFAULT_CONFIG = {
    "provider": None,
    "model": None,
    "base_url": None,
    "context_length": None,
    "hardware_profile": "auto",

    "agents": {
        "max_parallel": 2,
        "max_depth": 1,
        "max_iterations": 100,
    },

    "runtime": {
        "temperature": 0.10,
        "max_output_tokens": 8192,
    },

    "acceptance": {
        "reject_stub_evidence": True,
        "require_real_evidence_for_real_criteria": True,
    },
}


def deep_merge(base, override):
    result = copy.deepcopy(base)

    for key, value in (override or {}).items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value

    return result


def load_yaml(path):
    path = Path(path)

    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def save_yaml(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        yaml.safe_dump(
            data,
            f,
            sort_keys=False,
            allow_unicode=True,
        )


def global_config():
    return deep_merge(
        DEFAULT_CONFIG,
        load_yaml(GLOBAL_CONFIG),
    )


def find_workspace(start=None):
    current = Path(start or Path.cwd()).resolve()

    while True:
        if (current / ".nexus" / "workspace.yaml").exists():
            return current

        if current.parent == current:
            return None

        current = current.parent


def effective_config(workspace=None):
    cfg = global_config()

    ws = Path(workspace).resolve() if workspace else find_workspace()

    if ws:
        ws_cfg = load_yaml(
            ws / ".nexus" / "workspace.yaml"
        )

        cfg = deep_merge(
            cfg,
            ws_cfg.get("runtime", {}),
        )

        cfg["workspace_root"] = str(ws)
        cfg["workspace"] = ws_cfg

    else:
        cfg["workspace_root"] = None
        cfg["workspace"] = {}

    return cfg
