"""
config.py — JARVIS v3 Configuration
Single source of truth. Finds config.yaml next to this file.
"""
from __future__ import annotations
import os, copy
from pathlib import Path
from typing import Any
import yaml

# config.yaml lives right next to config.py (flat layout)
_DEFAULT_CONFIG = Path(__file__).parent / "config.yaml"


class Config:
    def __init__(self, path: str | Path | None = None) -> None:
        self._path = Path(path or _DEFAULT_CONFIG)
        self._data: dict = {}
        self.load()

    def load(self) -> None:
        if not self._path.exists():
            raise FileNotFoundError(
                f"config.yaml not found at: {self._path}\n"
                "Run JARVIS from the project root directory."
            )
        with open(self._path, "r", encoding="utf-8") as f:
            self._data = yaml.safe_load(f) or {}

    def save(self) -> None:
        with open(self._path, "w", encoding="utf-8") as f:
            yaml.dump(self._data, f, default_flow_style=False, allow_unicode=True)

    def get(self, key: str, default: Any = None) -> Any:
        parts = key.split(".")
        node = self._data
        for part in parts:
            if not isinstance(node, dict) or part not in node:
                return default
            node = node[part]
        return node

    def set(self, key: str, value: Any, save: bool = False) -> None:
        parts = key.split(".")
        node = self._data
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node[parts[-1]] = value
        if save:
            self.save()

    def section(self, key: str) -> dict:
        return copy.deepcopy(self._data.get(key, {}))

    def __getitem__(self, key: str) -> Any:
        return self._data[key]

    def __contains__(self, key: str) -> bool:
        return key in self._data

    @property
    def is_first_run(self) -> bool:
        return bool(self.get("app.first_run", True))

    def mark_first_run_complete(self) -> None:
        self.set("app.first_run", False, save=True)

    @property
    def ollama_url(self) -> str:
        return self.get("llm.ollama_url", "http://localhost:11434")

    @property
    def default_model(self) -> str:
        return self.get("llm.default_model", "qwen3:8b")

    @property
    def fast_model(self) -> str:
        return self.get("llm.fast_model", "qwen3:8b")

    @property
    def deep_model(self) -> str:
        return self.get("llm.deep_model", "qwen3:14b")

    @property
    def vision_model(self) -> str:
        return self.get("llm.vision_model", "llava:latest")

    @property
    def theme(self) -> str:
        return self.get("app.theme", "dark")

    @property
    def cdp_port(self) -> int:
        return int(self.get("browser.cdp_port", 9222))

    @property
    def allowed_paths(self) -> list[str]:
        return [os.path.expanduser(p)
                for p in self.get("safety.allowed_paths", ["~", "."])]

    @property
    def confirm_on(self) -> list[str]:
        return self.get("safety.confirm_on", ["delete", "shell", "write_file"])

    def validate(self) -> list[str]:
        warnings = []
        if not self.get("llm.ollama_url"):
            warnings.append("llm.ollama_url is not set")
        return warnings


_instance: Config | None = None

def get_config(path: str | Path | None = None) -> Config:
    global _instance
    if _instance is None:
        _instance = Config(path)
    return _instance

def reload_config() -> Config:
    global _instance
    _instance = None
    return get_config()
