"""
file_tools.py — JARVIS v3 File Operations
"""
from __future__ import annotations
import os, glob
from pathlib import Path


def read_file(path: str, max_bytes: int = 5_242_880) -> str:
    path = os.path.expanduser(path)
    try:
        p = Path(path)
        if not p.exists():
            return f"File not found: {path}"
        size = p.stat().st_size
        if size > max_bytes:
            return f"File too large ({size//1024} KB). Max {max_bytes//1024} KB."
        return p.read_text(encoding="utf-8", errors="replace")
    except PermissionError:
        return f"Permission denied: {path}"
    except Exception as e:
        return f"Error reading {path}: {e}"


def write_file(path: str, content: str) -> str:
    path = os.path.expanduser(path)
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {path}"
    except Exception as e:
        return f"Write error {path}: {e}"


def list_dir(path: str = ".", max_entries: int = 200) -> str:
    path = os.path.expanduser(path)
    try:
        p = Path(path)
        if not p.exists():
            return f"Not found: {path}"
        entries = sorted(p.iterdir(), key=lambda e: (e.is_file(), e.name.lower()))
        lines = []
        for e in entries[:max_entries]:
            icon = "📁" if e.is_dir() else "📄"
            size = f" ({e.stat().st_size:,}B)" if e.is_file() else ""
            lines.append(f"{icon} {e.name}{'/' if e.is_dir() else ''}{size}")
        if len(entries) > max_entries:
            lines.append(f"… {len(entries)-max_entries} more")
        return f"{path}:\n" + "\n".join(lines)
    except Exception as e:
        return f"List error: {e}"


def search_files(query: str, root: str = "~", extensions: str = "") -> str:
    root = os.path.expanduser(root)
    ext_list = [x.strip().lstrip("*.") for x in extensions.split(",") if x.strip()] if extensions else []
    matches = []
    q = query.lower()
    try:
        for dp, _, fnames in os.walk(root):
            if any(p.startswith(".") for p in Path(dp).parts[-2:]):
                continue
            for fname in fnames:
                if ext_list and not any(fname.endswith(f".{e}") for e in ext_list):
                    continue
                if q in fname.lower():
                    matches.append(os.path.join(dp, fname))
                if len(matches) >= 50:
                    break
            if len(matches) >= 50:
                break
        if not matches:
            return f"No files matching '{query}' in {root}"
        return f"{len(matches)} match(es):\n" + "\n".join(matches)
    except Exception as e:
        return f"Search error: {e}"


def delete_file(path: str) -> str:
    """High-risk — caller must confirm before dispatching here."""
    path = os.path.expanduser(path)
    try:
        p = Path(path)
        if not p.exists():
            return f"Not found: {path}"
        if p.is_dir():
            import shutil; shutil.rmtree(p)
            return f"Deleted directory: {path}"
        p.unlink()
        return f"Deleted: {path}"
    except Exception as e:
        return f"Delete error: {e}"
