"""
AI Components for Kashi Finances Backend.

Contains implementations of AI-powered workflows:

1. InvoiceAgent (Single-Shot Multimodal Workflow)
   - Uses Gemini vision for OCR and structured extraction from receipts
   - NOT an ADK agent - uses direct Gemini API

2. Recommendation System (Web-Grounded LLM)
   - Uses Gemini with Google Search grounding for product recommendations
   - NOT an ADK agent - uses Google Gen AI SDK with Google Search tool
   - Located in: backend/services/recommendation_service.py

The project uses simplified LLM workflows instead of complex multi-agent
architectures. The recommendation system uses Gemini with Google Search grounding
for real, web-verified product recommendations.

See .github/instructions/adk-agents.instructions.md for details.
"""

from backend.agents.invoice import (
    INPUT_SCHEMA as INVOICE_INPUT_SCHEMA,
)
from backend.agents.invoice import (
    OUTPUT_SCHEMA as INVOICE_OUTPUT_SCHEMA,
)
from backend.agents.invoice import (
    InvoiceAgentInput,
    InvoiceAgentOutput,
    run_invoice_agent,
)

__all__ = [
    "run_invoice_agent",
    "InvoiceAgentInput",
    "InvoiceAgentOutput",
    "INVOICE_INPUT_SCHEMA",
    "INVOICE_OUTPUT_SCHEMA",
]
