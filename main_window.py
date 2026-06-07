"""
main_window.py — JARVIS v4 Main Window

Changes vs v3:
  • Markdown rendering (#2): after each response finishes, the plain-text
    buffer is converted to HTML via the `markdown` package and inserted into
    the chat.  Streaming still uses fast insertText; the markdown pass runs
    on _on_done so there's no per-token overhead.
  • Stop event (#10): _stop() now calls agent.stop() (a threading.Event)
    instead of thread.terminate(), so the stream loop exits cleanly and
    Ollama isn't left generating in the background.
  • Status bar fix (#9): clears the "🔧 …" message the moment real tokens
    start arriving.
  • Save chat (#7): toolbar button exports the current session to a .md file.
  • Warm-up (#3): triggers router.warmup() after the window is shown.
  • clear_history: wired to agent.clear_history() when chat is cleared.
  • insertText for streaming (whitespace preserved).
  • QTextCharFormat colour set before streaming begins.
"""

from __future__ import annotations

import html
import logging

from PySide6.QtCore  import Qt, Signal, QThread, QTimer
from PySide6.QtGui   import (QFont, QTextCursor, QTextCharFormat, QColor,
                              QKeySequence, QShortcut)
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QTextEdit, QPushButton, QLabel, QTabWidget,
    QStatusBar, QFrame, QMessageBox, QFileDialog,
    QGridLayout,
)

logger = logging.getLogger(__name__)

# ── Markdown renderer ─────────────────────────────────────────────────────
try:
    import markdown as _md_lib

    _MD_EXTENSIONS = ["fenced_code", "tables", "nl2br", "sane_lists"]

    def _render_markdown(text: str) -> str:
        """Convert a markdown string to an HTML fragment styled for the dark UI."""
        raw_html = _md_lib.markdown(text, extensions=_MD_EXTENSIONS)
        # Inject inline CSS so Qt's limited HTML engine renders it reasonably
        styled = (
            raw_html
            .replace("<h1>",  '<h1 style="color:#8080ff;font-size:17px;margin:8px 0 4px 0;">')
            .replace("<h2>",  '<h2 style="color:#7070ee;font-size:15px;margin:6px 0 3px 0;">')
            .replace("<h3>",  '<h3 style="color:#6060cc;font-size:14px;margin:5px 0 2px 0;">')
            .replace("<strong>", '<strong style="color:#d0d8ff;">')
            .replace("<code>",
                     '<code style="background:#1e1e2e;color:#a0d0a0;'
                     'font-family:Consolas,monospace;padding:1px 4px;border-radius:3px;">')
            .replace("<pre>",
                     '<pre style="background:#1a1a2a;color:#a0d0a0;'
                     'font-family:Consolas,monospace;padding:8px;'
                     'border-radius:5px;margin:6px 0;white-space:pre-wrap;">')
            .replace("<blockquote>",
                     '<blockquote style="border-left:3px solid #4040a0;'
                     'margin:4px 0;padding-left:10px;color:#8080b0;">')
            .replace("<ul>", '<ul style="margin:4px 0 4px 16px;">')
            .replace("<ol>", '<ol style="margin:4px 0 4px 16px;">')
            .replace("<li>", '<li style="margin:2px 0;color:#d0d0e0;">')
            .replace("<p>",  '<p style="margin:4px 0;color:#d0d0e0;">')
            .replace("<a ",  '<a style="color:#6090ff;" ')
        )
        return styled

    _HAS_MARKDOWN = True

except ImportError:
    _HAS_MARKDOWN = False

    def _render_markdown(text: str) -> str:
        """Fallback: just HTML-escape and replace newlines."""
        return html.escape(text).replace("\n", "<br>")


# ── Stream worker ─────────────────────────────────────────────────────────

class StreamWorker(QThread):
    token    = Signal(str)
    finished = Signal()
    error    = Signal(str)

    def __init__(self, agent, user_input: str) -> None:
        super().__init__()
        self.agent      = agent
        self.user_input = user_input

    def run(self) -> None:
        try:
            for tok in self.agent.stream_run(self.user_input):
                self.token.emit(tok)
        except Exception as e:
            self.error.emit(str(e))
        finally:
            self.finished.emit()


# ── Main window ───────────────────────────────────────────────────────────

class MainWindow(QMainWindow):
    def __init__(self, ctx: dict) -> None:
        super().__init__()
        self.ctx    = ctx
        self.config = ctx["config"]
        self.router = ctx.get("router")
        self.memory = ctx.get("memory")
        self.voice  = ctx.get("voice")

        self._worker:        StreamWorker | None = None
        self._history:       list[str]           = []
        self._hist_idx:      int                 = -1
        self._is_typing:     bool                = False
        self._last_response: str                 = ""
        # Anchor point in the QTextDocument where the current streamed
        # response begins — used to replace plain text with markdown HTML.
        self._stream_start_pos: int              = 0

        from agent  import JarvisAgent
        from safety import get_safety

        safety = ctx.get("safety") or get_safety(self.config)
        safety.set_confirm_callback(self._confirm_dialog)

        self.agent = JarvisAgent(
            router=self.router,
            memory=self.memory,
            safety=safety,
            plugins=ctx.get("plugins"),
            config=self.config,
        )

        self.setWindowTitle("JARVIS v4")
        self.setMinimumSize(880, 620)
        self.resize(1060, 720)

        self._build_ui()
        self._setup_hotkey()
        self._setup_tray()

        if self.voice:
            self._setup_voice()

        self._welcome_message()

        # #3 Trigger model warm-up after the window is shown
        QTimer.singleShot(500, self._warmup)

    # ── UI ────────────────────────────────────────────────────────────────

    def _build_ui(self) -> None:
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        root.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_chat_tab(),    "💬 Chat")
        self._tabs.addTab(self._build_browser_tab(), "🌐 Browser")
        self._tabs.addTab(self._build_memory_tab(),  "🧠 Memory")
        self._tabs.addTab(self._build_tools_tab(),   "🔧 Tools")
        root.addWidget(self._tabs)

        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._update_status()

    def _build_header(self) -> QWidget:
        bar = QFrame()
        bar.setFixedHeight(50)
        bar.setStyleSheet("background:#0a0a12; border-bottom:1px solid #1a1a2a;")
        lay = QHBoxLayout(bar)
        lay.setContentsMargins(16, 0, 12, 0)

        title = QLabel("J A R V I S")
        title.setObjectName("title")
        title.setFont(QFont("Segoe UI", 14, QFont.Weight.Bold))
        lay.addWidget(title)

        self._model_lbl = QLabel("")
        self._model_lbl.setStyleSheet("color:#4040a0; font-size:11px;")
        self._update_model_label()
        lay.addWidget(self._model_lbl)
        lay.addStretch()

        for icon, tip, slot in [
            ("💾", "Save chat",   self._save_chat),
            ("⚙",  "Settings",   self._open_settings),
            ("📊", "Diagnostics", self._run_diagnostics),
            ("🗑",  "Clear chat",  self._clear_chat),
        ]:
            btn = QPushButton(icon)
            btn.setToolTip(tip)
            btn.setFixedSize(34, 34)
            btn.setStyleSheet(
                "QPushButton{background:transparent;border:none;font-size:16px;color:#8080cc;}"
                "QPushButton:hover{color:#ffffff;}")
            btn.clicked.connect(slot)
            lay.addWidget(btn)

        return bar

    def _build_chat_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self._chat = QTextEdit()
        self._chat.setObjectName("chat")
        self._chat.setReadOnly(True)
        self._chat.setFont(QFont("Segoe UI", 13))
        lay.addWidget(self._chat, 1)

        input_row = QHBoxLayout()
        input_row.setSpacing(8)

        self._input = QTextEdit()
        self._input.setObjectName("input")
        self._input.setFixedHeight(70)
        self._input.setPlaceholderText(
            "Ask JARVIS anything… (Enter to send, Shift+Enter for newline)")
        self._input.setFont(QFont("Segoe UI", 13))
        self._input.installEventFilter(self)
        input_row.addWidget(self._input, 1)

        btn_col = QVBoxLayout()
        btn_col.setSpacing(4)

        self._send_btn = QPushButton("Send ↵")
        self._send_btn.setObjectName("send")
        self._send_btn.setFixedSize(80, 32)
        self._send_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self._send_btn.clicked.connect(self._send)
        btn_col.addWidget(self._send_btn)

        self._stop_btn = QPushButton("⏹ Stop")
        self._stop_btn.setFixedSize(80, 30)
        self._stop_btn.setEnabled(False)
        self._stop_btn.clicked.connect(self._stop)
        btn_col.addWidget(self._stop_btn)

        input_row.addLayout(btn_col)
        lay.addLayout(input_row)
        return w

    def _build_browser_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(12)

        self._browser_status = QLabel("● Not connected")
        self._browser_status.setStyleSheet("color:#ff6060; font-size:13px;")
        lay.addWidget(self._browser_status)
        lay.addWidget(QLabel(
            "💡 Start Brave with: brave.exe --remote-debugging-port=9222",
            styleSheet="color:#5050a0; font-size:11px;"))

        controls = [
            ("List Tabs",    "browser.list_tabs()"),
            ("▶ Play",       "play the media"),
            ("⏸ Pause",      "pause the media"),
            ("⏩ +10s",       "skip forward 10 seconds"),
            ("⏪ -10s",       "skip back 10 seconds"),
            ("🔊 Vol+",       "increase volume"),
            ("🔉 Vol-",       "decrease volume"),
            ("🔇 Mute",       "mute the media"),
            ("⛶ Fullscreen", "toggle fullscreen"),
            ("⏮ Restart",    "restart the video"),
            ("📊 Status",    "what is the media status"),
        ]
        grid_w  = QWidget()
        grid    = QGridLayout(grid_w)
        grid.setSpacing(6)
        for i, (label, cmd) in enumerate(controls):
            btn = QPushButton(label)
            btn.setFixedHeight(34)
            btn.clicked.connect(lambda _, c=cmd: self._quick_send(c))
            grid.addWidget(btn, i // 4, i % 4)
        lay.addWidget(grid_w)

        self._browser_out = QTextEdit()
        self._browser_out.setObjectName("chat")
        self._browser_out.setReadOnly(True)
        self._browser_out.setPlaceholderText("Browser command output appears here…")
        lay.addWidget(self._browser_out, 1)

        self._refresh_browser_status()
        QTimer.singleShot(2000, self._refresh_browser_status)
        return w

    def _build_memory_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        row = QHBoxLayout()
        self._mem_refresh = QPushButton("🔄 Refresh")
        self._mem_refresh.clicked.connect(self._refresh_memory)
        row.addWidget(self._mem_refresh)
        clear_btn = QPushButton("🗑 Clear All")
        clear_btn.setObjectName("danger")
        clear_btn.clicked.connect(self._clear_memory)
        row.addWidget(clear_btn)
        row.addStretch()
        lay.addLayout(row)

        self._mem_display = QTextEdit()
        self._mem_display.setObjectName("chat")
        self._mem_display.setReadOnly(True)
        self._mem_display.setFont(QFont("Consolas", 11))
        lay.addWidget(self._mem_display, 1)

        self._refresh_memory()
        return w

    def _build_tools_tab(self) -> QWidget:
        w   = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(16, 16, 16, 16)
        lay.setSpacing(10)

        shortcuts = [
            ("📸 Screenshot",     "take a screenshot and describe what you see"),
            ("📋 Read Clipboard", "what is in my clipboard"),
            ("💻 System Info",    "show my system info"),
            ("🔍 Search Web…",    "search the web for "),
            ("📂 List Downloads", "list my downloads folder"),
            ("📄 Summarize PDF…", None),
            ("🔌 List Plugins",   "list all loaded plugins"),
            ("🩺 Run Diagnostics","status"),
        ]
        grid = QWidget()
        gl   = QGridLayout(grid)
        gl.setSpacing(8)
        for i, (label, cmd) in enumerate(shortcuts):
            btn = QPushButton(label)
            btn.setFixedHeight(40)
            if cmd:
                btn.clicked.connect(lambda _, c=cmd: self._quick_send(c))
            else:
                btn.clicked.connect(self._pick_pdf)
            gl.addWidget(btn, i // 2, i % 2)

        lay.addWidget(grid)
        lay.addStretch()
        return w

    # ── Event filter ──────────────────────────────────────────────────────

    def eventFilter(self, obj, event) -> bool:
        from PySide6.QtCore import QEvent
        from PySide6.QtGui  import QKeyEvent

        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            if (event.key() == Qt.Key.Key_Return
                    and not (event.modifiers() & Qt.KeyboardModifier.ShiftModifier)):
                self._send()
                return True
            if event.key() == Qt.Key.Key_Up:
                self._hist_prev(); return True
            if event.key() == Qt.Key.Key_Down:
                self._hist_next(); return True
        return super().eventFilter(obj, event)

    # ── Chat send / stream ────────────────────────────────────────────────

    def _send(self) -> None:
        if self._is_typing:
            return
        text = self._input.toPlainText().strip()
        if not text:
            return

        self._input.clear()
        self._history.insert(0, text)
        self._hist_idx = -1

        if text.lower() in ("status", "jarvis status", "/status"):
            self._run_diagnostics(); return
        if text.lower() in ("/clear", "clear", "clear chat"):
            self._clear_chat(); return

        self._append_user(text)
        self._start_stream(text)

    def _start_stream(self, text: str) -> None:
        self._is_typing = True
        self._send_btn.setEnabled(False)
        self._stop_btn.setEnabled(True)
        self._status.showMessage("JARVIS is thinking…")
        self._append_assistant_start()

        self._worker = StreamWorker(self.agent, text)
        self._worker.token.connect(self._on_token)
        self._worker.finished.connect(self._on_done)
        self._worker.error.connect(self._on_error)
        self._worker.start()

    def _on_token(self, tok: str) -> None:
        if tok.startswith("\r"):
            msg = tok.strip()
            if msg:
                self._status.showMessage(msg)
            return
        # #9 Clear the status bar the moment real content starts streaming
        if not self._last_response:
            self._status.clearMessage()
        self._append_token(tok)

    def _on_done(self) -> None:
        self._is_typing = False
        self._send_btn.setEnabled(True)
        self._stop_btn.setEnabled(False)

        # #2 Replace streamed plain text with rendered markdown
        if self._last_response:
            self._replace_stream_with_markdown(self._last_response)

        self._append_assistant_end()
        self._update_status()

        if self.voice and getattr(self.voice, "is_available", False):
            resp = self._last_response
            if resp and len(resp) < 300:
                self.voice.speak(resp)

    def _on_error(self, msg: str) -> None:
        self._on_done()
        self._append_html(f'<p style="color:#ff6060;">⚠️ {html.escape(msg)}</p>')

    def _stop(self) -> None:
        """Cleanly signal the agent to stop — no hard thread kill."""
        self.agent.stop()
        # Give the thread up to 3 s to exit on its own before giving up
        if self._worker and self._worker.isRunning():
            self._worker.wait(3000)
        self._on_done()

    def _quick_send(self, text: str) -> None:
        self._tabs.setCurrentIndex(0)
        self._input.setPlainText(text)
        self._send()

    # ── Markdown rendering helpers ─────────────────────────────────────────

    def _append_assistant_start(self) -> None:
        """Insert the JARVIS label, then record the cursor position so we
        can later replace the streamed plain text with rendered HTML."""
        self._append_html(
            '<div style="margin:4px 0;">'
            '<span style="color:#40a040;font-weight:600;">JARVIS</span>'
            '<span style="color:#305030;font-size:11px;"> ──────────</span>'
            '</div>'
        )
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)

        # Store the character position just *before* streaming begins
        self._stream_start_pos = cursor.position()

        # Set a plain char format so insertText calls don't inherit stray HTML
        fmt = QTextCharFormat()
        fmt.setForeground(QColor("#e0e0e0"))
        fmt.setFont(QFont("Segoe UI", 13))
        cursor.setCharFormat(fmt)
        self._chat.setTextCursor(cursor)
        self._last_response = ""

    def _append_token(self, tok: str) -> None:
        """
        Append a raw token using insertText — preserves every space.
        (insertHtml collapses whitespace between successive calls.)
        """
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertText(tok)
        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()
        self._last_response += tok

    def _replace_stream_with_markdown(self, text: str) -> None:
        """
        #2 After streaming finishes, select the plain-text region that was
        inserted token-by-token and replace it with rendered markdown HTML.
        """
        doc    = self._chat.document()
        cursor = self._chat.textCursor()

        # Select from the start-of-stream position to end of document
        cursor.setPosition(self._stream_start_pos)
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)

        md_html = _render_markdown(text)
        cursor.insertHtml(md_html)

        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()

    def _append_assistant_end(self) -> None:
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.setCharFormat(QTextCharFormat())
        cursor.insertText("\n\n")
        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()

    def _append_user(self, text: str) -> None:
        escaped = html.escape(text).replace("\n", "<br>")
        self._append_html(
            f'<div style="margin:10px 0 4px 0;">'
            f'<span style="color:#6060ff;font-weight:600;">You</span>'
            f'<span style="color:#4040a0;font-size:11px;"> ──────────</span>'
            f'</div>'
            f'<div style="color:#d0d0e0;margin-bottom:14px;padding-left:4px;">'
            f'{escaped}</div>'
        )

    def _append_html(self, html_str: str) -> None:
        cursor = self._chat.textCursor()
        cursor.movePosition(QTextCursor.MoveOperation.End)
        cursor.insertHtml(html_str)
        self._chat.setTextCursor(cursor)
        self._chat.ensureCursorVisible()

    def _welcome_message(self) -> None:
        model     = self.config.fast_model
        ollama_ok = self.router and self.router.is_online()
        md_note   = "" if _HAS_MARKDOWN else (
            ' <span style="color:#806000;font-size:10px;">'
            '(install <code>markdown</code> for rich formatting)</span>'
        )
        status_line = (
            '<span style="color:#40a040;">● Ollama online</span>'
            if ollama_ok else
            '<span style="color:#ff8040;">● Ollama not running — '
            'start it with: <code>ollama serve</code></span>'
        )
        self._append_html(
            f'<div style="margin:16px 0 20px 0; padding:14px; '
            f'background:#13131e; border-radius:8px; border:1px solid #2a2a3a;">'
            f'<div style="color:#8080ff;font-size:16px;font-weight:700;letter-spacing:3px;">'
            f'J A R V I S v4</div>'
            f'<div style="color:#5050a0;font-size:11px;margin-top:4px;">'
            f'Local AI Assistant{md_note}</div>'
            f'<div style="margin-top:10px;font-size:12px;">{status_line}</div>'
            f'<div style="color:#404060;font-size:11px;margin-top:6px;">'
            f'Model: {html.escape(model)} · '
            f'Ctrl+Alt+J to show/hide · type <b>status</b> to run diagnostics'
            f'</div></div>'
        )

    # ── #7 Save chat ──────────────────────────────────────────────────────

    def _save_chat(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self, "Save Chat", "jarvis_chat.md", "Markdown (*.md);;Text (*.txt)"
        )
        if not path:
            return
        content = self._chat.toPlainText()
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._status.showMessage(f"Chat saved to {path}", 4000)
        except Exception as e:
            QMessageBox.warning(self, "Save failed", str(e))

    # ── History navigation ────────────────────────────────────────────────

    def _hist_prev(self) -> None:
        if not self._history:
            return
        self._hist_idx = min(self._hist_idx + 1, len(self._history) - 1)
        self._input.setPlainText(self._history[self._hist_idx])

    def _hist_next(self) -> None:
        if self._hist_idx <= 0:
            self._hist_idx = -1
            self._input.clear()
            return
        self._hist_idx -= 1
        self._input.setPlainText(self._history[self._hist_idx])

    # ── Browser tab ───────────────────────────────────────────────────────

    def _refresh_browser_status(self) -> None:
        try:
            from browser_tools import get_browser
            b = get_browser(self.config)
            if b.is_connected():
                self._browser_status.setText("● Connected")
                self._browser_status.setStyleSheet("color:#40a040; font-size:13px;")
            else:
                self._browser_status.setText("● Not connected")
                self._browser_status.setStyleSheet("color:#ff6060; font-size:13px;")
        except Exception:
            pass

    # ── Memory tab ────────────────────────────────────────────────────────

    def _refresh_memory(self) -> None:
        if not self.memory:
            self._mem_display.setPlainText("Memory engine not available.")
            return
        stats  = self.memory.stats()
        recent = self.memory.get_recent(20)
        lines  = [
            f"Total memories: {stats['total_memories']}",
            f"Session messages: {stats['session_messages']}",
            f"Semantic search: {'enabled' if stats['semantic'] else 'disabled'}",
            "",
            "─── Recent ─────────────────────────────────────",
        ]
        for m in recent:
            import datetime
            ts = datetime.datetime.fromtimestamp(m.timestamp).strftime("%m/%d %H:%M")
            lines.append(f"[{ts}] {m.content[:120]}…")
        self._mem_display.setPlainText("\n".join(lines))

    def _clear_memory(self) -> None:
        reply = QMessageBox.question(
            self, "Clear Memory",
            "Delete all stored memories? This cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes and self.memory:
            self.memory.clear_session()
            self._refresh_memory()

    # ── Toolbar actions ───────────────────────────────────────────────────

    def _open_settings(self) -> None:
        from settings_dialog import SettingsDialog
        dlg = SettingsDialog(self.config, self)
        dlg.settings_changed.connect(self._update_model_label)
        dlg.exec()

    def _run_diagnostics(self) -> None:
        self._append_assistant_start()
        from diagnostics import run_all, format_report
        report = format_report(run_all(self.config))
        self._append_token(report)
        self._on_done()
        self._send_btn.setEnabled(True)

    def _clear_chat(self) -> None:
        self._chat.clear()
        if self.memory:
            self.memory.clear_session()
        # Also clear the agent's rolling conversation history
        self.agent.clear_history()
        self._welcome_message()

    def _pick_pdf(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Open PDF", "", "PDF files (*.pdf)")
        if path:
            self._quick_send(f"summarize this pdf: {path}")

    def _confirm_dialog(self, message: str) -> bool:
        reply = QMessageBox.question(
            self, "JARVIS — Confirmation", message,
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        return reply == QMessageBox.StandardButton.Yes

    def _update_status(self) -> None:
        ollama = "✅ Ollama" if (self.router and self.router.is_online()) else "❌ Ollama offline"
        mem    = f"💾 {self.memory.stats()['total_memories']} memories" if self.memory else ""
        self._status.showMessage(f" {ollama}   {mem}   Ctrl+Alt+J to hide")

    def _update_model_label(self) -> None:
        self._model_lbl.setText(
            f"fast: {self.config.fast_model} · deep: {self.config.deep_model}")

    # ── #3 Warm-up ────────────────────────────────────────────────────────

    def _warmup(self) -> None:
        if self.router and self.router.is_online():
            self.router.warmup()

    # ── Hotkey / Tray / Voice / Lifecycle ─────────────────────────────────

    def _setup_hotkey(self) -> None:
        try:
            import keyboard
            hotkey_str = self.config.get("app.hotkey", "ctrl+alt+j")
            keyboard.add_hotkey(hotkey_str, self._toggle_visibility)
        except ImportError:
            logger.info("keyboard package not installed — global hotkey disabled")
        except Exception as e:
            logger.warning("Hotkey setup failed: %s", e)

    def _setup_tray(self) -> None:
        from tray_icon import TrayIcon
        self._tray = TrayIcon(self)
        self._tray.show_window.connect(self.show_and_raise)
        self._tray.open_settings.connect(self._open_settings)
        self._tray.quit_app.connect(self._quit)
        self._tray.show()

    def _setup_voice(self) -> None:
        if not self.voice or not getattr(self.voice, "is_available", False):
            return

        def on_wake(text):
            QTimer.singleShot(0, self.show_and_raise)

        self.voice.on_wake_word = on_wake
        self.voice.start_listening()

    def _toggle_visibility(self) -> None:
        if self.isVisible():
            self.hide()
        else:
            self.show_and_raise()

    def show_and_raise(self) -> None:
        self.show()
        self.raise_()
        self.activateWindow()
        self._input.setFocus()

    def closeEvent(self, event) -> None:
        if self.config.get("app.minimize_to_tray", True):
            event.ignore()
            self.hide()
            self._tray.notify("JARVIS", "Running in background. Double-click tray to show.")
        else:
            self._quit()

    def _quit(self) -> None:
        self.agent.stop()
        if self.voice:
            self.voice.stop_listening()
        if self.memory:
            self.memory.close()
        from PySide6.QtWidgets import QApplication
        QApplication.quit()
