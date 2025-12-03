# RPC Documentation - Navigation Guide

This folder contains detailed documentation for all PostgreSQL RPC functions in the Kashi Finances backend.

## Documentation Structure

| File | Contents |
|------|----------|
| `accounts.md` | Account deletion and balance RPCs |
| `transactions.md` | Transaction deletion RPC |
| `categories.md` | Category deletion with reassignment |
| `transfers.md` | Create and delete transfers |
| `recurring.md` | Recurring transaction sync and management |
| `wishlists.md` | Create wishlist with items |
| `invoices.md` | Invoice soft-delete |
| `budgets.md` | Budget soft-delete |
| `cache.md` | Balance and consumption recomputation |
| `currency.md` | Currency validation and enforcement |
| `favorites.md` | Favorite account management |
| `guidelines.md` | Usage patterns and best practices |

## Quick Start

1. **Start with the index** - See `RPC-documentation.md` in project root for quick reference
2. **Load details on-demand** - Read specific files only when you need full signatures, behaviors, and examples
3. **For patterns** - See `guidelines.md` for common usage patterns and testing approaches

## Related Documentation

- `/DB-documentation.md` - Database schema index
- `/API-endpoints.md` - HTTP endpoints that call these RPCs
- `/docs/db/` - Detailed database documentation
