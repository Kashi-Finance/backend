#!/bin/zsh
# Load environment variables from .env for integration scripts
# Usage: source scripts/integration/setup-env.sh

set -a  # Mark all new variables for export
if [ -f .env ]; then
    source .env
else
    echo "❌ Error: .env file not found in current directory"
    exit 1
fi
set +a  # Stop auto-exporting

# Validate required variables
required_vars=("SUPABASE_URL" "SUPABASE_PUBLISHABLE_KEY" "REAL_TEST_TOKEN")
missing=()

for var in "${required_vars[@]}"; do
    if [ -z "$(eval echo \$$var)" ]; then
        missing+=("$var")
    fi
done

if [ ${#missing[@]} -gt 0 ]; then
    echo "❌ Missing environment variables: ${missing[*]}"
    echo "   Make sure these are defined in .env"
    exit 1
fi

# Validate token format (basic JWT check: 3 parts separated by dots)
if [[ ! "$REAL_TEST_TOKEN" =~ ^[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+\.[a-zA-Z0-9_-]+$ ]]; then
    echo "⚠️  Warning: REAL_TEST_TOKEN does not look like a valid JWT"
fi

echo "✅ Environment loaded successfully"
echo "   SUPABASE_URL: $SUPABASE_URL"
echo "   SUPABASE_PUBLISHABLE_KEY: ${SUPABASE_PUBLISHABLE_KEY:0:20}..."
echo "   REAL_TEST_TOKEN: ${REAL_TEST_TOKEN:0:30}..."
