#!/bin/zsh
# Start the backend server for integration testing

cd "$(dirname "$0")/../.."

echo "🚀 Starting Kashi Backend (http://localhost:8000)"
echo ""
echo "This will start the FastAPI server with hot-reload enabled."
echo "Press Ctrl+C to stop."
echo ""

# Check if the module is importable first
python -c "import backend.main" 2>/dev/null || {
    echo "❌ Cannot import backend module. Make sure you're in the backend directory."
    exit 1
}

# Start the server
python -m uvicorn backend.main:app --reload --host 127.0.0.1 --port 8000
