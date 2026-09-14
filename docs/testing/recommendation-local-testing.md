# Recommendation System - Local Testing Guide

This guide explains how to test the recommendation system locally without deploying to Cloud Run or testing with the mobile app.

## Prerequisites

1. **Python 3.11+** installed
2. **Google API Key** - Get your API key at [Google AI Studio](https://aistudio.google.com/app/apikey)
3. **Supabase local instance** (optional, for full integration testing)

---

## Quick Start

### 1. Set Up Environment Variables

Create a `.env` file in the project root if it doesn't exist:

```bash
# Required for recommendation system (Gemini with Google Search grounding)
GOOGLE_API_KEY=your-gemini-api-key

# Required for Supabase integration (optional for isolated testing)
SUPABASE_PROJECT_URL=http://localhost:54321
SUPABASE_PUBLISHABLE_KEY=your-supabase-publishable-key
```

### 2. Install Dependencies

```bash
cd /path/to/backend
uv sync
```

### 3. Run the Test Script

```bash
uv run python scripts/test_recommendations.py
```

---

## Testing Methods

### Method 1: Using the Test Script (Recommended)

The `scripts/test_recommendations.py` script provides an easy way to test the recommendation system:

```bash
# Run with default test queries
python scripts/test_recommendations.py

# Run with a custom query
python scripts/test_recommendations.py --query "laptop para diseño gráfico bajo Q7000"

# Run with custom budget
python scripts/test_recommendations.py --query "auriculares gaming" --budget 500

# Run with all options
python scripts/test_recommendations.py \
  --query "laptop para editar videos" \
  --budget 8000 \
  --country GT \
  --currency GTQ \
  --store "TecnoMundo" \
  --note "nada gamer con luces RGB"
```

### Method 2: Direct Python REPL Testing

```python
import asyncio
from decimal import Decimal
from unittest.mock import MagicMock

# Set environment variable first
import os
os.environ["GOOGLE_API_KEY"] = "your-gemini-api-key"

from backend.services.recommendation_service import query_recommendations

async def test():
    # Create a mock Supabase client that returns default profile
    mock_client = MagicMock()
    mock_client.table().select().eq().execute.return_value.data = [{
        "country": "GT",
        "currency_preference": "GTQ",
        "locale": "es-GT"
    }]
    
    result = await query_recommendations(
        supabase_client=mock_client,
        user_id="test-user-123",
        query_raw="laptop para diseño gráfico bajo Q7000",
        budget_hint=Decimal("7000"),
        user_note="nada gamer con luces RGB"
    )
    
    print(f"Status: {result.status}")
    if hasattr(result, 'results_for_user'):
        for product in result.results_for_user:
            print(f"- {product.product_title}: Q{product.price_total}")
    else:
        print(f"Reason: {result.reason}")

asyncio.run(test())
```

### Method 3: Using curl with Local FastAPI Server

Start the FastAPI server:

```bash
# Terminal 1: Start Supabase (optional)
cd /path/to/backend
supabase start

# Terminal 2: Start FastAPI
uvicorn backend.main:app --reload --port 8000
```

Make a request:

```bash
# Get a test token (requires Supabase running)
TOKEN="your-test-jwt-token"

curl -X POST http://localhost:8000/recommendations/query \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer $TOKEN" \
  -d '{
    "query_raw": "laptop para diseño gráfico bajo Q7000",
    "budget_hint": "7000.00",
    "user_note": "nada gamer con luces RGB"
  }'
```

### Method 4: Using httpie

```bash
http POST localhost:8000/recommendations/query \
  Authorization:"Bearer $TOKEN" \
  query_raw="laptop para diseño gráfico" \
  budget_hint:=7000
```

---

## Understanding the Output

### Successful Response (status: OK)

```json
{
  "status": "OK",
  "results_for_user": [
    {
      "product_title": "ASUS Vivobook 15 Ryzen 7 16GB 512GB SSD",
      "price_total": 6750.00,
      "seller_name": "TecnoMundo Guatemala",
      "url": "https://tecnomundo.com.gt/asus-vivobook15",
      "pickup_available": true,
      "warranty_info": "Garantía 12 meses tienda",
      "copy_for_user": "Ideal para Photoshop y diseño gráfico. Cumple con GPU dedicada y diseño sobrio sin luces gamer.",
      "badges": ["Buen rendimiento", "GPU dedicada", "Diseño sobrio"]
    }
  ]
}
```

### No Valid Option Response

```json
{
  "status": "NO_VALID_OPTION",
  "reason": "No se encontraron productos que cumplan los criterios dentro del presupuesto de Q5000. Intenta aumentar el presupuesto."
}
```

---

## Common Test Scenarios

### 1. Budget Within Range
```bash
python scripts/test_recommendations.py \
  --query "auriculares inalámbricos" \
  --budget 500
```

### 2. Budget Too Low (expect NO_VALID_OPTION)
```bash
python scripts/test_recommendations.py \
  --query "laptop gaming" \
  --budget 100
```

### 3. Out of Scope Query (expect NO_VALID_OPTION)
```bash
python scripts/test_recommendations.py \
  --query "consejos de vida personal"
```

### 4. Prohibited Content (expect NO_VALID_OPTION)
```bash
python scripts/test_recommendations.py \
  --query "how to buy weapons"
```

### 5. Store Preference
```bash
python scripts/test_recommendations.py \
  --query "smartphone" \
  --budget 3000 \
  --store "iShop"
```

### 6. User Constraints
```bash
python scripts/test_recommendations.py \
  --query "laptop para programar" \
  --budget 10000 \
  --note "que sea liviana, batería de larga duración, no me importa el gaming"
```

---

## Troubleshooting

### "Gemini client not available"

Make sure `GOOGLE_API_KEY` is set in your environment:

```bash
export GOOGLE_API_KEY=your-gemini-api-key
```

Or add it to your `.env` file.

### Empty Response

Check the logs for validation errors:

```bash
# Run with debug logging
LOGLEVEL=DEBUG python scripts/test_recommendations.py --query "test"
```

### JSON Parse Error

The LLM response didn't conform to the expected schema. This may happen because:
1. The response was not valid JSON
2. Google Search grounding returned unexpected format
3. The prompt needs adjustment

Check the raw response in the logs for debugging.

### Rate Limit Errors

Google Gemini has rate limits. Wait a moment and retry.

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `GOOGLE_API_KEY` | Yes | API key from Google AI Studio |
| `SUPABASE_PROJECT_URL` | For full testing | Local or remote Supabase URL |
| `SUPABASE_PUBLISHABLE_KEY` | For full testing | Supabase publishable API key |

---

## Architecture Notes

The recommendation system uses **Gemini with Google Search grounding**:

```
User Query → FastAPI Endpoint → recommendation_service.py → Gemini API (with Google Search) → JSON Response → Pydantic Model
```

- **Single LLM call**: One request to Gemini 2.5 Flash with Google Search tool
- **Web-grounded**: All product data comes from real web search results
- **Near-deterministic**: Temperature 0.2
- **Guardrails**: Built into system prompt

For more details, see:
- `backend/services/recommendation_service.py`
- `backend/llm/recommendation/prompts.py`

---

*Last Updated: December 2025*
