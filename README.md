# ⬡ JARVIS v3 — Local AI Desktop Assistant

A fully local, offline AI assistant. No cloud. No subscriptions. Your data stays on your machine.

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/certifiedclaw/jarvis-v3-wip
cd jarvis-v3-wip

# 2. Setup (installs deps, creates venv, pulls Ollama model)
#    Windows:
setup.bat
#    Linux/Mac:
bash setup.sh

# 3. Run
#    Windows:
run.bat
#    Linux/Mac:
./run.sh
#    Direct:
python main.py
```

---

## 🔧 Ollama Setup (required)

```bash
# Install from https://ollama.com/download, then:
ollama serve            # start the server
ollama pull qwen3:8b   # fast everyday model (required)
ollama pull qwen3:14b  # deep reasoning (optional)
ollama pull llava:latest  # vision/screenshot analysis (optional)
```

---

## 🌐 Browser Control (Brave-first CDP)

Start Brave with the remote debugging flag:

```
# Windows shortcut — add to Target field:
brave.exe --remote-debugging-port=9222

# Or run directly:
"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222
```

Works with Chrome and Edge too. Then just ask JARVIS:
- *"pause the video"*, *"skip forward 30 seconds"*, *"mute"*, *"fullscreen"*
- *"list my open tabs"*, *"switch to the YouTube tab"*

---

## ✨ Features

| Feature | Details |
|---|---|
| 🧠 Smart routing | Fast model for chat, deep model for complex tasks |
| 📄 PDF Q&A | Summarize, extract tables, search in documents |
| 🖥️ Vision | Screenshot + Ollama llava — "what's on my screen?" |
| 🌐 Browser control | CDP-based, no Playwright needed |
| 💾 Semantic memory | SQLite + sentence-transformers |
| 📚 Local RAG | Index your Obsidian vault / docs folder |
| 🎙 Voice | Wake-word detection (Vosk) + TTS (pyttsx3) |
| 🔌 Plugins | Drop a .py into `plugins/` — auto-loaded |
| ⌨️ Global hotkey | Ctrl+Alt+J to show/hide anywhere |
| 🩺 Diagnostics | Type `status` in chat |

---

## ⌨️ Chat Commands

| Type this | Does this |
|---|---|
| `status` | Full system diagnostics |
| `/clear` | Clear chat history |
| `↑ / ↓` arrow keys | Navigate command history |
| `Enter` | Send message |
| `Shift+Enter` | New line |

---

## 🔌 Writing a Plugin

Drop a `.py` file in `plugins/`:

```python
PLUGIN_NAME = "weather"

def get_weather(city="London"):
    return f"Sunny in {city}!"

PLUGIN_TOOLS = {
    "get_weather": get_weather,
}
```

---

## 📁 Structure

```
jarvis-v3/
├── main.py              ← entry point
├── config.yaml          ← all settings
├── agent.py             ← ReAct planning loop
├── router.py            ← Ollama LLM interface
├── memory_engine.py     ← persistent memory
├── browser_tools.py     ← CDP browser control
├── file_tools.py
├── system_tools.py
├── web_tools.py
├── pdf_tools.py
├── vision_tools.py
├── voice_engine.py
├── rag.py               ← local RAG
├── plugins.py           ← plugin loader
├── diagnostics.py
├── themes.py
├── loading_screen.py
├── main_window.py       ← PySide6 chat UI
├── welcome_dialog.py
├── settings_dialog.py
├── tray_icon.py
├── plugins/             ← drop custom tools here
├── data/                ← gitignored (memory, screenshots, RAG index)
└── logs/                ← gitignored
```

---

## 🐛 Troubleshooting

**Ollama not connecting**
```
ollama serve
```

**Stuck on "Initializing…"** — this was a bug in earlier versions where `main.py` was missing. Fixed in v3 final.

**No browser control** — start browser with `--remote-debugging-port=9222`

**Voice not working** — install optional deps:
```
pip install pyttsx3 vosk sounddevice
```
Then download a Vosk model to `data/vosk-model-small-en-us-0.15/`

---

## License

MIT
