"""
api_server.py — JARVIS v4.1 REST / Streaming API Server

Wraps JarvisAgent in a FastAPI app so JARVIS can be used:
  • Headless on a home server
  • From a browser-based front-end
  • From other scripts or apps over HTTP

Enable in config.yaml:
    api:
      enabled: true
      host: 127.0.0.1   # change to 0.0.0.0 for LAN access
      port: 8765

Then start with:
    python api_server.py
or have main.py start it in a background thread when api.enabled is true.

Endpoints:
    POST /chat              — single-turn, returns full response as JSON
    POST /chat/stream       — streaming response (Server-Sent Events)
    POST /clear             — clear conversation history
    GET  /status            — health check + diagnostics summary
    GET  /tools             — list all available tools (built-in + MCP + plugins)

Authentication: set API_KEY env var to require a Bearer token.
Leave unset for local-only use.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# ── Optional FastAPI import with clear error message ──────────────────────
try:
    from fastapi import FastAPI, HTTPException, Request, Depends
    from fastapi.middleware.cors import CORSMiddleware
    from fastapi.responses import StreamingResponse, JSONResponse
    from pydantic import BaseModel
    import uvicorn
except ImportError:
    raise ImportError(
        "api_server.py requires FastAPI and uvicorn.\n"
        "Install them with:  pip install fastapi uvicorn[standard]"
    )


# ── Pydantic models ───────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str
    stream: bool = False


class ChatResponse(BaseModel):
    response: str
    steps: int
    status: str


# ── App factory ───────────────────────────────────────────────────────────

def create_app(agent, config=None) -> FastAPI:
    """
    Build and return the FastAPI application.

    Parameters
    ----------
    agent : JarvisAgent
        A fully initialised JarvisAgent instance.
    config : Config, optional
        The JARVIS config object. Used for CORS / auth settings.
    """
    app = FastAPI(
        title="JARVIS API",
        description="Local AI assistant REST & streaming interface",
        version="4.1.0",
    )

    # ── CORS — only allow localhost by default ────────────────────────────
    allow_external = config.get("api.allow_external") if config else False
    origins = ["*"] if allow_external else [
        "http://localhost", "http://127.0.0.1",
        "http://localhost:8765", "http://127.0.0.1:8765",
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Optional API key auth ─────────────────────────────────────────────
    _api_key = os.environ.get("JARVIS_API_KEY", "")

    def _check_auth(request: Request) -> None:
        if not _api_key:
            return  # no key set — open access (local use)
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer ") or auth[7:] != _api_key:
            raise HTTPException(status_code=401, detail="Unauthorized")

    # ── Endpoints ─────────────────────────────────────────────────────────

    @app.get("/status")
    async def status(request: Request):
        _check_auth(request)
        return {
            "status": "ok",
            "version": "4.1.0",
            "llm_connected": agent.router is not None,
            "memory_enabled": agent.memory is not None,
            "history_turns": len(agent._conv_history) // 2,
        }

    @app.get("/tools")
    async def list_tools(request: Request):
        _check_auth(request)
        builtin = [
            "read_file", "write_file", "list_dir", "search_files", "delete_file",
            "system_info", "open_app", "open_url", "run_shell",
            "search_web", "fetch_url", "take_screenshot", "describe_screenshot",
            "ocr_image", "get_clipboard", "set_clipboard",
            "summarize_pdf", "extract_tables", "search_in_document",
            "username_search", "social_search", "email_breach_check", "whois_lookup",
            "dns_lookup", "subdomain_enum", "ssl_cert_info", "port_scan",
            "full_domain_report", "full_person_report",
        ]
        plugin_tools = []
        if agent.plugins:
            try:
                plugin_tools = [f"plugin.{t}" for t in agent.plugins.list_tools()]
            except Exception:
                pass
        mcp_tools = []
        try:
            from mcp_bridge import MCPBridge
            mcp_tools = MCPBridge.instance().list_all_tools()
        except Exception:
            pass
        return {"builtin": builtin, "plugins": plugin_tools, "mcp": mcp_tools}

    @app.post("/chat")
    async def chat(req: ChatRequest, request: Request):
        _check_auth(request)
        if req.stream:
            # Redirect to streaming endpoint
            return await chat_stream(req, request)

        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(None, agent.run, req.message)
        return ChatResponse(
            response=result["response"],
            steps=result["steps"],
            status=result["status"],
        )

    @app.post("/chat/stream")
    async def chat_stream(req: ChatRequest, request: Request):
        _check_auth(request)

        async def event_generator() -> AsyncGenerator[str, None]:
            queue: asyncio.Queue[str | None] = asyncio.Queue()
            loop = asyncio.get_event_loop()

            def run_in_thread():
                try:
                    for token in agent.stream_run(req.message):
                        loop.call_soon_threadsafe(queue.put_nowait, token)
                except Exception as exc:
                    loop.call_soon_threadsafe(queue.put_nowait, f"\n⚠️ Error: {exc}")
                finally:
                    loop.call_soon_threadsafe(queue.put_nowait, None)  # sentinel

            thread = threading.Thread(target=run_in_thread, daemon=True)
            thread.start()

            while True:
                token = await queue.get()
                if token is None:
                    break
                # SSE format
                yield f"data: {json.dumps({'token': token})}\n\n"

            yield "data: [DONE]\n\n"

        return StreamingResponse(
            event_generator(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    @app.post("/clear")
    async def clear_history(request: Request):
        _check_auth(request)
        agent.clear_history()
        return {"status": "ok", "message": "Conversation history cleared."}

    return app


# ── Standalone entrypoint ─────────────────────────────────────────────────

def start_server(agent, config=None) -> None:
    """Start the API server in a background daemon thread."""
    if not (config and config.get("api.enabled")):
        return

    host = config.get("api.host") or "127.0.0.1"
    port = int(config.get("api.port") or 8765)

    app = create_app(agent, config)

    def _run():
        logger.info("JARVIS API server starting on http://%s:%d", host, port)
        uvicorn.run(app, host=host, port=port, log_level="warning")

    t = threading.Thread(target=_run, daemon=True, name="jarvis-api")
    t.start()
    logger.info("JARVIS API server thread started.")


if __name__ == "__main__":
    # Quick standalone test — boots with a dummy agent
    import sys
    logging.basicConfig(level=logging.INFO)

    class _DummyAgent:
        router = None
        memory = None
        plugins = None
        _conv_history = []

        def run(self, msg):
            return {"response": f"Echo: {msg}", "steps": 0, "status": "complete"}

        def stream_run(self, msg):
            for word in f"Echo: {msg}".split():
                yield word + " "

        def clear_history(self):
            self._conv_history.clear()

    _app = create_app(_DummyAgent())
    uvicorn.run(_app, host="127.0.0.1", port=8765)
