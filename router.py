"""
router.py — JARVIS v4 LLM Router

Changes vs v3:
  • warmup(): sends a trivial prompt to fast_model in a background thread
    at startup so the first real user message doesn't pay cold-start cost.
  • Smarter routing (#4): token-count is the primary gate; keywords are only
    a secondary tiebreaker.  Stops "write" and "create" from always forcing
    the deep model on short one-liners.
  • temperature now correctly reads from config (was hard-coded to 0.4,
    conflicting with config.yaml's 0.7 default).
  • chat_sync accepts an explicit model= kwarg (needed by agent planning).
"""

from __future__ import annotations

import json
import logging
import subprocess
import threading
from typing import Generator

import requests

logger = logging.getLogger(__name__)

# Keywords that suggest the deep model is warranted
_DEEP_KEYWORDS = {
    "explain", "analyze", "analyse", "compare", "design", "architecture",
    "essay", "code", "debug", "fix", "summarize", "summarise",
    "plan", "strategy", "research", "implement", "refactor",
    "optimize", "document", "evaluate",
}

# Minimum token estimate before keywords can tip the scale
_KEYWORD_MIN_TOKENS = 60


class LLMRouter:
    def __init__(self, config=None) -> None:
        from config import get_config
        self._cfg        = config or get_config()
        self.ollama_url   = self._cfg.ollama_url
        self.fast_model   = self._cfg.fast_model
        self.deep_model   = self._cfg.deep_model
        self.vision_model = self._cfg.vision_model
        self.auto_route   = bool(self._cfg.get("llm.auto_route", True))
        # Token threshold above which we unconditionally use the deep model
        self.route_threshold = int(self._cfg.get("llm.route_threshold", 400))
        # Read temperature from config so config.yaml wins
        self.temperature = float(self._cfg.get("llm.temperature", 0.4))
        self.num_ctx     = int(self._cfg.get("llm.num_ctx", 8192))
        self.timeout     = int(self._cfg.get("llm.timeout_seconds", 120))

    # ── Health ────────────────────────────────────────────────────────────

    def is_online(self) -> bool:
        try:
            return requests.get(f"{self.ollama_url}/api/tags", timeout=3).status_code == 200
        except Exception:
            return False

    def get_available_models(self) -> list[str]:
        try:
            r = requests.get(f"{self.ollama_url}/api/tags", timeout=4)
            return [m["name"] for m in r.json().get("models", [])]
        except Exception:
            return []

    def pull_model(self, model: str, progress_cb=None) -> bool:
        try:
            result = subprocess.run(
                ["ollama", "pull", model], capture_output=False, timeout=600
            )
            return result.returncode == 0
        except Exception as e:
            logger.warning("Pull failed %s: %s", model, e)
            return False

    # ── #3 Warm-up ────────────────────────────────────────────────────────

    def warmup(self) -> None:
        """
        Fire a trivial prompt at the fast model in a background daemon thread.
        This loads the model weights into GPU/RAM so the first real user
        message is served immediately rather than waiting 5-15 seconds.
        Call this once from main.py right after the router is constructed.
        """
        def _ping():
            try:
                logger.info("Warming up fast model: %s", self.fast_model)
                self.chat_sync(
                    [{"role": "user", "content": "hi"}],
                    model=self.fast_model,
                )
                logger.info("Warm-up complete.")
            except Exception as e:
                logger.debug("Warm-up failed (non-fatal): %s", e)

        t = threading.Thread(target=_ping, daemon=True, name="jarvis-warmup")
        t.start()

    # ── #4 Smarter routing ────────────────────────────────────────────────

    def route(self, prompt: str) -> str:
        """
        Choose fast vs deep model.

        Logic (in priority order):
          1. If auto_route is off → always fast.
          2. If the prompt is very long (> route_threshold chars) → deep.
          3. If the prompt is short (< _KEYWORD_MIN_TOKENS chars) → fast,
             regardless of keywords.  This stops one-word commands like
             "write a note" from always routing to the big model.
          4. If the prompt contains deep-intent keywords AND is medium-length
             → deep.
          5. Otherwise → fast.
        """
        if not self.auto_route:
            return self.fast_model
        if len(prompt) > self.route_threshold:
            return self.deep_model
        if len(prompt) < _KEYWORD_MIN_TOKENS:
            return self.fast_model
        words = set(prompt.lower().split())
        if words & _DEEP_KEYWORDS:
            return self.deep_model
        return self.fast_model

    # ── Chat ──────────────────────────────────────────────────────────────

    def chat(
        self,
        messages: list[dict],
        model: str | None = None,
        stream: bool = True,
    ) -> Generator[str, None, None]:
        if model is None:
            last  = next((m["content"] for m in reversed(messages) if m["role"] == "user"), "")
            model = self.route(last)

        payload = {
            "model":    model,
            "messages": messages,
            "stream":   stream,
            "options":  {"temperature": self.temperature, "num_ctx": self.num_ctx},
        }

        try:
            resp = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload, stream=stream, timeout=self.timeout,
            )
            resp.raise_for_status()

            if stream:
                for raw in resp.iter_lines():
                    if not raw:
                        continue
                    data = json.loads(raw)
                    tok  = data.get("message", {}).get("content", "")
                    if tok:
                        yield tok
                    if data.get("done"):
                        break
            else:
                yield resp.json()["message"]["content"]

        except requests.exceptions.ConnectionError:
            yield (
                "\n⚠️ Ollama is not running.\n"
                "Open a terminal and run: ollama serve\n"
                "Then pull a model: ollama pull qwen3:8b"
            )
        except requests.exceptions.Timeout:
            yield "\n⚠️ Ollama timed out — the model may still be loading."
        except Exception as e:
            logger.error("LLM error: %s", e)
            yield f"\n⚠️ LLM error: {e}"

    def chat_sync(self, messages: list[dict], model: str | None = None) -> str:
        return "".join(self.chat(messages, model=model, stream=False))

    def describe_image(
        self, image_b64: str, prompt: str = "Describe this image."
    ) -> Generator[str, None, None]:
        msgs = [{"role": "user", "content": prompt, "images": [image_b64]}]
        yield from self.chat(msgs, model=self.vision_model)
