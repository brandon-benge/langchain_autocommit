import copy
import os
import sys

import yaml


def _resolve_path() -> str:
    if getattr(sys, "frozen", False):
        return os.path.join(sys._MEIPASS, "params.yaml")
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "params.yaml")


def _load_file(path: str) -> dict:
    with open(path, "r") as f:
        return yaml.safe_load(f)


def deep_merge(base: dict, overrides: dict) -> dict:
    result = copy.deepcopy(base)
    for key, value in overrides.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = copy.deepcopy(value)
    return result


def load_config(overrides: dict | None = None) -> dict:
    cfg = _load_file(_resolve_path())
    if overrides:
        cfg = deep_merge(cfg, overrides)
    return cfg


DEFAULT_CONFIG = load_config()
