"""
tray_icon.py — JARVIS v3 System Tray Icon
"""
from __future__ import annotations
from PySide6.QtCore import QObject, Signal
from PySide6.QtGui import QIcon, QPixmap, QPainter, QColor, QFont, QAction
from PySide6.QtWidgets import QSystemTrayIcon, QMenu, QApplication


def _make_icon(color: str = "#6060ff") -> QIcon:
    """Generate a small 'J' icon programmatically — no image file needed."""
    px = QPixmap(32, 32)
    px.fill(QColor(0, 0, 0, 0))
    p = QPainter(px)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    p.setBrush(QColor(color))
    p.setPen(QColor(0, 0, 0, 0))
    p.drawEllipse(0, 0, 32, 32)
    p.setPen(QColor("#ffffff"))
    p.setFont(QFont("Segoe UI", 16, QFont.Weight.Bold))
    p.drawText(px.rect(), 0x84, "J")  # 0x84 = AlignCenter
    p.end()
    return QIcon(px)


class TrayIcon(QObject):
    show_window   = Signal()
    hide_window   = Signal()
    quit_app      = Signal()
    open_settings = Signal()

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._tray = QSystemTrayIcon(_make_icon(), parent)
        self._tray.setToolTip("JARVIS v3  —  Local AI Assistant")

        menu = QMenu()
        show_act = QAction("Show JARVIS", menu)
        show_act.triggered.connect(self.show_window)
        menu.addAction(show_act)

        settings_act = QAction("Settings…", menu)
        settings_act.triggered.connect(self.open_settings)
        menu.addAction(settings_act)

        menu.addSeparator()

        quit_act = QAction("Quit", menu)
        quit_act.triggered.connect(self.quit_app)
        menu.addAction(quit_act)

        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_activated)

    def show(self) -> None:
        self._tray.show()

    def hide(self) -> None:
        self._tray.hide()

    def notify(self, title: str, msg: str) -> None:
        self._tray.showMessage(title, msg, QSystemTrayIcon.MessageIcon.Information, 3000)

    def set_status(self, working: bool) -> None:
        color = "#ffaa00" if working else "#6060ff"
        self._tray.setIcon(_make_icon(color))

    def _on_activated(self, reason) -> None:
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self.show_window.emit()
