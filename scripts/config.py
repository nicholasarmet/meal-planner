from __future__ import annotations
import os
from pathlib import Path
import yaml

_DEFAULT = Path(__file__).parent.parent / "config.yaml"


def load_config(path: str | None = None) -> dict:
    p = Path(path) if path else Path(os.environ.get("MEAL_PLANNER_CONFIG", str(_DEFAULT)))
    with open(p) as f:
        config = yaml.safe_load(f)
    if not config.get("vault_path"):
        raise ValueError("vault_path must be set in config.yaml")
    return config


def get_vault_path(config: dict) -> Path:
    return Path(config["vault_path"])
