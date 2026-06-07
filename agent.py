"""
agent.py — JARVIS v4.1 Agent Core

Changes vs v4.0:
• Conversation history: rolling window of past turns is sent to the LLM
  every call so JARVIS remembers what was said earlier in the session.
• Graceful stop: stream_run checks a threading.Event so Stop actually
  cancels the generation loop instead of hard-killing the thread.
• Browser media auto-switch (#5): before any browser.media_* command,
  scan all tabs and switch to the one with a playing/loaded video element.
• Planning always uses fast_model.
• Shared _SYSTEM_JARVIS prompt ensures well-formatted responses.

Patches applied in v4.1:
• FIX #1  — run_shell now always requires explicit user confirmation via
  SafetyLayer regardless of config confirm_on list. It is also exposed in
  the planner prompt so the LLM can use it intentionally (with the gate).
• FIX #2  — _HISTORY_WINDOW is read from config.memory.window at runtime
  instead of being a hardcoded constant that can drift from config.yaml.
• FIX #3  — stream_run / run wrapped in top-level try/except so unhandled
  exceptions yield a visible error token instead of silently freezing the UI.
• FIX #6  — OSINT tool results are truncated to MAX_OSINT_OUTPUT chars and
  capped with a per-call 30 s timeout to prevent context blowout.
"""

from __future__ import annotations

import json
import logging
import re
import threading
from dataclasses import dataclass, field
from typing import Any, Generator

logger = logging.getLogger(__name__)

# ── Shared prompt constants ───────────────────────────────────────────────

_SYSTEM_JARVIS = (
    "You are JARVIS, a helpful and articulate local AI assistant. "
    "Always respond in clear, natural English with proper grammar, punctuation, "
    "and paragraph spacing. Never output raw JSON, tool names, or bullet lists "
    "of tool results — synthesize the information into a polished, human-readable answer."
)

_PLAN_SUFFIX = (
    "\n\nJSON format:\n"
    '{"steps": [{"tool": "tool_name", "args": {"key": "value"}, "description": "what this does"}]}\n'
    'For pure conversation (no tool needed): {"steps": []}\n'
)

# Media commands that benefit from auto tab-switching
_MEDIA_CMDS = {
    "media_play", "media_pause", "media_toggle", "media_volume",
    "media_mute", "media_fullscreen", "media_skip", "media_restart", "media_status",
}

# FIX #6 — hard cap on OSINT output to avoid flooding the context window
MAX_OSINT_OUTPUT = 2000
OSINT_TOOL_TIMEOUT = 30  # seconds

# FIX #2 — fallback default if config key is missing
_DEFAULT_HISTORY_WINDOW = 12


@dataclass
class StepResult:
    tool: str
    args: dict
    description: str
    result: str
    success: bool
    iteration: int


@dataclass
class TaskSession:
    goal: str
    iteration: int = 0
    retries: int = 0
    tool_log: list[dict] = field(default_factory=list)

    def record(self, tool: str, args: dict, result: str) -> None:
        self.tool_log.append({"tool": tool, "args": args, "result": result[:300]})
        self.iteration += 1

    def context_summary(self) -> str:
        if not self.tool_log:
            return ""
        lines = [f"[{e['tool']}] {e['result'][:200]}" for e in self.tool_log[-4:]]
        return "Recent steps:\n" + "\n".join(lines)


class JarvisAgent:
    def __init__(self, router=None, memory=None, safety=None,
                 plugins=None, config=None) -> None:
        self.router = router
        self.memory = memory
        self.safety = safety
        self.plugins = plugins
        self.config = config
        self.max_tool_rounds = int((config.get("agent.max_tool_rounds") if config else None) or 8)
        self.max_replan = int((config.get("agent.max_replan") if config else None) or 2)

        # FIX #2 — read history window from config at construction time so it
        # stays in sync with config.yaml instead of using a hardcoded constant.
        self._history_window: int = int(
            (config.get("memory.window") if config else None) or _DEFAULT_HISTORY_WINDOW
        )

        # Rolling conversation history — shared across all calls this session
        self._conv_history: list[dict] = []

        # Stop event — set by main_window when the user clicks ⏹ Stop
        self.stop_event = threading.Event()

    # ── Public API ────────────────────────────────────────────────────────

    def stop(self) -> None:
        """Signal the current stream to stop cleanly."""
        self.stop_event.set()

    def reset_stop(self) -> None:
        """Clear the stop flag before starting a new stream."""
        self.stop_event.clear()

    def run(self, user_input: str) -> dict[str, Any]:
        # FIX #3 — top-level error boundary so callers always get a dict back
        try:
            return self._run_inner(user_input)
        except Exception as exc:
            logger.exception("Unhandled error in run()")
            return {
                "status": "error",
                "response": f"⚠️ An unexpected error occurred: {exc}",
                "steps": 0,
                "details": [],
            }

    def _run_inner(self, user_input: str) -> dict[str, Any]:
        self.reset_stop()
        session = TaskSession(goal=user_input)
        all_details: list[StepResult] = []
        final = ""

        for attempt in range(self.max_replan + 1):
            plan = self._plan(user_input, session, attempt)
            steps = plan.get("steps", [])

            if not steps:
                final = self._direct_answer(user_input)
                break

            step_results, any_ok = self._execute_steps(steps, session)
            all_details.extend(step_results)

            if any_ok:
                final = self._synthesize(user_input, all_details)
                break

            if attempt < self.max_replan:
                session.retries += 1
            else:
                final = "I was unable to complete the task.\n" + self._failure_summary(all_details)

        self._push_history("user", user_input)
        self._push_history("assistant", final or "Done.")

        if self.memory and final:
            try:
                self.memory.store(user_input, final)
            except Exception:
                pass

        return {
            "status": "complete",
            "response": final or "Done.",
            "steps": session.iteration,
            "details": [vars(d) for d in all_details],
        }

    def stream_run(self, user_input: str) -> Generator[str, None, None]:
        # FIX #3 — wrap the entire generator body; yield an error token on crash
        try:
            yield from self._stream_run_inner(user_input)
        except Exception as exc:
            logger.exception("Unhandled error in stream_run()")
            yield f"\n⚠️ Unexpected error: {exc}"

    def _stream_run_inner(self, user_input: str) -> Generator[str, None, None]:
        self.reset_stop()
        session = TaskSession(goal=user_input)
        all_details: list[StepResult] = []
        response_buf = ""

        for attempt in range(self.max_replan + 1):
            plan = self._plan(user_input, session, attempt)
            steps = plan.get("steps", [])

            if not steps:
                for tok in self._stream_direct(user_input):
                    if self.stop_event.is_set():
                        break
                    response_buf += tok
                    yield tok
                self._push_history("user", user_input)
                self._push_history("assistant", response_buf)
                return

            for step in steps:
                if self.stop_event.is_set():
                    yield "\n[Stopped]"
                    return

                session.iteration += 1
                tool = step.get("tool", "")
                args = step.get("args", {})
                desc = step.get("description", tool)

                yield f"\r🔧 {desc}…"

                result_str = self._dispatch(tool, args)
                ok = getattr(self._verify(tool, args, result_str), "success", True)
                session.record(tool, args, result_str)
                all_details.append(StepResult(
                    tool=tool, args=args, description=desc,
                    result=result_str, success=ok,
                    iteration=session.iteration,
                ))

            if any(d.success for d in all_details):
                break

            if attempt < self.max_replan:
                session.retries += 1
            else:
                yield "\n⚠️ I could not complete all steps.\n"
                return

        yield "\r"

        for tok in self._stream_synthesize(user_input, all_details):
            if self.stop_event.is_set():
                break
            response_buf += tok
            yield tok

        self._push_history("user", user_input)
        self._push_history("assistant", response_buf)

        if self.memory and response_buf:
            try:
                self.memory.store(user_input, response_buf)
            except Exception:
                pass

    # ── Conversation history ──────────────────────────────────────────────

    def _push_history(self, role: str, content: str) -> None:
        self._conv_history.append({"role": role, "content": content})
        # FIX #2 — use instance variable (from config) instead of module constant
        if len(self._conv_history) > self._history_window * 2:
            self._conv_history = self._conv_history[-(self._history_window * 2):]

    def _history_messages(self) -> list[dict]:
        """Return a copy of the current rolling history for injection into LLM calls."""
        return list(self._conv_history)

    def clear_history(self) -> None:
        """Called by main_window when the user clears the chat."""
        self._conv_history.clear()

    # ── Planning ──────────────────────────────────────────────────────────

    def _plan(self, user_input: str, session: TaskSession, attempt: int = 0) -> dict:
        if self.router is None:
            return {"steps": []}

        mem_ctx = ""
        if self.memory:
            try:
                mem_ctx = self.memory.inject_context(user_input, "")[:500]
            except Exception:
                pass

        failure_note = ""
        if attempt > 0:
            failure_note = (
                f"\nAttempt {attempt} failed. Try DIFFERENT tools.\n"
                + session.context_summary()
            )

        plugin_line = self._plugin_tools()
        if plugin_line:
            plugin_line = "\n" + plugin_line

        # FIX #1 — run_shell is now listed in the planner so the LLM can use it,
        # but safety.py always requires explicit confirmation for it.
        prompt = (
            "You are JARVIS. Output ONLY valid JSON to plan this task.\n\n"
            "Available tools:\n"
            "read_file(path), write_file(path,content), list_dir(path), search_files(query,root),\n"
            "delete_file(path), system_info(metric), open_app(name), open_url(url),\n"
            "run_shell(command)  ← ALWAYS requires user confirmation before executing,\n"
            "search_web(query), get_clipboard(), set_clipboard(text),\n"
            "take_screenshot(), describe_screenshot(), ocr_image(path),\n"
            "summarize_pdf(path), extract_tables(path), search_in_document(path,query),\n"
            "browser.list_tabs(), browser.switch_tab(index), browser.media_play(),\n"
            "browser.media_pause(), browser.media_toggle(), browser.media_volume(delta),\n"
            "browser.media_mute(), browser.media_fullscreen(), browser.media_skip(seconds),\n"
            "browser.media_restart(), browser.media_status(), browser.goto(url),\n"
            "browser.search(query), browser.extract_page_text(), browser.get_page_info(),\n"
            "username_search(username), social_search(name), email_breach_check(email),\n"
            "email_format_guess(domain), whois_lookup(domain), dns_lookup(domain,record_type),\n"
            "subdomain_enum(domain), ssl_cert_info(domain), wayback_lookup(url),\n"
            "tech_stack(domain), ip_osint(ip_or_host), port_scan(host,ports),\n"
            "generate_dorks(target,dork_type), google_dork(query), github_user_osint(username),\n"
            "github_secret_search(repo), extract_metadata(file_path),\n"
            "reverse_image_search(image_path_or_url), phone_lookup(number),\n"
            "full_domain_report(domain), full_person_report(name,extras),\n"
            "mcp.call(server,tool,args)  ← call any connected MCP server tool"
            + plugin_line
            + _PLAN_SUFFIX
            + f"Memory context: {mem_ctx}\n"
            + failure_note
            + f"\nTask: {user_input}"
        )

        try:
            raw = self.router.chat_sync(
                [{"role": "user", "content": prompt}],
                model=self.router.fast_model,
            )
            return self._parse_json(raw)
        except Exception as e:
            logger.warning("Planning failed: %s", e)
            return {"steps": []}

    def _plugin_tools(self) -> str:
        if not self.plugins:
            return ""
        try:
            tools = self.plugins.list_tools()[:6]
            return ", ".join(f"plugin.{t}()" for t in tools) if tools else ""
        except Exception:
            return ""

    # ── Execution ─────────────────────────────────────────────────────────

    def _execute_steps(self, steps: list[dict], session: TaskSession):
        results, any_ok = [], False
        for step in steps:
            if self.stop_event.is_set():
                break
            session.iteration += 1
            tool = step.get("tool", "")
            args = step.get("args", {})
            result_str = self._dispatch(tool, args)
            ok = getattr(self._verify(tool, args, result_str), "success", True)
            any_ok = any_ok or ok
            session.record(tool, args, result_str)
            results.append(StepResult(
                tool=tool, args=args,
                description=step.get("description", tool),
                result=result_str, success=ok,
                iteration=session.iteration,
            ))
        return results, any_ok

    def _dispatch(self, tool: str, args: dict) -> str:
        try:
            # FIX #1 — run_shell is unconditionally high-risk; always confirm,
            # even if the operator forgot to list it in config confirm_on.
            if tool in ("run_shell", "shell"):
                detail = f"Command: {args.get('command', args)}"
                if self.safety:
                    if not self.safety.request_confirmation(tool, detail):
                        return f"[Denied] User did not confirm shell execution."
                else:
                    # No safety layer attached — refuse rather than run blind
                    return "[Denied] run_shell requires a SafetyLayer but none is configured."

            elif self.safety and self.safety.requires_confirmation(tool):
                detail = f"Tool: {tool}\nArgs: {json.dumps(args, default=str)[:200]}"
                if not self.safety.request_confirmation(tool, detail):
                    return f"[Denied] User did not confirm: {tool}"

            if tool.startswith("browser."):
                return self._dispatch_browser(tool, args)
            if tool.startswith("plugin."):
                name = tool[7:]
                return str(self.plugins.execute_tool(name, **args)) if self.plugins else "No plugins"
            if tool.startswith("mcp."):
                return self._dispatch_mcp(tool, args)
            return self._dispatch_builtin(tool, args)

        except Exception as e:
            logger.exception("Dispatch error: %s", tool)
            return f"Error in {tool}: {e}"

    # FIX #6 — OSINT tools are wrapped with a timeout and output truncation
    _OSINT_TOOLS = {
        "username_search", "social_search", "email_breach_check", "email_format_guess",
        "whois_lookup", "dns_lookup", "subdomain_enum", "ssl_cert_info", "wayback_lookup",
        "tech_stack", "ip_osint", "port_scan", "generate_dorks", "google_dork",
        "github_user_osint", "github_secret_search", "extract_metadata",
        "reverse_image_search", "phone_lookup", "full_domain_report", "full_person_report",
    }

    def _dispatch_builtin(self, tool: str, args: dict) -> str:
        import file_tools, system_tools, web_tools, pdf_tools, vision_tools, osint_tools

        table = {
            "read_file":             lambda: file_tools.read_file(**args),
            "write_file":            lambda: file_tools.write_file(**args),
            "list_dir":              lambda: file_tools.list_dir(**args),
            "search_files":          lambda: file_tools.search_files(**args),
            "delete_file":           lambda: file_tools.delete_file(**args),
            "system_info":           lambda: system_tools.system_info(**args),
            "open_app":              lambda: system_tools.open_app(**args),
            "open_url":              lambda: system_tools.open_url(**args),
            "take_screenshot":       lambda: system_tools.take_screenshot(),
            "describe_screenshot":   lambda: vision_tools.describe_screenshot(self.router),
            "ocr_image":             lambda: vision_tools.ocr_image(**args),
            "get_clipboard":         lambda: system_tools.get_clipboard(),
            "set_clipboard":         lambda: system_tools.set_clipboard(**args),
            # FIX #1 — run_shell is intentionally NOT in this table.
            # It is handled explicitly in _dispatch() above so it always
            # passes through the mandatory confirmation gate first.
            "search_web":            lambda: web_tools.search_web(**args),
            "fetch_url":             lambda: web_tools.fetch_url(**args),
            "summarize_pdf":         lambda: pdf_tools.summarize_pdf(self.router, **args),
            "extract_tables":        lambda: pdf_tools.extract_tables(**args),
            "search_in_document":    lambda: pdf_tools.search_in_document(**args),
            # ── OSINT ──────────────────────────────────────────────────────
            "username_search":       lambda: osint_tools.username_search(**args),
            "social_search":         lambda: osint_tools.social_search(**args),
            "email_breach_check":    lambda: osint_tools.email_breach_check(**args),
            "email_format_guess":    lambda: osint_tools.email_format_guess(**args),
            "whois_lookup":          lambda: osint_tools.whois_lookup(**args),
            "dns_lookup":            lambda: osint_tools.dns_lookup(**args),
            "subdomain_enum":        lambda: osint_tools.subdomain_enum(**args),
            "ssl_cert_info":         lambda: osint_tools.ssl_cert_info(**args),
            "wayback_lookup":        lambda: osint_tools.wayback_lookup(**args),
            "tech_stack":            lambda: osint_tools.tech_stack(**args),
            "ip_osint":              lambda: osint_tools.ip_osint(**args),
            "port_scan":             lambda: osint_tools.port_scan(**args),
            "generate_dorks":        lambda: osint_tools.generate_dorks(**args),
            "google_dork":           lambda: osint_tools.google_dork(**args),
            "github_user_osint":     lambda: osint_tools.github_user_osint(**args),
            "github_secret_search":  lambda: osint_tools.github_secret_search(**args),
            "extract_metadata":      lambda: osint_tools.extract_metadata(**args),
            "reverse_image_search":  lambda: osint_tools.reverse_image_search(**args),
            "phone_lookup":          lambda: osint_tools.phone_lookup(**args),
            "full_domain_report":    lambda: osint_tools.full_domain_report(**args),
            "full_person_report":    lambda: osint_tools.full_person_report(**args),
        }

        fn = table.get(tool)
        if not fn:
            return f"Unknown tool: {tool}"

        # FIX #6 — apply timeout + truncation for OSINT tools
        if tool in self._OSINT_TOOLS:
            return self._run_with_timeout(fn, OSINT_TOOL_TIMEOUT, MAX_OSINT_OUTPUT)

        r = fn()
        return str(r) if r is not None else "Done."

    @staticmethod
    def _run_with_timeout(fn, timeout_s: int, max_chars: int) -> str:
        """Run fn() in a thread with a timeout; truncate output to max_chars."""
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as ex:
            future = ex.submit(fn)
            try:
                result = future.result(timeout=timeout_s)
                text = str(result) if result is not None else "Done."
                if len(text) > max_chars:
                    text = text[:max_chars] + f"\n… [truncated — {len(text) - max_chars} chars omitted]"
                return text
            except concurrent.futures.TimeoutError:
                return f"[Timeout] Tool did not complete within {timeout_s}s."
            except Exception as e:
                return f"Error: {e}"

    def _dispatch_browser(self, tool: str, args: dict) -> str:
        try:
            from browser_tools import get_browser
            browser = get_browser(self.config)
            action = tool.split(".", 1)[1]
            if action in _MEDIA_CMDS:
                browser.auto_focus_media_tab()
            return browser.execute(action, args)
        except Exception as e:
            return f"Browser error: {e}"

    def _dispatch_mcp(self, tool: str, args: dict) -> str:
        """Route mcp.call(server, tool, args) to the MCP bridge."""
        try:
            from mcp_bridge import MCPBridge
            bridge = MCPBridge.instance()
            server = args.get("server", "")
            mcp_tool = args.get("tool", "")
            mcp_args = args.get("args", {})
            return bridge.call(server, mcp_tool, mcp_args)
        except Exception as e:
            return f"MCP error: {e}"

    def _verify(self, tool: str, args: dict, result: str):
        if self.safety:
            try:
                return self.safety.verify_tool_result(tool, args, result)
            except Exception:
                pass
        return None

    # ── Synthesis ─────────────────────────────────────────────────────────

    def _build_messages(self, system: str, final_user: str) -> list[dict]:
        msgs = [{"role": "system", "content": system}]
        msgs.extend(self._history_messages())
        msgs.append({"role": "user", "content": final_user})
        return msgs

    def _synthesize(self, user_input: str, details: list[StepResult]) -> str:
        if not self.router or not details:
            return "Task complete."
        ctx = "\n".join(f"[{d.tool}] {d.result[:600]}" for d in details if d.success)
        user_msg = (
            f"The user asked: {user_input}\n\n"
            f"Tool results:\n{ctx}\n\n"
            "Write a concise, well-structured answer in natural English. "
            "Use proper grammar and spacing. Do not repeat tool names or raw data."
        )
        return self.router.chat_sync(self._build_messages(_SYSTEM_JARVIS, user_msg))

    def _stream_synthesize(self, user_input: str, details: list[StepResult]):
        if not self.router or not details:
            yield "Task complete."
            return
        ctx = "\n".join(f"[{d.tool}] {d.result[:600]}" for d in details if d.success)
        user_msg = (
            f"The user asked: {user_input}\n\n"
            f"Tool results:\n{ctx}\n\n"
            "Write a concise, well-structured answer in natural English. "
            "Use proper grammar and spacing. Do not repeat tool names or raw data."
        )
        yield from self.router.chat(self._build_messages(_SYSTEM_JARVIS, user_msg))

    def _direct_answer(self, user_input: str) -> str:
        if not self.router:
            return "LLM not connected."
        sys_prompt = _SYSTEM_JARVIS
        if self.memory:
            try:
                sys_prompt = self.memory.inject_context(user_input, sys_prompt) or sys_prompt
            except Exception:
                pass
        return self.router.chat_sync(self._build_messages(sys_prompt, user_input))

    def _stream_direct(self, user_input: str):
        if not self.router:
            yield "LLM not connected."
            return
        sys_prompt = _SYSTEM_JARVIS
        if self.memory:
            try:
                sys_prompt = self.memory.inject_context(user_input, sys_prompt) or sys_prompt
            except Exception:
                pass
        yield from self.router.chat(self._build_messages(sys_prompt, user_input))

    def _failure_summary(self, details: list[StepResult]) -> str:
        failed = [d for d in details if not d.success]
        if not failed:
            return ""
        return "Errors encountered:\n" + "\n".join(
            f"  • {d.tool}: {d.result[:120]}" for d in failed[:4]
        )

    @staticmethod
    def _parse_json(text: str) -> dict:
        text = text.strip()
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        m = re.search(r"\{[\s\S]*\}", text, re.DOTALL)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                pass
        return {"steps": []}
