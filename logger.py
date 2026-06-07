"""
logger.py — JARVIS v3 Logging Setup
"""
from __future__ import annotations
import logging, logging.handlers
from pathlib import Path


def setup(config=None) -> None:
    from config import get_config
    cfg = config or get_config()
    level_str = cfg.get("logging.level", "INFO").upper()
    log_dir   = Path(cfg.get("logging.log_dir", "./logs"))
    backups   = int(cfg.get("logging.max_log_files", 7))
    log_dir.mkdir(parents=True, exist_ok=True)

    fmt = logging.Formatter(
        "%(asctime)s  %(levelname)-8s  %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S")

    fh = logging.handlers.TimedRotatingFileHandler(
        log_dir / "jarvis.log", when="midnight",
        backupCount=backups, encoding="utf-8")
    fh.setFormatter(fmt)

    ch = logging.StreamHandler()
    ch.setFormatter(fmt)
    ch.setLevel(logging.INFO)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level_str, logging.INFO))
    root.addHandler(fh)
    root.addHandler(ch)

    for noisy in ("urllib3", "requests", "httpcore", "sentence_transformers"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
