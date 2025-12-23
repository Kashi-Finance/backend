#!/bin/zsh
# Create a profile row for the authenticated user via Supabase REST API
# Usage: ./11b-create-profile.sh [--first-name NAME] [--country CODE] [--currency CODE]

set -euo pipefail

SCRIPT_DIR=$(cd -- "$(dirname -- "${0}")" && pwd)

FIRST_NAME="TestUser"
COUNTRY="GT"
CURRENCY="GTQ"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --first-name) FIRST_NAME="$2"; shift 2;;
    --country) COUNTRY="$2"; shift 2;;
    --currency) CURRENCY="$2"; shift 2;;
    -h|--help) echo "Usage: $0 [--first-name NAME] [--country CODE] [--currency CODE]"; exit 0;;
    *) echo "Unknown arg: $1"; exit 1;;
  esac
done

cd "$(dirname "$0")/../.."
source scripts/integration/setup-env.sh || exit 1

echo "Creating profile for authenticated user..."

PAYLOAD=$(python3 - <<PY
import json
payload = {
    'first_name': '${FIRST_NAME}',
    'currency_preference': '${CURRENCY}',
    'country': '${COUNTRY}',
    'locale': 'system'
}
print(json.dumps(payload))
PY
)

echo "Payload: $PAYLOAD"

# Call the backend API to create the profile (uses the user's token)
API_URL="http://127.0.0.1:8000/profile"
RESP=$(curl -s -w "\n%{http_code}" -X POST "$API_URL" \
  -H "Authorization: Bearer ${REAL_TEST_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "$PAYLOAD")

HTTP_CODE=$(echo "$RESP" | tail -n1)
BODY=$(echo "$RESP" | sed '$d')

echo "Response body:" 
echo "$BODY" | jq -S . 2>/dev/null || echo "$BODY"
echo "HTTP status: $HTTP_CODE"

if [[ "$HTTP_CODE" -ge 200 && "$HTTP_CODE" -lt 300 ]]; then
  echo "Profile created via backend successfully. You can now run ./scripts/integration/11-profile-get.sh"
  exit 0
elif [[ "$HTTP_CODE" -eq 409 ]]; then
  echo "Profile already exists for this user (expected if profile was created previously)."
  echo "You can update it using: ./scripts/integration/12-profile-patch.sh"
  exit 0
else
  echo "Failed to create profile via backend (status $HTTP_CODE)" >&2
  exit 3
fi
