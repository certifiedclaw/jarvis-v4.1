"""
vision_tools.py — JARVIS v3 Vision Tools
"""
from __future__ import annotations
import base64
from pathlib import Path


def _b64(path: str) -> str:
    return base64.b64encode(Path(path).read_bytes()).decode()


def describe_image(router, image_path: str, prompt: str = "Describe this image in detail.") -> str:
    if router is None:
        return "LLM router not available."
    try:
        return "".join(router.describe_image(_b64(image_path), prompt))
    except FileNotFoundError:
        return f"Image not found: {image_path}"
    except Exception as e:
        return f"Vision error: {e}"


def describe_screenshot(router, prompt: str = "What is on the screen right now?") -> str:
    from system_tools import take_screenshot
    path = take_screenshot()
    if "error" in path.lower() or "not installed" in path.lower():
        return path
    return describe_image(router, path, prompt)


def ocr_image(image_path: str) -> str:
    try:
        import pytesseract
        from PIL import Image
        text = pytesseract.image_to_string(Image.open(image_path))
        return text.strip() or "(no text detected)"
    except ImportError:
        return "OCR unavailable: pip install pytesseract Pillow  (+ tesseract binary)"
    except Exception as e:
        return f"OCR error: {e}"
