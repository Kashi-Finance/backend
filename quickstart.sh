#!/bin/bash
# Kashi Finances Backend - Quick Start Script (pyenv-aware)
# 
# This script sets up a complete local development environment including:
# - Python virtual environment
# - Dependencies installation
# - Supabase local stack (PostgreSQL + Auth + Storage)
# - Database migrations
# - Test verification

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

# Check Supabase CLI
echo ""
echo "🐘 Verifying Supabase CLI..."
if ! command -v supabase &> /dev/null; then
    echo "⚠️  Supabase CLI not found (optional, only needed for local DB)."
    echo "   Install with: brew install supabase/tap/supabase"
    echo "   Or download from: https://github.com/supabase/cli"
else
    echo "✓ Supabase CLI found: $(supabase --version)"
    
    # Check if supabase/ directory exists
    if [ -d "supabase" ]; then
        echo ""
        echo "🗄️  Starting local Supabase stack (PostgreSQL + Auth + Storage)..."
        if supabase start > /dev/null 2>&1; then
            echo "✓ Supabase local services started"
            # Display connection info
            SUPABASE_LOCAL_URL=$(supabase status 2>/dev/null | grep "API URL" | awk '{print $NF}' || echo "http://localhost:54321")
            echo "   API URL: $SUPABASE_LOCAL_URL"
        else
            echo "⚠️  Supabase may already be running or encountered an error"
        fi
    else
        echo "⚠️  supabase/ directory not found. To set up Supabase migrations:"
        echo "   supabase init"
    fi
fi

# Verify installation
echo ""
echo "🧪 Verifying FastAPI app can be imported..."
if ! python -c "from backend.main import app; print('✓ FastAPI app loaded successfully')"; then
    echo "❌ Failed to import FastAPI app"
    exit 1
fi

# Run tests
echo ""
echo "🧪 Running test suite..."
if command -v pytest &> /dev/null; then
    if python -m pytest tests/ -v --tb=short; then
        echo "✅ All tests passed!"
    else
        echo "⚠️  Some tests failed. Review output above."
    fi
else
    echo "ℹ️  pytest not found. To run tests manually: python -m pytest tests/ -v"
fi

echo ""
echo "✅ Setup complete!"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "📋 Next Steps:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1️⃣  Activate virtual environment (if not already active):"
echo "   source venv/bin/activate"
echo ""
echo "2️⃣  Start the development server:"
echo "   uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000"
echo ""
echo "3️⃣  View API documentation:"
echo "   • OpenAPI/Swagger: http://localhost:8000/docs"
echo "   • ReDoc: http://localhost:8000/redoc"
echo "   • Health check: http://localhost:8000/health"
echo ""
echo "4️⃣  Example API calls (after server starts):"
echo ""
echo "   📝 Create a normal transfer (between user's own accounts):"
echo "   curl -X POST http://localhost:8000/transfers \\"
echo '     -H "Authorization: Bearer <TOKEN>" \\'
echo '     -H "Content-Type: application/json" \\'
echo '     -d {"from_account_id":"<ACCOUNT_A>","to_account_id":"<ACCOUNT_B>",...}'
echo ""
echo "   � Create a recurring transfer (monthly example):"
echo "   curl -X POST http://localhost:8000/transfers/recurring \\"
echo '     -H "Authorization: Bearer <TOKEN>" \\'
echo '     -H "Content-Type: application/json" \\'
echo '     -d {"from_account_id":"<ACCOUNT_A>","to_account_id":"<ACCOUNT_B>","frequency":"monthly",...}'
echo ""
echo "5️⃣  Run tests anytime:"
echo "   python -m pytest tests/ -v              # Run all tests"
echo "   python -m pytest tests/test_transfers.py -v  # Test transfer system only"
echo "   python -m pytest tests/ -k transfer --tb=short  # Filter tests"
echo ""
echo "6️⃣  Watch for recurring transaction syncing:"
echo "   • Check logs for: 'Syncing recurring transactions for user'"
echo "   • Backend automatically creates new transactions from recurring rules"
echo "   • Verify in logs or by querying /transactions endpoint"
echo ""
echo "📖 Documentation:"
echo "   • API Endpoints: See API-endpoints.md"
echo "   • Architecture: See kashi-agents-architecture.md"
echo "   • Transfer System: See recommendation-agent-specs.md"
echo "   • README: See README.md for full project guide"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
