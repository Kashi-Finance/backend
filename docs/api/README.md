# Kashi Finances API Documentation

> **Navigation Guide for AI Agents and Developers**

This directory contains comprehensive API documentation organized by feature domain. This structure is optimized for AI agent context windows following Anthropic's progressive disclosure pattern.

## Quick Navigation

| Domain | File | Description |
|--------|------|-------------|
| Auth & Profile | [auth-profile.md](./auth-profile.md) | User authentication, session, profile CRUD |
| Accounts | [accounts.md](./accounts.md) | Financial accounts (bank, cash, credit) |
| Categories | [categories.md](./categories.md) | Transaction categorization (system + user) |
| Transactions | [transactions.md](./transactions.md) | Manual transactions, filtering, CRUD |
| Invoices | [invoices.md](./invoices.md) | OCR workflow, receipt processing |
| Budgets | [budgets.md](./budgets.md) | Spending limits, category linking |
| Recurring | [recurring.md](./recurring.md) | Scheduled transaction rules |
| Transfers | [transfers.md](./transfers.md) | Internal account transfers |
| Wishlists | [wishlists.md](./wishlists.md) | Purchase goals and saved items |
| Recommendations | [recommendations.md](./recommendations.md) | AI-powered product search |
| Cross-Cutting | [cross-cutting.md](./cross-cutting.md) | Security, dependencies, shared patterns |

## How to Use This Documentation

1. **For a specific endpoint**: Navigate to the relevant domain file above
2. **For API overview**: See the [API Index](../../API-endpoints.md) in the root
3. **For cross-feature interactions**: See [cross-cutting.md](./cross-cutting.md)
4. **For security/auth patterns**: See [auth-profile.md](./auth-profile.md) Section 0

## Documentation Standards

Each domain file follows this structure:
- **Table of Contents** (at top for files >100 lines)
- **Endpoint Reference Table** (method, path, description)
- **Detailed Endpoint Sections** (request/response schemas, status codes, examples)
- **Domain-Specific Rules** (business logic, constraints)
- **Integration Notes** (how this domain interacts with others)

## File Size Targets

Per Anthropic best practices:
- Each file should be under 500 lines when possible
- Files >100 lines include table of contents
- Complex topics split into focused sections
