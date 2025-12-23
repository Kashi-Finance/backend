"""
Database access layer for Kashi Finances Backend.

CRITICAL: This layer is governed by .github/instructions/db.instructions.md

All database operations MUST:
- Respect Row Level Security (RLS): user_id = auth.uid()
- Never bypass RLS
- Never invent schemas, table names, or SQL queries

DO NOT define table schemas, migrations, or RLS policies here.
DO NOT write raw SQL unless explicitly defined in db.instructions.md.

Includes:
- Supabase client initialization
- Data access functions that enforce RLS
- Helper functions for invoice.extracted_text formatting (EXTRACTED_INVOICE_TEXT_FORMAT)
- Embedding generation and vector search utilities (using text-embedding-3-small)
"""

from .client import get_supabase_client

__all__ = ["get_supabase_client"]
