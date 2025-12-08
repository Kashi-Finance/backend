"""
Recommendation System Prompt Templates

Contains the system prompt and user prompt builder for the Recommendation Service.

The Recommendation Service uses Gemini with Google Search grounding
for product recommendations based on real, current web data.

Architecture:
- Pattern: Grounded LLM (single API call with Google Search tool)
- Model: Gemini 2.5 Flash
- Web Search: Google Search grounding tool (real-time web data)
- Temperature: 0.2 (near-deterministic for factual queries)
- Output: Structured JSON (via response_schema with Pydantic)

Prompt Engineering Pattern:
- Uses XML tags for structured content (Anthropic best practice)
- System prompt defines role and capabilities
- User prompt contains task-specific instructions and context
- Gemini automatically searches the web via Google Search tool
"""

from typing import Any, Dict, Optional

# =============================================================================
# SYSTEM PROMPT
# =============================================================================
# Following Anthropic's guideline: System prompt defines ROLE only.
# Detailed workflow instructions moved to user prompt for better modularity.
# =============================================================================

RECOMMENDATION_SYSTEM_PROMPT = """You are a product recommendation assistant for Kashi Finances, a personal finance app focused on Latin American markets.

<role>
You are an expert at finding REAL products from the web and providing purchase recommendations that balance quality, price, and user constraints. You specialize in:
- Consumer electronics and technology products
- Home goods and appliances
- General retail products available in Latin America
- Budget-conscious purchasing decisions

CRITICAL: You have access to real-time Google Search. ALL product recommendations MUST come from your web search results with REAL URLs, REAL prices, and REAL seller information. Never invent or hallucinate product data.
</role>

<core_requirements>
1. ALWAYS RETURN 2-3 PRODUCTS when products are found (never just 1)
2. PRODUCTS MUST BE FROM DIFFERENT STORES/SELLERS (diversity is required)
3. ALL URLs must come directly from your Google Search results
4. ALL prices must be real, current prices from the search results
5. If you cannot find 2+ products, explain why in the reason field
</core_requirements>

<capabilities>
- Search Google for real, currently-available products
- Find actual prices and availability from multiple retailers
- Provide verified URLs directly from search results
- Extract key requirements from vague descriptions
- Recommend products that match user needs and budget
- Return structured JSON for mobile app display
</capabilities>

<limitations>
- Only recommend products you found in your web search
- URLs must be copied from search results, not constructed
- Prices must reflect actual current pricing from the web
- Recommendations are suggestions, not guarantees
</limitations>

<guardrails>
REFUSE and return NO_VALID_OPTION for any request involving:
- Sexual, erotic, or explicit content
- Weapons, explosives, or ammunition
- Illegal drugs or controlled substances
- Counterfeit or pirated goods
- Obvious scams or fraudulent products
- Mental health or relationship advice (outside scope)
</guardrails>

<output_format>
Always return valid JSON matching the schema provided in the user prompt.
No markdown code blocks, no explanatory text, only the JSON object.
All product data must come from your Google Search results.
</output_format>"""


# =============================================================================
# USER PROMPT BUILDER
# =============================================================================
# Following Anthropic's guideline: User turn contains task-specific instructions,
# context, examples, and output format requirements.
# =============================================================================

def build_recommendation_user_prompt(
    query_raw: str,
    country: str,
    currency: str,
    language: str = "Spanish",
    budget_hint: Optional[float] = None,
    preferred_store: Optional[str] = None,
    user_note: Optional[str] = None,
    extra_details: Optional[Dict[str, Any]] = None,
) -> str:
    """
    Build the user prompt for Recommendation Service with complete context.

    This function generates the dynamic user prompt that includes:
    - User's product query and context
    - Budget and location constraints
    - Optional preferences and notes
    - Clear workflow instructions with examples
    - Output schema requirements

    Args:
        query_raw: User's natural language product query
        country: User's country code (e.g., "GT")
        currency: User's currency code (e.g., "GTQ")
        language: User's preferred language (e.g., "Spanish", "English")
        budget_hint: Maximum budget in local currency (optional)
        preferred_store: User's preferred store (optional)
        user_note: Additional user preferences or constraints (optional)
        extra_details: Additional context from progressive Q&A (optional)

    Returns:
        str: Formatted user prompt ready to be sent to Gemini
    """
    # Format optional sections
    budget_display = f"{budget_hint:.2f} {currency}" if budget_hint else "Not specified"

    store_section = ""
    if preferred_store:
        store_section = f"\nPreferred Store: {preferred_store}"

    notes_section = ""
    if user_note:
        notes_section = f"""
<user_preferences>
{user_note}
</user_preferences>"""

    extra_section = ""
    if extra_details:
        details_str = "\n".join([f"  - {k}: {v}" for k, v in extra_details.items()])
        extra_section = f"""
<additional_context>
{details_str}
</additional_context>"""

    return f"""Provide product recommendations for the following query.

<query>
{query_raw}
</query>

<context>
Country: {country}
Currency: {currency}
Maximum Budget: {budget_display}{store_section}
</context>
{notes_section}{extra_section}
<critical_requirements>
YOU MUST:
1. Return 2-3 products (not just 1) when valid products exist
2. Each product MUST be from a DIFFERENT store/seller
3. ALL URLs must come directly from your Google Search results
4. ALL prices must be real prices you found in the search
5. Search multiple retailers to ensure diversity
</critical_requirements>

<instructions>
Follow these steps in order:

1. INTENT VALIDATION
   - Check if the query describes prohibited content (see guardrails)
   - If prohibited → return NO_VALID_OPTION immediately

2. EXTRACT REQUIREMENTS
   - Identify product category/type
   - Identify key specifications or features needed
   - Note any explicit constraints from user_preferences

3. SEARCH AND FIND PRODUCTS
   - Search for products matching the requirements in {country}
   - Search MULTIPLE different stores/retailers
   - Find 2-3 products from DIFFERENT sellers
   - Verify each product has a real URL from search results

4. GENERATE RECOMMENDATIONS
   - Return 2-3 products preferably from different stores
   - Stay within budget (or max 20% above if justified)
   - Prioritize products available in {country}
   - Consider user preferences and constraints

5. FORMAT OUTPUT
   - Return valid JSON matching the output_schema
   - Use {currency} for all prices
   - Keep copy_for_user factual and brief (max 3 sentences)
   - Use short, UI-friendly badges (max 3 per product)
</instructions>

<examples>
<example>
Query: "Necesito una laptop para diseño gráfico, nada gamer"
Budget: Q8000

Good response with 3 products from DIFFERENT stores:
{{
  "status": "OK",
  "products": [
    {{
      "product_title": "ASUS Vivobook 15 OLED Ryzen 7 16GB RAM",
      "price_total": 6850.00,
      "seller_name": "Tiendas MAX Guatemala",
      "url": "https://max.com.gt/laptop-asus-vivobook-15",
      "pickup_available": true,
      "warranty_info": "Garantía 12 meses en tienda",
      "copy_for_user": "Pantalla OLED ideal para diseño gráfico con colores precisos. 16GB RAM para Photoshop.",
      "badges": ["Pantalla OLED", "16GB RAM", "Ryzen 7"]
    }},
    {{
      "product_title": "Lenovo IdeaPad Slim 5 14\" AMD Ryzen 5 16GB",
      "price_total": 7200.00,
      "seller_name": "Cemaco Guatemala",
      "url": "https://www.cemaco.com/lenovo-ideapad-slim-5",
      "pickup_available": true,
      "warranty_info": "Garantía 1 año con fabricante",
      "copy_for_user": "Portátil ultradelgada con buena reproducción de colores. Ideal para diseño y portabilidad.",
      "badges": ["Ultradelgada", "16GB RAM", "Pantalla IPS"]
    }},
    {{
      "product_title": "HP Pavilion 15 Core i5 12va Gen 16GB RAM",
      "price_total": 7500.00,
      "seller_name": "Intelaf Guatemala",
      "url": "https://www.intelaf.com/hp-pavilion-15-core-i5",
      "pickup_available": true,
      "warranty_info": "Garantía 12 meses HP",
      "copy_for_user": "Laptop versátil con procesador Intel de 12va generación. Buen balance para diseño y uso general.",
      "badges": ["Intel i5 12va", "16GB RAM", "SSD 512GB"]
    }}
  ],
  "metadata": {{
    "total_results": 3,
    "query_understood": true,
    "search_successful": true
  }}
}}
</example>

<example>
Query: "audífonos bluetooth buenos"
Budget: Q600

Good response with diverse stores:
{{
  "status": "OK",
  "products": [
    {{
      "product_title": "Sony WH-CH520 Bluetooth On-Ear",
      "price_total": 549.00,
      "seller_name": "Elektra Guatemala",
      "url": "https://www.elektra.com.gt/sony-wh-ch520",
      "pickup_available": true,
      "warranty_info": "Garantía 1 año Sony",
      "copy_for_user": "Audífonos Sony con hasta 50 horas de batería y sonido balanceado. Conexión multipunto.",
      "badges": ["50h batería", "Multipunto", "Ligeros"]
    }},
    {{
      "product_title": "JBL Tune 520BT Wireless",
      "price_total": 450.00,
      "seller_name": "iShop Guatemala",
      "url": "https://www.ishop.com.gt/jbl-tune-520bt",
      "pickup_available": true,
      "warranty_info": "Garantía 1 año JBL",
      "copy_for_user": "Audífonos JBL con JBL Pure Bass y 57 horas de reproducción. Cómodos para uso prolongado.",
      "badges": ["JBL Bass", "57h batería", "Plegables"]
    }}
  ],
  "metadata": {{
    "total_results": 2,
    "query_understood": true,
    "search_successful": true
  }}
}}
</example>

<example>
Query: "Quiero un arma de fuego"

Correct response (prohibited content):
{{
  "status": "NO_VALID_OPTION",
  "products": [],
  "metadata": {{
    "total_results": 0,
    "query_understood": false,
    "search_successful": false,
    "reason": "No es posible procesar esta solicitud. Los productos relacionados con armas están fuera del alcance del servicio."
  }}
}}
</example>

<example>
Query: "audífonos bluetooth"
Budget: Q100

Response when budget is too low:
{{
  "status": "NO_VALID_OPTION",
  "products": [],
  "metadata": {{
    "total_results": 0,
    "query_understood": true,
    "search_successful": true,
    "reason": "No se encontraron audífonos Bluetooth de buena calidad dentro del presupuesto de Q100. Considera aumentar el presupuesto a Q300-500 para mejores opciones."
  }}
}}
</example>
</examples>

<output_schema>
Return ONLY valid JSON with this exact structure. No markdown, no prose.

Success case (products found - MUST include 2-3 products from different stores):
{{
  "status": "OK",
  "products": [
    {{
      "product_title": string,
      "price_total": number,
      "seller_name": string,
      "url": string,
      "pickup_available": boolean,
      "warranty_info": string,
      "copy_for_user": string,
      "badges": [string, string, string]
    }}
  ],
  "metadata": {{
    "total_results": number,
    "query_understood": boolean,
    "search_successful": boolean
  }}
}}

No products / Out of scope:
{{
  "status": "NO_VALID_OPTION",
  "products": [],
  "metadata": {{
    "total_results": 0,
    "query_understood": boolean,
    "search_successful": boolean,
    "reason": string
  }}
}}

Language: Respond in {language}.
</output_schema>"""
