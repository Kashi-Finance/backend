#!/bin/zsh
# Test: GET /health (no authentication required)
# Quick health check to verify the backend is running

cd "$(dirname "$0")/../.."

echo "🔍 Testing: GET /health"
echo ""

curl -X GET http://localhost:8000/health \
  -H "Content-Type: application/json" \
  -w "\n\n📊 Status Code: %{http_code}\n" \
  -s | jq . 2>/dev/null || curl -X GET http://localhost:8000/health -w "\n\n📊 Status Code: %{http_code}\n" -s

echo ""
