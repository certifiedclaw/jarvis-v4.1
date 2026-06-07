"""
settings_dialog.py — JARVIS v3 Settings UI
"""
from __future__ import annotations
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QTabWidget, QWidget,
    QLabel, QLineEdit, QComboBox, QCheckBox, QPushButton,
    QGroupBox, QFormLayout, QSpinBox, QDoubleSpinBox,
    QTextEdit, QScrollArea, QFrame, QSizePolicy
)


class SettingsDialog(QDialog):
    settings_changed = Signal()

    def __init__(self, config, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.setWindowTitle("JARVIS Settings")
        self.setMinimumSize(600, 520)
        self._build()
        self._load_values()

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(20, 20, 20, 16)
        root.setSpacing(12)

        hdr = QLabel("Settings")
        hdr.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
        hdr.setStyleSheet("color:#8080ff;")
        root.addWidget(hdr)

        tabs = QTabWidget()
        tabs.addTab(self._tab_llm(),      "🧠 LLM")
        tabs.addTab(self._tab_ui(),       "🎨 UI")
        tabs.addTab(self._tab_browser(),  "🌐 Browser")
        tabs.addTab(self._tab_voice(),    "🎙 Voice")
        tabs.addTab(self._tab_safety(),   "🛡 Safety")
        tabs.addTab(self._tab_about(),    "ℹ About")
        root.addWidget(tabs)

        # Buttons
        btn_row = QHBoxLayout()
        btn_row.addStretch()
        cancel = QPushButton("Cancel")
        cancel.clicked.connect(self.reject)
        save = QPushButton("Save & Apply")
        save.setObjectName("send")
        save.clicked.connect(self._save)
        btn_row.addWidget(cancel)
        btn_row.addWidget(save)
        root.addLayout(btn_row)

    # ── Tabs ──────────────────────────────────────────────────────────────────
    def _tab_llm(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)

        self._ollama_url  = QLineEdit()
        self._fast_model  = QLineEdit()
        self._deep_model  = QLineEdit()
        self._vision_model= QLineEdit()
        self._temperature = QDoubleSpinBox()
        self._temperature.setRange(0.0, 2.0)
        self._temperature.setSingleStep(0.05)
        self._num_ctx     = QSpinBox()
        self._num_ctx.setRange(512, 131072)
        self._num_ctx.setSingleStep(512)
        self._auto_route  = QCheckBox("Auto-route to fast/deep model based on complexity")

        f.addRow("Ollama URL:",       self._ollama_url)
        f.addRow("Fast model:",       self._fast_model)
        f.addRow("Deep model:",       self._deep_model)
        f.addRow("Vision model:",     self._vision_model)
        f.addRow("Temperature:",      self._temperature)
        f.addRow("Context window:",   self._num_ctx)
        f.addRow("",                  self._auto_route)

        note = QLabel("Models must be pulled via  ollama pull <name>")
        note.setStyleSheet("color:#5050a0; font-size:11px;")
        f.addRow("", note)
        return w

    def _tab_ui(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)

        self._theme   = QComboBox()
        self._theme.addItems(["dark", "light"])
        self._hotkey  = QLineEdit()
        self._min_tray= QCheckBox("Minimize to system tray on close")

        f.addRow("Theme:",         self._theme)
        f.addRow("Global hotkey:", self._hotkey)
        f.addRow("",               self._min_tray)

        note = QLabel("Theme change takes effect on next restart.")
        note.setStyleSheet("color:#5050a0; font-size:11px;")
        f.addRow("", note)
        return w

    def _tab_browser(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)

        self._cdp_port = QSpinBox()
        self._cdp_port.setRange(1024, 65535)
        self._auto_connect = QCheckBox("Auto-connect on startup")

        f.addRow("CDP port:",    self._cdp_port)
        f.addRow("",             self._auto_connect)

        note = QLabel(
            "Start Brave with:   brave.exe --remote-debugging-port=9222\n"
            "Or add --remote-debugging-port=9222 to the browser shortcut.")
        note.setStyleSheet("color:#5050a0; font-size:11px;")
        note.setWordWrap(True)
        f.addRow("How to enable:", note)
        return w

    def _tab_voice(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)

        self._voice_enabled = QCheckBox("Enable voice (requires vosk + sounddevice)")
        self._tts_rate = QSpinBox()
        self._tts_rate.setRange(50, 400)
        self._wake_words = QLineEdit()

        f.addRow("",             self._voice_enabled)
        f.addRow("TTS rate:",    self._tts_rate)
        f.addRow("Wake words (comma-separated):", self._wake_words)

        note = QLabel("pip install vosk sounddevice pyttsx3")
        note.setStyleSheet("color:#5050a0; font-size:11px; font-family:monospace;")
        f.addRow("Install:", note)
        return w

    def _tab_safety(self) -> QWidget:
        w = QWidget()
        f = QFormLayout(w)
        f.setSpacing(12)
        f.setContentsMargins(16, 16, 16, 16)

        self._confirm_delete = QCheckBox("Confirm before delete")
        self._confirm_shell  = QCheckBox("Confirm before shell commands")
        self._confirm_write  = QCheckBox("Confirm before write_file")

        f.addRow("", self._confirm_delete)
        f.addRow("", self._confirm_shell)
        f.addRow("", self._confirm_write)
        return w

    def _tab_about(self) -> QWidget:
        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setContentsMargins(24, 24, 24, 24)
        lay.setSpacing(12)

        title = QLabel("JARVIS v3")
        title.setFont(QFont("Segoe UI", 18, QFont.Weight.Bold))
        title.setStyleSheet("color:#8080ff;")
        lay.addWidget(title)

        about = QLabel(
            "A fully local, offline AI desktop assistant.\n"
            "Powered by Ollama · Built with PySide6.\n\n"
            "github.com/certifiedclaw/jarvis-v3\n\n"
            "Type  status  in the chat to run a full diagnostics check."
        )
        about.setStyleSheet("color:#a0a0c0; font-size:13px; line-height:1.6;")
        about.setWordWrap(True)
        lay.addWidget(about)
        lay.addStretch()
        return w

    # ── Load / Save ───────────────────────────────────────────────────────────
    def _load_values(self) -> None:
        c = self.config
        self._ollama_url.setText(c.get("llm.ollama_url", "http://localhost:11434"))
        self._fast_model.setText(c.get("llm.fast_model", "qwen3:8b"))
        self._deep_model.setText(c.get("llm.deep_model", "qwen3:14b"))
        self._vision_model.setText(c.get("llm.vision_model", "llava:latest"))
        self._temperature.setValue(float(c.get("llm.temperature", 0.7)))
        self._num_ctx.setValue(int(c.get("llm.num_ctx", 8192)))
        self._auto_route.setChecked(bool(c.get("llm.auto_route", True)))

        idx = 0 if c.theme == "dark" else 1
        self._theme.setCurrentIndex(idx)
        self._hotkey.setText(c.get("app.hotkey", "ctrl+alt+j"))
        self._min_tray.setChecked(bool(c.get("app.minimize_to_tray", True)))

        self._cdp_port.setValue(int(c.get("browser.cdp_port", 9222)))
        self._auto_connect.setChecked(bool(c.get("browser.auto_connect", True)))

        self._voice_enabled.setChecked(bool(c.get("voice.enabled", False)))
        self._tts_rate.setValue(int(c.get("voice.tts_rate", 175)))
        self._wake_words.setText(", ".join(c.get("voice.wake_words", ["jarvis"])))

        confirms = set(c.confirm_on)
        self._confirm_delete.setChecked("delete" in confirms)
        self._confirm_shell.setChecked("shell" in confirms)
        self._confirm_write.setChecked("write_file" in confirms)

    def _save(self) -> None:
        c = self.config
        c.set("llm.ollama_url",    self._ollama_url.text().strip())
        c.set("llm.fast_model",    self._fast_model.text().strip())
        c.set("llm.deep_model",    self._deep_model.text().strip())
        c.set("llm.vision_model",  self._vision_model.text().strip())
        c.set("llm.temperature",   self._temperature.value())
        c.set("llm.num_ctx",       self._num_ctx.value())
        c.set("llm.auto_route",    self._auto_route.isChecked())
        c.set("app.theme",         self._theme.currentText())
        c.set("app.hotkey",        self._hotkey.text().strip())
        c.set("app.minimize_to_tray", self._min_tray.isChecked())
        c.set("browser.cdp_port",  self._cdp_port.value())
        c.set("browser.auto_connect", self._auto_connect.isChecked())
        c.set("voice.enabled",     self._voice_enabled.isChecked())
        c.set("voice.tts_rate",    self._tts_rate.value())
        wws = [w.strip() for w in self._wake_words.text().split(",") if w.strip()]
        c.set("voice.wake_words",  wws)
        confirms = []
        if self._confirm_delete.isChecked(): confirms.append("delete")
        if self._confirm_shell.isChecked():  confirms.append("shell")
        if self._confirm_write.isChecked():  confirms.append("write_file")
        c.set("safety.confirm_on", confirms)
        c.save()
        self.settings_changed.emit()
        self.accept()
