# ⬡ JARVIS v4.1 — Local AI Desktop Assistant

> A fully local, offline AI assistant powered by Ollama. No cloud. No subscriptions. Your data stays on your machine.

---

## ✨ What's New in v4.1

| Change | Details |
|--------|---------|
| 🧠 Conversation memory | Rolling 12-message history — JARVIS remembers earlier turns in the session |
| ⏹ Graceful stop | Stop button cleanly cancels generation without killing the thread |
| 🎬 Auto media-tab switch | Browser media commands auto-detect and switch to the active video tab |
| 🛡️ Dual safety layers | `safety.py` + `jarvis_safety.py` — tool-level confirmation + OSINT guardrails |
| ⏰ Task scheduler | Schedule recurring or one-shot tasks (`task_scheduler.py`) |
| 🔑 Hotkey commands | Configurable global shortcuts via `hotkey_commands.py` |
| 📦 Extra tools | Expanded utility belt in `extra_tools.py` |

---

## ⚡ Quick Start

```bash
# 1. Clone
git clone https://github.com/certifiedclaw/jarvis-v4.1
cd jarvis-v4.1

# 2. Setup (installs deps, creates venv, pulls Ollama model)
#    Windows:
setup.bat
#    Linux/Mac:
bash setup.sh

# 3. Run
#    Windows:
run.bat
#    Linux/Mac:
python main.py
```

---

## 🔧 Ollama Setup (required)

```bash
# Install from https://ollama.com/download, then:
ollama serve             # start the server
ollama pull qwen3:8b    # fast everyday model (required)
ollama pull qwen3:14b   # deep reasoning (optional)
ollama pull llava:latest # vision / screenshot analysis (optional)
```

The fast model handles planning and conversation. The deep model is routed automatically for complex multi-step tasks.

---

## 🌐 Browser Control (CDP)

Start your browser with the remote debugging flag before using browser commands:

```bash
# Windows — add to the browser shortcut Target field:
brave.exe --remote-debugging-port=9222

# Or run directly:
"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe" --remote-debugging-port=9222
```

Works with Brave, Chrome, and Edge. Then ask JARVIS naturally:

- *"pause the video"*, *"mute"*, *"skip forward 30 seconds"*, *"fullscreen"*
- *"list my open tabs"*, *"switch to the YouTube tab"*

> **v4.1:** JARVIS now automatically detects which tab has a playing video and switches to it before executing media commands.

---

## 🛠️ Features

| Feature | Details |
|---------|---------|
| 🧠 Smart routing | Fast model for chat, deep model for complex reasoning |
| 💬 Conversation history | Remembers the last 6 turns (configurable) |
| 📄 PDF Q&A | Summarize, extract tables, search within documents |
| 🖥️ Vision | Screenshot + `llava` — *"what's on my screen?"* |
| 🌐 Browser control | CDP-based, no Playwright needed |
| 💾 Semantic memory | SQLite + sentence-transformers for persistent recall |
| 📚 Local RAG | Index your Obsidian vault or any docs folder |
| 🔍 OSINT toolkit | WHOIS, DNS, subdomain enum, breach checks, port scan, dorks, and more |
| 🎙️ Voice | Wake-word detection (Vosk) + TTS (pyttsx3) |
| 🔌 Plugins | Drop a `.py` into `plugins/` — auto-loaded at startup |
| ⌨️ Global hotkey | `Ctrl+Alt+J` to show/hide from anywhere |
| ⏰ Task scheduler | Schedule one-shot or recurring tasks |
| 🩺 Diagnostics | Type `status` in chat for a full system report |

---

## ⌨️ Chat Commands

| Command | Action |
|---------|--------|
| `status` | Full system diagnostics |
| `/clear` | Clear chat history (also resets conversation memory) |
| `↑ / ↓` arrow keys | Navigate command history |
| `Enter` | Send message |
| `Shift+Enter` | New line |

---

## 🔌 Writing a Plugin

Drop a `.py` file in the `plugins/` folder — JARVIS auto-loads it on startup:

```python
PLUGIN_NAME = "weather"

def get_weather(city="London"):
    return f"Sunny in {city}!"

PLUGIN_TOOLS = {
    "get_weather": get_weather,
}
```

JARVIS exposes your tool as `plugin.get_weather` in its planner automatically.

---

## 📁 Project Structure

```
jarvis-v4.1/
├── main.py               ← entry point
├── config.yaml           ← all settings
├── agent.py              ← ReAct planning loop + conversation history
├── router.py             ← Ollama LLM interface (fast / deep model routing)
├── memory_engine.py      ← semantic memory (SQLite + embeddings)
├── rag.py                ← local RAG (Obsidian / docs indexing)
├── smart_context.py      ← context injection helpers
│
├── browser_tools.py      ← CDP browser control
├── file_tools.py
├── system_tools.py
├── web_tools.py
├── pdf_tools.py
├── vision_tools.py
├── osint_tools.py        ← WHOIS, DNS, breach checks, dorks, port scan …
├── extra_tools.py        ← additional utility tools
│
├── voice_engine.py       ← wake-word + TTS
├── hotkey_commands.py    ← global hotkey bindings
├── task_scheduler.py     ← scheduled / recurring tasks
│
├── safety.py             ← tool confirmation layer
├── jarvis_safety.py      ← OSINT-aware safety guardrails
├── plugins.py            ← plugin loader
├── diagnostics.py
│
├── main_window.py        ← PySide6 chat UI
├── main.py (Main)        ← compiled / alternate entry
├── welcome_dialog.py
├── settings_dialog.py
├── themes.py
├── loading_screen.py
├── tray_icon.py
├── logger.py
├── config.py
│
├── setup.bat / setup.sh  ← one-shot environment setup
├── run.bat               ← Windows launcher
├── requirements.txt
│
├── plugins/              ← drop custom tools here (gitignored)
├── data/                 ← memory, screenshots, RAG index (gitignored)
└── logs/                 ← runtime logs (gitignored)
```

---

## 🐛 Troubleshooting

**Ollama not connecting**
```bash
ollama serve
```

**Stuck on "Initializing…"**
Make sure `main.py` is present and Ollama is running. Run `status` in chat for a diagnostic report.

**No browser control**
Start your browser with `--remote-debugging-port=9222` (see [Browser Control](#-browser-control-cdp)).

**Voice not working**
Install the optional audio dependencies:
```bash
pip install pyttsx3 vosk sounddevice
```
Then download a Vosk model and place it at:
`data/vosk-model-small-en-us-0.15/`
Download from: https://alphacephei.com/vosk/models

**OSINT tools failing**
Some OSINT functions hit external APIs. Check your network connection and review `osint_tools.py` for any API key requirements.

---

## ⚙️ Configuration

Edit `config.yaml` to tune behavior:

```yaml
agent:
  max_tool_rounds: 8      # max tool calls per request
  max_replan: 2           # retries on tool failure

models:
  fast_model: qwen3:8b    # used for planning + conversation
  deep_model: qwen3:14b   # used for complex reasoning

memory:
  enabled: true
  window: 12              # rolling conversation turns to keep
```

---

## 🗺️ Roadmap / Ideas

- [ ] Web UI / REST API mode for headless deployment
- [ ] MCP (Model Context Protocol) server support for external tool integration
- [ ] Multi-agent mode — spawn sub-agents for parallel tasks
- [ ] Plugin marketplace / registry
- [ ] Android/iOS companion app via local network
- [ ] Fine-tuned Ollama model tailored to JARVIS tool use

---

## 📄 License

MIT — see [LICENSE](LICENSE)
