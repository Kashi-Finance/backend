"""
Recommendation System Prompt Templates

Contains the system prompt and user prompt builder for the Recommendation Service.

The Recommendation Service uses Perplexity Sonar with native web grounding
for product recommendations based on real, current web data.

Architecture:
- Pattern: Grounded LLM (single API call with native web search)
- Model: Perplexity Sonar (sonar or sonar-pro)
- Web Search: Built-in (always-on web grounding)
- Temperature: 0.1 (near-deterministic for factual queries)
- Output: Structured JSON (via response_format)

Prompt Engineering Pattern:
- Uses XML tags for structured content (Anthropic best practice)
- System prompt defines role and capabilities
- User prompt contains task-specific instructions and context
- Perplexity automatically searches the web and grounds responses in real data
"""

from typing import Dict, Any, Optional


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

IMPORTANT: You have access to real-time web search. All product recommendations MUST be based on actual products you find on the web, with real URLs, real prices, and real seller information.
</role>

<capabilities>
- Search the web for real, currently-available products
- Find actual prices and availability from retailers
- Provide verified URLs to product listings
- Extract key requirements from vague descriptions
- Recommend products that match user needs and budget
- Return structured JSON for mobile app display
</capabilities>

<limitations>
- Only recommend products you can verify exist on the web
- URLs must be real product pages, not hallucinated
- Prices must reflect actual current pricing
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
All product URLs and prices must be from your web search results.
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
        budget_hint: Maximum budget in local currency (optional)
        preferred_store: User's preferred store (optional)
        user_note: Additional user preferences or constraints (optional)
        extra_details: Additional context from progressive Q&A (optional)
        
    Returns:
        str: Formatted user prompt ready to be sent to DeepSeek
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
<instructions>
Follow these steps in order:

1. INTENT VALIDATION
   - Check if the query describes prohibited content (see guardrails)
   - If prohibited → return NO_VALID_OPTION immediately

2. EXTRACT REQUIREMENTS
   - Identify product category/type
   - Identify key specifications or features needed
   - Note any explicit constraints from user_preferences

3. GENERATE RECOMMENDATIONS
   - Provide 1-3 products that match the requirements
   - Stay within budget (or max 20% above if justified)
   - Prioritize products available in {country}
   - Consider user preferences and constraints

4. FORMAT OUTPUT
   - Return valid JSON matching the output_schema
   - Use {currency} for all prices
   - Keep copy_for_user factual and brief (max 3 sentences)
   - Use short, UI-friendly badges (max 3 per product)
</instructions>

<examples>
<example>
Query: "Necesito una laptop para diseño gráfico, nada gamer"
Budget: Q7000

Good response:
{{
  "status": "OK",
  "products": [
    {{
      "product_title": "ASUS Vivobook 15 OLED Ryzen 7 16GB RAM",
      "price_total": 6850.00,
      "seller_name": "Tiendas MAX Guatemala",
      "url": "https://max.com.gt/asus-vivobook",
      "pickup_available": true,
      "warranty_info": "Garantía 12 meses en tienda",
      "copy_for_user": "Pantalla OLED ideal para diseño gráfico con colores precisos. Diseño sobrio sin luces RGB. 16GB RAM suficiente para Photoshop y aplicaciones de diseño.",
      "badges": ["Pantalla OLED", "16GB RAM", "Diseño sobrio"]
    }}
  ],
  "metadata": {{
    "total_results": 1,
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
Budget: Q200

Response when no products found in budget:
{{
  "status": "NO_VALID_OPTION",
  "products": [],
  "metadata": {{
    "total_results": 0,
    "query_understood": true,
    "search_successful": true,
    "reason": "No se encontraron audífonos Bluetooth de buena calidad dentro del presupuesto de Q200. Considera aumentar el presupuesto a Q350-500 para mejores opciones."
  }}
}}
</example>
</examples>

<output_schema>
Return ONLY valid JSON with this exact structure. No markdown, no prose.

Success case (products found):
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

Language: Respond in Spanish for {country} users.
</output_schema>"""