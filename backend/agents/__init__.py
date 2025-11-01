"""
adk Agents for Kashi Finances Backend.

Contains implementations of the four allowed adk agents built on Google ADK:
- InvoiceAgent: OCR and structured extraction from receipts/invoices
- RecommendationCoordinatorAgent: Orchestrates recommendation flows
- SearchAgent: AgentTool for product/offer search (used by RecommendationCoordinatorAgent)
- FormatterAgent: AgentTool for result formatting (used by RecommendationCoordinatorAgent)

CRITICAL RULES (from .github/instructions/adk-agents.instructions.md):
- These are the ONLY allowed adk agents
- SearchAgent and FormatterAgent are AgentTools, NOT exposed to API layer directly
- API endpoints call RecommendationCoordinatorAgent, which orchestrates its AgentTools
- All agents MUST define strict typed input/output schemas (JSON-serializable)
- All agents MUST reject out-of-domain requests
- All agents MUST NOT write to database directly (return structured data only)

Always use the most recent version of the Google ADK documentation when creating
or modifying adk agents or their schemas.

TODO: Implement adk agents following .github/instructions/adk-agents.instructions.md
TODO: Each agent will be in its own module (invoice_agent.py, recommendation_coordinator_agent.py, etc.)
"""
