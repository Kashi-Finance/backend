#!/usr/bin/env zsh
# Create or login a Supabase test user and store REAL_TEST_TOKEN in an env file
# Usage:
#   ./00-create-test-user.sh \
#     --email test+ci@example.com \
#     --password 'TestPassword123!' \
#     [--env-file .env]

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${0}")" && pwd)

# Defaults
EMAIL="test+ci@example.com"
PASSWORD="TestPassword123!"
ENV_FILE=".env"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2;;
    --password) PASSWORD="$2"; shift 2;;
    --env-file) ENV_FILE="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--email EMAIL] [--password PASSWORD] [--env-file FILE]"; exit 0;;
    *) echo "Unknown arg: $1"; echo "Usage: $0 [--email EMAIL] [--password PASSWORD] [--env-file FILE]"; exit 1;;
  esac
done

# Load existing env vars if present
if [[ -f "${ENV_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
fi

if [[ -z "${SUPABASE_URL:-}" || -z "${SUPABASE_PUBLISHABLE_KEY:-}" ]]; then
  echo "ERROR: SUPABASE_URL and SUPABASE_PUBLISHABLE_KEY must be set in ${ENV_FILE} or environment." >&2
  echo "Edit ${ENV_FILE} and add these variables, for example:" >&2
  echo "  SUPABASE_URL=https://your-project.supabase.co" >&2
  echo "  SUPABASE_PUBLISHABLE_KEY=your-anon-key" >&2
  exit 2
fi

echo "Supabase URL: ${SUPABASE_URL}"
echo "Using publishable key from ${ENV_FILE} (or env)"

JSON_RESPONSE=""

echo "Attempting signup for ${EMAIL} (may return token or require email confirmation)..."
JSON_RESPONSE=$(curl -s -X POST "${SUPABASE_URL}/auth/v1/signup" \
  -H "apikey: ${SUPABASE_PUBLISHABLE_KEY}" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}") || true

echo "Signup response:" 
echo "${JSON_RESPONSE}" | jq -S . 2>/dev/null || echo "(no jq: raw json below)\n${JSON_RESPONSE}"

# Try to extract access_token directly from signup response (some projects return token on signup)
if command -v jq >/dev/null 2>&1; then
  ACCESS_TOKEN=$(echo "${JSON_RESPONSE}" | jq -r '.access_token // empty')
else
  ACCESS_TOKEN=$(python3 - <<PY
import sys, json
try:
    obj = json.load(sys.stdin)
    print(obj.get('access_token',''))
except Exception:
    print('')
PY
  <<<"${JSON_RESPONSE}")
fi

if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "Attempting to fetch access_token via /auth/v1/token (password grant)..."
  # Try JSON body first to avoid cases where server expects JSON
  TOKEN_RESPONSE=$(curl -s -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
    -H "apikey: ${SUPABASE_PUBLISHABLE_KEY}" \
    -H "Content-Type: application/json" \
    -d "{\"email\":\"${EMAIL}\",\"password\":\"${PASSWORD}\"}") || true

  # If that failed with a JSON parse error, try form-encoded fallback
  if echo "${TOKEN_RESPONSE}" | grep -qi 'bad_json\|Could not parse request body' >/dev/null 2>&1; then
    TOKEN_RESPONSE=$(curl -s -X POST "${SUPABASE_URL}/auth/v1/token?grant_type=password" \
      -H "apikey: ${SUPABASE_PUBLISHABLE_KEY}" \
      -H "Content-Type: application/x-www-form-urlencoded" \
      --data-urlencode "email=${EMAIL}" \
      --data-urlencode "password=${PASSWORD}") || true
  fi

  # Try to extract access_token from the token response
  if command -v jq >/dev/null 2>&1; then
    ACCESS_TOKEN=$(echo "${TOKEN_RESPONSE}" | jq -r '.access_token // empty')
  else
    ACCESS_TOKEN=$(python3 - <<PY
import sys, json
try:
    obj = json.load(sys.stdin)
    print(obj.get('access_token',''))
except Exception:
    print('')
PY
    <<<"${TOKEN_RESPONSE}")
  fi
fi

if [[ -z "${ACCESS_TOKEN}" ]]; then
  echo "Failed to obtain access_token. Token endpoint response:" >&2
  # TOKEN_RESPONSE may be empty if signup returned a token but extraction failed
  if [[ -n "${TOKEN_RESPONSE:-}" ]]; then
    echo "${TOKEN_RESPONSE}" | jq -S . 2>/dev/null || echo "${TOKEN_RESPONSE}"
  else
    echo "(no token response body available)"
  fi
  echo "If your project requires email confirmation on signup, use a service_role key locally or create the user via the Supabase dashboard." >&2
  exit 3
fi

echo "Got access_token (length: ${#ACCESS_TOKEN})"

SAVE_FILE="${ENV_FILE}"
if [[ -f "${SAVE_FILE}" ]]; then
  # Replace any existing REAL_TEST_TOKEN line, preserve others
  grep -v '^REAL_TEST_TOKEN=' "${SAVE_FILE}" > "${SAVE_FILE}.tmp" || true
  printf '%s\n' "REAL_TEST_TOKEN=${ACCESS_TOKEN}" >> "${SAVE_FILE}.tmp"
  mv "${SAVE_FILE}.tmp" "${SAVE_FILE}"
else
  cat > "${SAVE_FILE}" <<EOF
SUPABASE_URL=${SUPABASE_URL}
SUPABASE_PUBLISHABLE_KEY=${SUPABASE_PUBLISHABLE_KEY}
REAL_TEST_TOKEN=${ACCESS_TOKEN}
EOF
fi

echo "Saved REAL_TEST_TOKEN to ${SAVE_FILE}"
echo "You can now run: source scripts/integration/setup-env.sh && ./scripts/integration/11-profile-get.sh"

exit 0
