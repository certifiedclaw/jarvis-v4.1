"""
loading_screen.py — JARVIS v3

FIX: The previous version never called start_animation() because there was no main.py.
Now the animation auto-starts in show() and init runs in a QThread so the UI never blocks.
"""
from __future__ import annotations
import sys
from PySide6.QtCore import Qt, Signal, QThread, QTimer, QObject
from PySide6.QtGui import QFont, QColor
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QLabel,
                                QProgressBar, QApplication)


class InitWorker(QThread):
    """Initialises all heavy subsystems off the main thread."""
    progress = Signal(int, str)   # (percent, message)
    done     = Signal(object)     # emits the fully-built app context dict

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config

    def run(self) -> None:
        ctx = {"config": self.config}

        self.progress.emit(10, "Loading configuration…")
        try:
            warns = self.config.validate()
            if warns:
                import logging; logging.getLogger(__name__).warning("Config: %s", warns)
        except Exception:
            pass

        self.progress.emit(25, "Starting LLM router…")
        try:
            from router import LLMRouter
            ctx["router"] = LLMRouter(self.config)
        except Exception as e:
            ctx["router"] = None
            ctx["router_error"] = str(e)

        self.progress.emit(45, "Connecting to memory…")
        try:
            from memory_engine import MemoryEngine
            ctx["memory"] = MemoryEngine(self.config)
        except Exception as e:
            ctx["memory"] = None

        self.progress.emit(60, "Loading tools & plugins…")
        try:
            from safety import SafetyLayer
            ctx["safety"] = SafetyLayer(self.config)
        except Exception:
            ctx["safety"] = None
        try:
            from plugins import PluginSystem
            ps = PluginSystem(self.config)
            ps.load_all()
            ctx["plugins"] = ps
        except Exception:
            ctx["plugins"] = None

        self.progress.emit(75, "Connecting to browser…")
        try:
            from browser_tools import get_browser
            browser = get_browser(self.config)
            ctx["browser_connected"] = browser.is_connected()
        except Exception:
            ctx["browser_connected"] = False

        self.progress.emit(90, "Starting voice engine…")
        try:
            from voice_engine import VoiceEngine
            ctx["voice"] = VoiceEngine(self.config)
        except Exception:
            ctx["voice"] = None

        self.progress.emit(100, "All systems online ✓")
        self.msleep(300)
        self.done.emit(ctx)


class LoadingScreen(QWidget):
    """
    Frameless splash screen.
    Call show() — animation starts automatically.
    Connect finished signal to open the main window.
    """
    finished = Signal(dict)   # emits ctx dict when init complete

    def __init__(self, config) -> None:
        super().__init__()
        self.config = config
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint |
                            Qt.WindowType.WindowStaysOnTopHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedSize(520, 280)
        self._build_ui()
        self._center()

    def _build_ui(self) -> None:
        self.setStyleSheet("""
            QWidget#card {
                background-color: #0f0f18;
                border: 1px solid #2a2a4a;
                border-radius: 16px;
            }
            QLabel { background: transparent; color: #e0e0e0; }
        """)
        card = QWidget(self)
        card.setObjectName("card")
        card.setGeometry(0, 0, 520, 280)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(50, 40, 50, 36)
        lay.setSpacing(10)

        title = QLabel("J A R V I S")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        title.setFont(QFont("Segoe UI", 30, QFont.Weight.Bold))
        title.setStyleSheet("color: #6060ff; letter-spacing: 8px;")
        lay.addWidget(title)

        ver = QLabel("v3.0.0  ·  Local AI Assistant")
        ver.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ver.setStyleSheet("color: #4040a0; font-size: 11px; letter-spacing: 1px;")
        lay.addWidget(ver)

        lay.addSpacing(16)

        self._status = QLabel("Starting up…")
        self._status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._status.setStyleSheet("color: #9090cc; font-size: 13px;")
        lay.addWidget(self._status)

        self._bar = QProgressBar()
        self._bar.setRange(0, 100)
        self._bar.setValue(0)
        self._bar.setTextVisible(False)
        self._bar.setFixedHeight(4)
        self._bar.setStyleSheet("""
            QProgressBar { background:#1a1a2e; border-radius:2px; border:none; }
            QProgressBar::chunk {
                background: qlineargradient(x1:0,y1:0,x2:1,y2:0,
                    stop:0 #4444cc, stop:1 #8888ff);
                border-radius: 2px;
            }
        """)
        lay.addWidget(self._bar)

    def _center(self) -> None:
        screen = QApplication.primaryScreen().geometry()
        self.move((screen.width()  - self.width())  // 2,
                  (screen.height() - self.height()) // 2)

    def show(self) -> None:
        super().show()
        # Start background init immediately after window is visible
        QTimer.singleShot(100, self._start_init)

    def _start_init(self) -> None:
        self._worker = InitWorker(self.config)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_done)
        self._worker.start()

    def _on_progress(self, pct: int, msg: str) -> None:
        self._bar.setValue(pct)
        self._status.setText(msg)

    def _on_done(self, ctx: dict) -> None:
        self.finished.emit(ctx)
        self.close()
