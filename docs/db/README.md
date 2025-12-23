# Database Documentation Structure

> Navigation guide for Kashi Finances database documentation.

## File Index

| File | Purpose | When to Read |
|------|---------|--------------|
| [../DB-documentation.md](../../DB-documentation.md) | **Index file** — Quick reference | Start here for overview |
| [tables.md](./tables.md) | Full table definitions | When implementing CRUD, migrations |
| [rls.md](./rls.md) | Row-Level Security policies | When debugging access, adding tables |
| [enums.md](./enums.md) | PostgreSQL enum definitions | When using typed fields |
| [indexes.md](./indexes.md) | Index definitions and strategy | When optimizing queries |
| [soft-delete.md](./soft-delete.md) | Soft-delete patterns | When implementing delete operations |
| [cached-values.md](./cached-values.md) | Cached balance/consumption | When working with balance calculations |
| [semantic-search.md](./semantic-search.md) | pgvector embeddings | When implementing search features |
| [system-data.md](./system-data.md) | System categories and keys | When handling special transactions |

## Quick Links

- **Table schemas** → [tables.md](./tables.md)
- **RLS policies** → [rls.md](./rls.md)
- **Delete behavior** → [soft-delete.md](./soft-delete.md)
- **Balance caching** → [cached-values.md](./cached-values.md)

## Architecture

```
Supabase (PostgreSQL)
├── auth.users          ← Managed by Supabase Auth
├── public.*            ← Application tables with RLS
├── pgvector extension  ← Semantic search
└── Storage buckets     ← Invoice images
```
