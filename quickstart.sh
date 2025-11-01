#!/bin/bash
# Kashi Finances Backend - Quick Start Script (pyenv-aware)

set -e  # Exit on error

echo "🚀 Kashi Finances Backend - Quick Start"
echo "========================================"
echo ""

# Prefer pyenv-managed python if available and a local version is set
if command -v pyenv >/dev/null 2>&1; then
    if [ -f ".python-version" ]; then
        # Use pyenv shim for the local Python
        PYENV_PY=$(pyenv which python3 2>/dev/null || true)
        if [ -n "$PYENV_PY" ]; then
            PYTHON_EXEC="$PYENV_PY"
        else
            PYTHON_EXEC=python3
        fi
    else
        PYTHON_EXEC=python3
    fi
else
    PYTHON_EXEC=python3
fi

# Report detected python
PYVER=$($PYTHON_EXEC -c 'import sys; print("{}.{}".format(sys.version_info.major, sys.version_info.minor))')
echo "📍 Using Python executable: $PYTHON_EXEC"
echo "📍 Detected Python version: $PYVER"

PY_MAJOR=$($PYTHON_EXEC -c 'import sys; print(sys.version_info.major)')
PY_MINOR=$($PYTHON_EXEC -c 'import sys; print(sys.version_info.minor)')

# Supported python range
if [ "$PY_MAJOR" -ne 3 ] || [ $PY_MINOR -lt 11 ] || [ $PY_MINOR -gt 13 ]; then
    echo "\n⚠️  Detected Python $PYVER which is not within the recommended range (3.11-3.13)."
    echo "   Options to proceed:"
    echo "     • Use Python 3.11 - 3.13 (recommended). Install via pyenv or your package manager."
    echo "       Example (macOS + pyenv):"
    echo "         pyenv install 3.11.6"
    echo "         pyenv local 3.11.6"
    echo "     • OR install Rust toolchain so pydantic-core can be built from source."
    echo "\nExiting early to avoid long build failures."
    exit 1
fi

# Check for Rust toolchain (helpful info only)
if ! command -v rustc >/dev/null 2>&1; then
    echo "\nℹ️  Rust toolchain not found. Some packages (pydantic-core) may require Rust to build native extensions."
    echo "   If pip fails later with pydantic-core build errors, install Rust via rustup:" 
    echo "     curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh"
    echo ""
else
    echo "✅ Found Rust compiler: $(rustc --version)"
fi

# Create virtual environment if it doesn't exist
if [ ! -d "venv" ]; then
    echo ""
    echo "📦 Creating virtual environment using $PYTHON_EXEC..."
    $PYTHON_EXEC -m venv venv
    echo "✓ Virtual environment created"
else
    echo "✓ Virtual environment already exists"
fi

# Activate virtual environment
echo ""
echo "🔧 Activating virtual environment..."
# shellcheck disable=SC1091
source venv/bin/activate

# Ensure pip, setuptools, wheel are up-to-date
echo ""
echo "📥 Upgrading packaging tools..."
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
echo ""
echo "📥 Installing dependencies from requirements.txt..."
if ! pip install -r requirements.txt; then
    echo "\n❌ pip failed to install some packages. If the failure mentions 'pydantic-core',"
    echo "   either install a supported Python version (3.11-3.13) or install the Rust toolchain"
    echo "   so the native extension can be built. See README.md for guidance."
    exit 1
fi

echo "✓ Dependencies installed"

# Verify installation
echo ""
echo "🧪 Verifying FastAPI app can be imported..."
if ! python -c "from backend.main import app; print('✓ FastAPI app loaded successfully')"; then
    echo "❌ Failed to import FastAPI app"
    exit 1
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "Next steps:"
echo "  1. Activate virtual environment: source venv/bin/activate" 
echo "  2. Start dev server: uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo "  3. Visit http://localhost:8000/health"
echo "  4. View API docs at http://localhost:8000/docs"
echo ""
echo "📖 See README.md and BOOTSTRAP_COMPLETE.md for more information"
