"""
browser_tools.py — JARVIS v4 Browser Control (CDP)

Changes vs v3:
  • auto_focus_media_tab(): scans all open tabs and switches to whichever
    one has a playing or buffered media element — so media commands work
    even when a different tab is focused.
  • Improved _MEDIA_FIND catches streams (no duration), readyState >= 1,
    and elements that have a src but haven't started buffering yet.
  • media_status() guards NaN duration for live streams.
  • Error messages include the raw JS error string for easier debugging.

Launch browser with: brave.exe --remote-debugging-port=9222
"""

from __future__ import annotations

import json
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)

# ── Media element finder ──────────────────────────────────────────────────
# Three-tier check: readyState >= 1 OR has currentSrc OR has src attribute.
# Picks the element with the longest duration; falls back to highest readyState.
_MEDIA_FIND = (
    "const _all = [...document.querySelectorAll('video,audio')];"
    "const _els = _all.filter(e => e.readyState >= 1 || e.currentSrc || e.src);"
    "const _el  = _els.reduce((a, b) => {"
    "  if (!a) return b;"
    "  if ((b.duration || 0) > (a.duration || 0)) return b;"
    "  if (!b.duration && b.readyState > a.readyState) return b;"
    "  return a;"
    "}, null);"
    "if (!_el) return 'no media found';"
)

# JS snippet that returns true if the page has any usable media
_HAS_MEDIA_JS = (
    "(function(){"
    "const els=[...document.querySelectorAll('video,audio')]"
    ".filter(e=>e.readyState>=1||e.currentSrc||e.src);"
    "return els.length > 0;"
    "})()"
)


def _media_js(action_code: str) -> str:
    return f"(function(){{{_MEDIA_FIND}{action_code}return 'ok';}})()"


_YT_KEY = lambda k: (
    f"(function(){{document.dispatchEvent(new KeyboardEvent('keydown',"
    f"{{key:'{k}',bubbles:true,cancelable:true}}));return 'ok';}})()"
)


class CDPBrowser:
    def __init__(self, host: str = "localhost", port: int = 9222) -> None:
        self.host   = host
        self.port   = port
        self._base  = f"http://{host}:{port}"
        self._active_tab: dict | None = None

    def is_connected(self) -> bool:
        try:
            return requests.get(f"{self._base}/json/version", timeout=2).status_code == 200
        except Exception:
            return False

    def connect(self) -> bool:
        try:
            for tab in self._get_tabs():
                if tab.get("type") == "page":
                    self._active_tab = tab
                    return True
        except Exception as e:
            logger.debug("CDP connect: %s", e)
        return False

    def _get_tabs(self) -> list[dict]:
        return requests.get(f"{self._base}/json", timeout=3).json()

    def _refresh_tab(self) -> None:
        """Re-fetch active tab metadata (URL/title may have changed)."""
        try:
            tabs = [t for t in self._get_tabs() if t.get("type") == "page"]
            if tabs:
                for t in tabs:
                    if self._active_tab and t.get("id") == self._active_tab.get("id"):
                        self._active_tab = t
                        return
                self._active_tab = tabs[0]
        except Exception:
            pass

    def _eval(self, js: str, tab: dict | None = None) -> str:
        """Execute JS via WebSocket CDP on the given tab (or active tab)."""
        target = tab or self._active_tab
        if not target:
            self.connect()
            target = self._active_tab
        ws_url = (target or {}).get("webSocketDebuggerUrl")
        if not ws_url:
            return "no ws url"
        try:
            import websockets, asyncio

            async def _run():
                async with websockets.connect(
                    ws_url, max_size=10_000_000, open_timeout=5
                ) as ws:
                    cmd = json.dumps({
                        "id": 1,
                        "method": "Runtime.evaluate",
                        "params": {"expression": js, "returnByValue": True},
                    })
                    await ws.send(cmd)
                    raw  = await asyncio.wait_for(ws.recv(), timeout=10)
                    data = json.loads(raw)
                    exc  = data.get("result", {}).get("exceptionDetails")
                    if exc:
                        return f"js error: {exc.get('text', 'unknown')}"
                    val = data.get("result", {}).get("result", {}).get("value", "")
                    return str(val)

            return asyncio.run(_run())
        except ImportError:
            return "websockets not installed — run: pip install websockets"
        except Exception as e:
            return f"eval error: {e}"

    def _is_youtube(self) -> bool:
        return "youtube.com" in (self._active_tab or {}).get("url", "")

    # ── #5 Auto media-tab focus ───────────────────────────────────────────

    def auto_focus_media_tab(self) -> str:
        """
        Scan all open page tabs and switch to the first one that has a
        loaded/playing media element.  If none is found, stay on the
        current tab so subsequent commands still attempt to run.
        """
        try:
            tabs = [t for t in self._get_tabs() if t.get("type") == "page"]
            # Check current tab first — cheapest happy path
            if self._active_tab:
                r = self._eval(_HAS_MEDIA_JS, self._active_tab)
                if r == "True":
                    return "already on media tab"

            for tab in tabs:
                if tab.get("id") == (self._active_tab or {}).get("id"):
                    continue   # already checked
                r = self._eval(_HAS_MEDIA_JS, tab)
                if r == "True":
                    self._active_tab = tab
                    requests.get(f"{self._base}/json/activate/{tab['id']}", timeout=2)
                    logger.debug("Auto-switched to media tab: %s", tab.get("title", ""))
                    return f"switched to media tab: {tab.get('title','')[:40]}"
        except Exception as e:
            logger.debug("auto_focus_media_tab error: %s", e)
        return "no media tab found — staying on current tab"

    # ── Tabs ──────────────────────────────────────────────────────────────

    def list_tabs(self) -> str:
        try:
            tabs = [t for t in self._get_tabs() if t.get("type") == "page"]
            if not tabs:
                return "No open tabs found."
            lines = [
                f"[{i}] {t.get('title','')[:60]} — {t.get('url','')[:80]}"
                for i, t in enumerate(tabs)
            ]
            return "\n".join(lines)
        except Exception as e:
            return f"Error listing tabs: {e}"

    def switch_tab(self, index: int = 0, title: str = "") -> str:
        try:
            tabs   = [t for t in self._get_tabs() if t.get("type") == "page"]
            target = None
            if title:
                for t in tabs:
                    if title.lower() in t.get("title", "").lower():
                        target = t
                        break
            elif 0 <= index < len(tabs):
                target = tabs[index]
            if not target:
                return "Tab not found."
            self._active_tab = target
            requests.get(f"{self._base}/json/activate/{target['id']}", timeout=2)
            return f"Switched to: {target.get('title', 'tab')}"
        except Exception as e:
            return f"Error switching tab: {e}"

    # ── Media ─────────────────────────────────────────────────────────────

    def media_play(self) -> str:
        r = self._eval(_media_js("_el.play();"))
        return "▶ Playing" if "ok" in r else f"Could not play: {r}"

    def media_pause(self) -> str:
        r = self._eval(_media_js("_el.pause();"))
        return "⏸ Paused" if "ok" in r else f"Could not pause: {r}"

    def media_toggle(self) -> str:
        r = self._eval(_media_js("if(_el.paused)_el.play();else _el.pause();"))
        return "⏯ Toggled play/pause" if "ok" in r else f"Could not toggle: {r}"

    def media_volume(self, delta: float = 0.1) -> str:
        r = self._eval(_media_js(
            f"_el.volume = Math.min(1, Math.max(0, _el.volume + ({delta})));"
        ))
        direction = "up" if delta > 0 else "down"
        return f"🔊 Volume {direction}" if "ok" in r else f"Could not adjust volume: {r}"

    def media_mute(self) -> str:
        r = self._eval(_media_js("_el.muted = !_el.muted;"))
        return "🔇 Mute toggled" if "ok" in r else f"Could not toggle mute: {r}"

    def media_fullscreen(self) -> str:
        if self._is_youtube():
            r = self._eval(_YT_KEY("f"))
        else:
            r = self._eval(_media_js(
                "if (!document.fullscreenElement) _el.requestFullscreen();"
                "else document.exitFullscreen();"
            ))
        return "⛶ Fullscreen toggled" if "ok" in r else f"Could not toggle fullscreen: {r}"

    def media_skip(self, seconds: float = 10.0) -> str:
        if self._is_youtube() and abs(seconds) in (10, 30):
            r = self._eval(_YT_KEY("l" if seconds > 0 else "j"))
        else:
            r = self._eval(_media_js(f"_el.currentTime += ({seconds});"))
        label = f"+{abs(seconds)}s" if seconds > 0 else f"-{abs(seconds)}s"
        return f"⏩ Skipped {label}" if "ok" in r else f"Could not skip: {r}"

    def media_restart(self) -> str:
        r = self._eval(_media_js("_el.currentTime = 0; _el.play();"))
        return "⏮ Restarted from beginning" if "ok" in r else f"Could not restart: {r}"

    def media_status(self) -> str:
        js = (
            "(function(){"
            "const all=[...document.querySelectorAll('video,audio')];"
            "const el=all.filter(e=>e.readyState>=1||e.currentSrc||e.src)"
            "  .reduce((a,b)=>{"
            "    if(!a)return b;"
            "    if((b.duration||0)>(a.duration||0))return b;"
            "    if(!b.duration&&b.readyState>a.readyState)return b;"
            "    return a;"
            "  },null);"
            "if(!el)return 'no media';"
            "return JSON.stringify({"
            "  paused:el.paused,volume:el.volume,muted:el.muted,"
            "  current:el.currentTime,duration:el.duration,"
            "  readyState:el.readyState,src:el.currentSrc||el.src||''"
            "});"
            "})()"
        )
        r = self._eval(js)
        try:
            d = json.loads(r)

            def fmt(s):
                if s is None or (isinstance(s, float) and s != s):
                    return "?"
                if s == float("inf"):
                    return "∞"
                return f"{int(s // 60)}:{int(s % 60):02d}"

            state   = "⏸" if d.get("paused") else "▶"
            muted   = " 🔇" if d.get("muted") else ""
            vol     = int(d.get("volume", 1) * 100)
            cur     = fmt(d.get("current"))
            dur     = fmt(d.get("duration"))
            dur_str = f" / {dur}" if d.get("duration") else ""
            return f"{state}{muted} {cur}{dur_str}  Vol: {vol}%"
        except Exception:
            return r or "No media found"

    # ── Navigation ────────────────────────────────────────────────────────

    def goto(self, url: str) -> str:
        if not url.startswith(("http://", "https://")):
            url = "https://" + url
        try:
            r = requests.get(f"{self._base}/json/new?{url}", timeout=5)
            if r.ok:
                self._active_tab = r.json()
                return f"Navigated to {url}"
        except Exception as e:
            return f"Navigation error: {e}"
        return f"Navigated to {url}"

    def search(self, query: str) -> str:
        import urllib.parse
        return self.goto(f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}")

    def extract_page_text(self) -> str:
        r = self._eval("document.body && document.body.innerText.slice(0, 6000)")
        return r if r and len(r) > 10 else "Could not extract page text."

    def get_page_info(self) -> str:
        self._refresh_tab()
        t = self._active_tab or {}
        return f"Title: {t.get('title', '?')}\nURL: {t.get('url', '?')}"

    # ── Dispatch ──────────────────────────────────────────────────────────

    def execute(self, action: str, args: dict) -> str:
        if not self.is_connected():
            return (
                f"Browser not connected on port {self.port}. "
                f"Start Brave with: brave.exe --remote-debugging-port={self.port}"
            )
        if not self._active_tab:
            self.connect()

        dispatch = {
            "list_tabs":        lambda: self.list_tabs(),
            "switch_tab":       lambda: self.switch_tab(**args),
            "media_play":       lambda: self.media_play(),
            "media_pause":      lambda: self.media_pause(),
            "media_toggle":     lambda: self.media_toggle(),
            "media_volume":     lambda: self.media_volume(float(args.get("delta", 0.1))),
            "media_mute":       lambda: self.media_mute(),
            "media_fullscreen": lambda: self.media_fullscreen(),
            "media_skip":       lambda: self.media_skip(float(args.get("seconds", 10))),
            "media_restart":    lambda: self.media_restart(),
            "media_status":     lambda: self.media_status(),
            "goto":             lambda: self.goto(args.get("url", "")),
            "search":           lambda: self.search(args.get("query", "")),
            "extract_page_text":lambda: self.extract_page_text(),
            "get_page_info":    lambda: self.get_page_info(),
        }

        fn = dispatch.get(action)
        if fn:
            try:
                return fn()
            except Exception as e:
                return f"Browser '{action}' error: {e}"
        return f"Unknown browser action: {action}"


_browser: CDPBrowser | None = None


def get_browser(config=None) -> CDPBrowser:
    global _browser
    if _browser is None:
        port, host = 9222, "localhost"
        if config:
            port = int(config.get("browser.cdp_port", 9222))
            host = config.get("browser.cdp_host", "localhost")
        _browser = CDPBrowser(host=host, port=port)
        _browser.connect()
    return _browser
