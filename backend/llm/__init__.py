"""
LLM workflows for Kashi Finances Backend.

Contains implementations of single-shot LLM workflows (no agent framework):

1. Invoice OCR workflow (legacy name: InvoiceAgent)
   - Uses Gemini vision for OCR and structured extraction from receipts
   - Single-shot multimodal call via the google-genai SDK (no ADK, no tool loop)

2. Recommendation workflow (legacy name: Recommendation System)
   - Uses Gemini with Google Search grounding for product recommendations
   - Single-shot call via the google-genai SDK with the Google Search tool

The directory is named `llm` (renamed from `agents` in 2026) because these are
plain request/response LLM calls, not autonomous agents. Identifiers such as
`run_invoice_agent` / `InvoiceAgentOutput` keep their legacy names for
backward compatibility.

See .github/instructions/llm-workflows.instructions.md for details.
"""

from backend.llm.invoice import (
    INPUT_SCHEMA as INVOICE_INPUT_SCHEMA,
)
from backend.llm.invoice import (
    OUTPUT_SCHEMA as INVOICE_OUTPUT_SCHEMA,
)
from backend.llm.invoice import (
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
