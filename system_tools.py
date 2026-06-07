"""
system_tools.py — JARVIS v3 System Tools
"""
from __future__ import annotations
import os, platform, subprocess, webbrowser
from pathlib import Path


def system_info(metric: str = "all") -> str:
    try:
        import psutil
    except ImportError:
        return "psutil not installed: pip install psutil"
    metric = metric.lower()
    lines = []
    if metric in ("cpu", "all"):
        cpu = psutil.cpu_percent(interval=0.5)
        lines.append(f"CPU: {cpu}%  ({psutil.cpu_count()} cores)")
    if metric in ("ram", "memory", "all"):
        vm = psutil.virtual_memory()
        lines.append(f"RAM: {vm.used/1e9:.1f}/{vm.total/1e9:.1f} GB  ({vm.percent}%)")
    if metric in ("disk", "all"):
        try:
            du = psutil.disk_usage("/")
            lines.append(f"Disk: {du.used/1e9:.1f}/{du.total/1e9:.1f} GB  ({du.percent}%)")
        except Exception:
            pass
    if metric in ("gpu", "all"):
        try:
            r = subprocess.run(
                ["nvidia-smi","--query-gpu=name,utilization.gpu,memory.used,memory.total",
                 "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=5)
            if r.returncode == 0:
                for line in r.stdout.strip().splitlines():
                    p = [x.strip() for x in line.split(",")]
                    lines.append(f"GPU: {p[0]}  {p[1]}% util  {p[2]}/{p[3]} MB VRAM")
        except Exception:
            lines.append("GPU: nvidia-smi unavailable")
    return "\n".join(lines) if lines else f"Unknown metric: {metric}"


def open_app(name: str) -> str:
    try:
        sys = platform.system()
        if sys == "Windows":
            os.startfile(name)
        elif sys == "Darwin":
            subprocess.Popen(["open", "-a", name])
        else:
            subprocess.Popen([name])
        return f"Opened: {name}"
    except Exception as e:
        return f"Could not open {name}: {e}"


def open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    webbrowser.open(url)
    return f"Opened: {url}"


def get_clipboard() -> str:
    try:
        import pyperclip
        return pyperclip.paste() or "(empty)"
    except ImportError:
        return "pyperclip not installed: pip install pyperclip"
    except Exception as e:
        return f"Clipboard error: {e}"


def set_clipboard(text: str) -> str:
    try:
        import pyperclip
        pyperclip.copy(text)
        return f"Copied {len(text)} chars to clipboard"
    except ImportError:
        return "pyperclip not installed"
    except Exception as e:
        return f"Clipboard error: {e}"


def take_screenshot(save_path: str | None = None) -> str:
    try:
        import mss, mss.tools
        from datetime import datetime
        if not save_path:
            d = Path("./data/screenshots")
            d.mkdir(parents=True, exist_ok=True)
            save_path = str(d / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png")
        with mss.mss() as sct:
            img = sct.grab(sct.monitors[0])
            mss.tools.to_png(img.rgb, img.size, output=save_path)
        return save_path
    except ImportError:
        return "mss not installed: pip install mss"
    except Exception as e:
        return f"Screenshot error: {e}"


def run_shell(command: str, timeout: int = 30) -> str:
    """High-risk — confirmed by SafetyLayer before reaching here."""
    try:
        r = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        out = (r.stdout or "")[:3000]
        if r.stderr:
            out += f"\n[stderr]: {r.stderr[:500]}"
        return out or "(no output)"
    except subprocess.TimeoutExpired:
        return f"Timed out after {timeout}s"
    except Exception as e:
        return f"Shell error: {e}"
