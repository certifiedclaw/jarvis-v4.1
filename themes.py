"""
themes.py — JARVIS v3 UI Themes
"""
DARK = """
QWidget { background:#0f0f14; color:#e0e0e0; font-family:'Segoe UI','Inter',sans-serif; font-size:13px; }
QMainWindow,QDialog { background:#0f0f14; }
QTextEdit#chat { background:#13131a; border:1px solid #2a2a3a; border-radius:8px; padding:12px; color:#e0e0e0; }
QTextEdit#input { background:#1c1c28; border:1px solid #3a3a5a; border-radius:8px; padding:8px 12px; color:#f0f0f0; }
QTextEdit#input:focus { border:1px solid #5a5aff; }
QPushButton { background:#2a2a40; border:1px solid #4a4a6a; border-radius:6px; padding:6px 16px; color:#e0e0e0; }
QPushButton:hover { background:#3a3a5a; }
QPushButton:pressed { background:#1a1a30; }
QPushButton#send { background:#3a3aff; border:none; color:#fff; font-weight:600; padding:8px 22px; border-radius:8px; }
QPushButton#send:hover { background:#5555ff; }
QPushButton#send:pressed { background:#2222cc; }
QPushButton#danger { background:#3a1a1a; border:1px solid #6a2a2a; color:#ff8080; }
QPushButton#danger:hover { background:#4a2020; }
QTabBar::tab { background:#1c1c28; color:#a0a0c0; padding:8px 20px; border:none; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#fff; border-bottom:2px solid #5a5aff; background:#0f0f14; }
QTabBar::tab:hover { color:#d0d0f0; background:#1a1a24; }
QTabWidget::pane { border:1px solid #2a2a3a; border-radius:8px; background:#13131a; }
QScrollBar:vertical { background:#13131a; width:8px; border:none; border-radius:4px; }
QScrollBar::handle:vertical { background:#3a3a5a; border-radius:4px; min-height:20px; }
QScrollBar::handle:vertical:hover { background:#5a5a7a; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QStatusBar { background:#0a0a10; color:#6060a0; font-size:11px; border-top:1px solid #1a1a2a; }
QStatusBar::item { border:none; }
QLabel { background:transparent; }
QLabel#title { color:#8080ff; font-size:20px; font-weight:700; letter-spacing:3px; }
QLabel#subtitle { color:#5050a0; font-size:11px; }
QLineEdit { background:#1c1c28; border:1px solid #3a3a5a; border-radius:6px; padding:6px 10px; color:#f0f0f0; }
QLineEdit:focus { border:1px solid #5a5aff; }
QComboBox { background:#1c1c28; border:1px solid #3a3a5a; border-radius:6px; padding:5px 10px; color:#e0e0e0; }
QComboBox::drop-down { border:none; }
QComboBox QAbstractItemView { background:#1c1c28; border:1px solid #3a3a5a; selection-background-color:#3a3aff55; color:#e0e0e0; }
QCheckBox { spacing:8px; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #4a4a6a; border-radius:4px; background:#1c1c28; }
QCheckBox::indicator:checked { background:#5a5aff; border-color:#5a5aff; }
QSplitter::handle { background:#2a2a3a; }
QToolTip { background:#1c1c28; color:#e0e0e0; border:1px solid #4a4a6a; padding:4px 8px; border-radius:4px; }
QGroupBox { border:1px solid #2a2a3a; border-radius:8px; margin-top:12px; padding-top:8px; }
QGroupBox::title { color:#8080ff; padding:0 8px; }
QSlider::groove:horizontal { background:#2a2a3a; height:4px; border-radius:2px; }
QSlider::handle:horizontal { background:#5a5aff; width:14px; height:14px; margin:-5px 0; border-radius:7px; }
"""

LIGHT = """
QWidget { background:#f5f5fa; color:#1a1a2e; font-family:'Segoe UI','Inter',sans-serif; font-size:13px; }
QMainWindow,QDialog { background:#f5f5fa; }
QTextEdit#chat { background:#fff; border:1px solid #d0d0e0; border-radius:8px; padding:12px; color:#1a1a2e; }
QTextEdit#input { background:#fff; border:1px solid #c0c0d8; border-radius:8px; padding:8px 12px; color:#1a1a2e; }
QTextEdit#input:focus { border:1px solid #5a5aff; }
QPushButton { background:#e8e8f5; border:1px solid #c0c0d8; border-radius:6px; padding:6px 16px; color:#1a1a2e; }
QPushButton:hover { background:#d8d8f0; }
QPushButton#send { background:#4444ee; border:none; color:#fff; font-weight:600; padding:8px 22px; border-radius:8px; }
QPushButton#send:hover { background:#5555ff; }
QPushButton#danger { background:#fff0f0; border:1px solid #ffaaaa; color:#cc0000; }
QTabBar::tab { background:#eaeaf5; color:#5555aa; padding:8px 20px; border:none; border-bottom:2px solid transparent; }
QTabBar::tab:selected { color:#1a1a2e; border-bottom:2px solid #5a5aff; background:#f5f5fa; }
QTabWidget::pane { border:1px solid #d0d0e8; border-radius:8px; background:#fff; }
QScrollBar:vertical { background:#eaeaf5; width:8px; border-radius:4px; }
QScrollBar::handle:vertical { background:#c0c0d8; border-radius:4px; }
QScrollBar::add-line:vertical,QScrollBar::sub-line:vertical { height:0; }
QStatusBar { background:#eaeaf5; color:#7070a0; font-size:11px; }
QLabel { background:transparent; }
QLabel#title { color:#4444ee; font-size:20px; font-weight:700; letter-spacing:3px; }
QLabel#subtitle { color:#7070a0; font-size:11px; }
QLineEdit { background:#fff; border:1px solid #c0c0d8; border-radius:6px; padding:6px 10px; color:#1a1a2e; }
QComboBox { background:#fff; border:1px solid #c0c0d8; border-radius:6px; padding:5px 10px; color:#1a1a2e; }
QCheckBox::indicator { width:16px; height:16px; border:1px solid #a0a0c0; border-radius:4px; background:#fff; }
QCheckBox::indicator:checked { background:#5a5aff; border-color:#5a5aff; }
QGroupBox { border:1px solid #d0d0e0; border-radius:8px; margin-top:12px; padding-top:8px; }
QGroupBox::title { color:#4444ee; padding:0 8px; }
"""


def apply(app, theme: str = "dark") -> None:
    app.setStyleSheet(DARK if theme.lower() == "dark" else LIGHT)


def get_qss(theme: str = "dark") -> str:
    return DARK if theme.lower() == "dark" else LIGHT
