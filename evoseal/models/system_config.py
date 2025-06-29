"""System configuration model with YAML support for EVOSEAL."""

from __future__ import annotations

import os
from typing import Any, Optional

import yaml


class SystemConfig:
    REQUIRED_KEYS = ["dgm", "openevolve", "seal", "integration"]

    def __init__(self, config_dict: dict[str, Any]):
        self.config = config_dict

    def get(self, key: str, default: Any = None) -> Any:
        # Support dot notation for nested keys
        parts = key.split(".")
        current = self.config
        for part in parts:
            if not isinstance(current, dict) or part not in current:
                return default
            current = current[part]
        return current

    def validate(self) -> bool:
        missing = [k for k in self.REQUIRED_KEYS if k not in self.config]
        if missing:
            raise ValueError(f"Missing required configuration section(s): {', '.join(missing)}")
        return True

    @classmethod
    def from_yaml(cls, yaml_path: str) -> SystemConfig:
        if not os.path.exists(yaml_path):
            raise FileNotFoundError(f"YAML config file not found: {yaml_path}")
        with open(yaml_path) as f:
            config_dict = yaml.safe_load(f)
        return cls(config_dict)
