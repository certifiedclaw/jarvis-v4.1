"""
welcome_dialog.py — JARVIS v3 First-Run Welcome
Shows once. "Don't show again" sets app.first_run=false in config.
"""
from __future__ import annotations
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QFont
from PySide6.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                                QPushButton, QCheckBox, QFrame)


class WelcomeDialog(QDialog):
    def __init__(self, config, voice=None, parent=None) -> None:
        super().__init__(parent)
        self.config = config
        self.voice  = voice
        self.setWindowTitle("Welcome to JARVIS v3")
        self.setFixedSize(560, 480)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self._build()
        # Speak greeting after a short delay
        QTimer.singleShot(600, self._greet)

    def _build(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)

        # Header
        header = QFrame()
        header.setFixedHeight(120)
        header.setStyleSheet("background:#1a1a30; border-radius:0px;")
        hl = QVBoxLayout(header)
        hl.setAlignment(Qt.AlignmentFlag.AlignCenter)

        title = QLabel("J A R V I S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 28, QFont.Weight.Bold))
        title.setStyleSheet("color:#6060ff; letter-spacing:8px; background:transparent;")
        hl.addWidget(title)

        sub = QLabel("v3.0.0  ·  Your local AI assistant")
        sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sub.setStyleSheet("color:#4040a0; font-size:12px; background:transparent;")
        hl.addWidget(sub)
        root.addWidget(header)

        # Body
        body = QVBoxLayout()
        body.setContentsMargins(36, 24, 36, 16)
        body.setSpacing(12)

        greeting = QLabel("Hello! I'm JARVIS v3 — a fully local AI assistant\nthat runs entirely on your machine.")
        greeting.setAlignment(Qt.AlignmentFlag.AlignCenter)
        greeting.setStyleSheet("color:#c0c0e0; font-size:14px;")
        greeting.setWordWrap(True)
        body.addWidget(greeting)

        # Feature bullets
        features = [
            ("🧠", "Smart LLM routing — fast or deep model based on complexity"),
            ("🌐", "Browser control — play/pause media, switch tabs, navigate"),
            ("📄", "PDF & document Q&A — summarise, search, extract tables"),
            ("🖥️", "Screenshot analysis — see what's on your screen"),
            ("🔌", "Plugin system — drop a .py file in plugins/ to extend me"),
        ]
        for icon, text in features:
            row = QHBoxLayout()
            row.setSpacing(10)
            il = QLabel(icon)
            il.setFixedWidth(28)
            il.setStyleSheet("font-size:18px; background:transparent;")
            tl = QLabel(text)
            tl.setStyleSheet("color:#a0a0c0; font-size:12px; background:transparent;")
            tl.setWordWrap(True)
            row.addWidget(il)
            row.addWidget(tl, 1)
            body.addLayout(row)

        body.addSpacing(8)

        hotkey_lbl = QLabel("💡  Press  Ctrl+Alt+J  anywhere to show/hide JARVIS")
        hotkey_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        hotkey_lbl.setStyleSheet(
            "color:#6060ff; font-size:12px; background:#1a1a2e; "
            "border-radius:6px; padding:8px; border:1px solid #2a2a4a;")
        body.addWidget(hotkey_lbl)

        root.addLayout(body)

        # Footer
        footer = QHBoxLayout()
        footer.setContentsMargins(36, 8, 36, 20)

        self._no_show = QCheckBox("Don't show this again")
        self._no_show.setStyleSheet("color:#6060a0; font-size:12px;")
        footer.addWidget(self._no_show)
        footer.addStretch()

        btn = QPushButton("  Let's go!  →")
        btn.setObjectName("send")
        btn.setFixedHeight(38)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.clicked.connect(self._accept)
        footer.addWidget(btn)
        root.addLayout(footer)

    def _greet(self) -> None:
        if self.voice and self.voice.is_available:
            self.voice.speak(
                "Hello! I'm JARVIS version 3. I'm your local AI assistant. "
                "Say 'Hey JARVIS' or press Control Alt J to talk to me anytime.")

    def _accept(self) -> None:
        if self._no_show.isChecked():
            self.config.mark_first_run_complete()
        self.accept()
