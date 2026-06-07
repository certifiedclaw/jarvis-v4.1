"""
main.py — JARVIS v3 Entry Point
Run: python main.py
"""
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)
os.chdir(_HERE)

from PySide6.QtWidgets import QApplication, QMessageBox
app = QApplication(sys.argv)
app.setApplicationName("JARVIS")
app.setApplicationVersion("3.0.0")
app.setQuitOnLastWindowClosed(False)

# Logging
import logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    handlers=[
        logging.FileHandler("logs/jarvis.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("main")
log.info("JARVIS v3 starting up")

# Config
from config import get_config
try:
    cfg = get_config()
except FileNotFoundError as e:
    QMessageBox.critical(None, "JARVIS — Config Error", str(e))
    sys.exit(1)

# Theme
import themes
themes.apply(app, cfg.theme)

# Dirs
for d in ("data", "logs", "data/screenshots", "data/rag_index", "plugins"):
    os.makedirs(d, exist_ok=True)

# Loading screen
from loading_screen import LoadingScreen
splash = LoadingScreen(cfg)

def on_init_done(ctx: dict) -> None:
    log.info("Init complete — launching main window")
    from main_window import MainWindow
    window = MainWindow(ctx)

    if cfg.is_first_run:
        from welcome_dialog import WelcomeDialog
        WelcomeDialog(cfg, voice=ctx.get("voice"), parent=window).exec()

    window.show()

splash.finished.connect(on_init_done)
splash.show()

log.info("Qt event loop starting")
sys.exit(app.exec())
