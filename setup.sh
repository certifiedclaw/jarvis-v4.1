#!/usr/bin/env bash
set -e
cd "$(dirname "$0")"

echo ""
echo "  ======================================"
echo "    J A R V I S  v3  —  Setup"
echo "  ======================================"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
    echo "  [ERROR] python3 not found. Install Python 3.10+."
    exit 1
fi
PYVER=$(python3 --version 2>&1 | awk '{print $2}')
echo "  [OK] Python $PYVER"

# Venv
if [ ! -d ".venv" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv
fi
echo "  [OK] Virtual environment ready"

# shellcheck disable=SC1091
source .venv/bin/activate

echo "  Installing dependencies..."
pip install --upgrade pip -q
pip install -r requirements.txt -q

# Dirs
mkdir -p data logs plugins data/screenshots data/rag_index

# Ollama check
if command -v ollama &>/dev/null; then
    echo "  [OK] Ollama found"
    echo "  Pulling default model (qwen3:8b)..."
    ollama pull qwen3:8b
else
    echo ""
    echo "  [NOTICE] Ollama not found."
    echo "  Install from: https://ollama.com/download"
    echo "  Then run: ollama pull qwen3:8b"
fi

# run.sh shortcut
cat > run.sh <<'EOF'
#!/usr/bin/env bash
cd "$(dirname "$0")"
source .venv/bin/activate
python main.py "$@"
EOF
chmod +x run.sh

echo ""
echo "  ======================================"
echo "    Setup complete!"
echo "  ======================================"
echo ""
echo "  To run JARVIS:  ./run.sh"
echo ""
