"""
AI Components for Kashi Finances Backend.

Contains implementations of AI-powered workflows:

1. InvoiceAgent (Single-Shot Multimodal Workflow)
   - Uses Gemini vision for OCR and structured extraction from receipts
   - NOT an ADK agent - uses direct Gemini API

2. Recommendation System (Prompt Chaining Workflow)
   - Uses DeepSeek V3.2 for product recommendations
   - NOT an ADK agent - uses OpenAI-compatible API
   - Located in: backend/services/recommendation_service.py

ARCHITECTURE NOTE (November 2025):
The project uses simplified LLM workflows instead of complex multi-agent 
architectures. The previous ADK Orchestrator-Workers pattern for recommendations 
was replaced with Prompt Chaining for improved reliability, cost, and maintainability.

See .github/instructions/adk-agents.instructions.md for details.
"""

from backend.agents.invoice import (
    run_invoice_agent,
    InvoiceAgentInput,
    InvoiceAgentOutput,
    INPUT_SCHEMA as INVOICE_INPUT_SCHEMA,
    OUTPUT_SCHEMA as INVOICE_OUTPUT_SCHEMA,
)

__all__ = [
    "run_invoice_agent",
    "InvoiceAgentInput",
    "InvoiceAgentOutput",
    "INVOICE_INPUT_SCHEMA",
    "INVOICE_OUTPUT_SCHEMA",
]
