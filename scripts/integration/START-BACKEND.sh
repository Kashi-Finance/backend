#!/bin/zsh
# Start the backend server for integration testing

cd "$(dirname "$0")/../.."

echo "🚀 Starting Kashi Backend (http://localhost:8000)"
echo ""
echo "This will start the FastAPI server with hot-reload enabled."
echo "Press Ctrl+C to stop."
echo ""

# Prefer python3 when available, fallback to python
if command -v python3 >/dev/null 2>&1; then
    PY_CMD=python3
elif command -v python >/dev/null 2>&1; then
    PY_CMD=python
else
    echo "❌ Python is not installed or not on PATH. Please install Python 3 and try again."
    exit 2
fi

# Check if the module is importable first
${PY_CMD} -c "import backend.main" 2>/dev/null || {
        echo "❌ Cannot import backend module. Make sure you're in the repository root (so 'backend' package is on PYTHONPATH) and that dependencies are installed."
        echo "   Run: cd \"$(dirname \"$0\")/../..\" && ${PY_CMD} -c 'import backend.main'"
        exit 1
}

# Start the server
${PY_CMD} -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
