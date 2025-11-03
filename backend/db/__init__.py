"""
Database access layer for Kashi Finances Backend.

CRITICAL: This layer is governed by .github/instructions/db.instructions.md

All database operations MUST:
- Respect Row Level Security (RLS): user_id = auth.uid()
- Never bypass RLS
- Never invent schemas, table names, or SQL queries
- Add TODO(db-team) comments for any persistence needs

DO NOT define table schemas, migrations, or RLS policies here.
DO NOT write raw SQL unless explicitly defined in db.instructions.md.

If you need to persist or fetch data and the exact implementation isn't in
db.instructions.md, add a comment like:
    # TODO(db-team): persist/fetch <resource> according to backend/db.instructions.md

Examples of what WILL be defined here eventually (per db.instructions.md):
- Supabase client initialization
- Data access functions that enforce RLS
- Helper functions for invoice.extracted_text formatting (EXTRACTED_INVOICE_TEXT_FORMAT)
- Embedding generation and vector search utilities (using text-embedding-3-small)
"""

from .client import get_supabase_client

__all__ = ["get_supabase_client"]
