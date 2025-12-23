# Semantic Search

> Transactions support natural language search via pgvector embeddings.

---

## Overview

Users can search transactions using natural language:
- "supermarket expenses last month"
- "gym membership payments"
- "coffee shops near downtown"

Even if the transaction description doesn't contain these exact words, semantic search finds relevant matches.

---

## Implementation

### Embedding Model

**Model:** `text-embedding-3-small` by OpenAI

| Property | Value |
|:---------|:------|
| Dimensions | 1536 |
| Cost | ~$0.02 USD per 1M tokens |
| Quality | Good multilingual retrieval |

### Storage

| Table | Column | Type |
|:------|:-------|:-----|
| `transaction` | `embedding` | `VECTOR(1536)` |

### Index

```sql
CREATE INDEX transaction_embedding_idx 
ON transaction 
USING ivfflat (embedding vector_cosine_ops);
```

**Index type:** IVFFlat (Inverted File with Flat compression)
**Similarity metric:** Cosine similarity

---

## Embedding Generation

### When to Generate

1. **Transaction creation** — Generate embedding after insert
2. **Transaction update** — Regenerate if description changes
3. **Backfill** — Background job for transactions without embeddings

### Input Text

The embedding is generated from combined transaction data:

**If transaction has linked invoice (`invoice_id` is not NULL):**
```
Store: {invoice.store_name}
Items: {invoice.items}
Total: {transaction.amount} {account.currency}
Date: {transaction.date}
Category: {category.name}
Description: {transaction.description}
```

**If transaction is manual (`invoice_id` is NULL):**
```
Amount: {transaction.amount} {account.currency}
Date: {transaction.date}
Category: {category.name}
Description: {transaction.description}
```

---

## Query Flow

1. **User enters search query** (e.g., "grocery shopping")
2. **Backend generates embedding** for the query text
3. **Vector similarity search** finds closest matches
4. **RLS filters results** to user's own transactions
5. **Return ranked results** to frontend

### Example Query

```sql
SELECT 
  t.id,
  t.description,
  t.amount,
  t.date,
  1 - (t.embedding <=> $query_embedding) AS similarity
FROM transaction t
WHERE t.user_id = auth.uid() 
  AND t.deleted_at IS NULL
ORDER BY t.embedding <=> $query_embedding
LIMIT 10;
```

**Operator:** `<=>` is the cosine distance operator in pgvector

---

## RLS Considerations

All semantic search queries must respect RLS:

```sql
-- Always filter by user_id first
WHERE user_id = auth.uid() AND deleted_at IS NULL
-- Then apply vector similarity
ORDER BY embedding <=> $query_embedding
```

This ensures:
- Users only see their own transactions
- Soft-deleted transactions are excluded
- Vector search is scoped to user's data

---

## Performance Tips

1. **Pre-filter before vector search** — Use WHERE clauses to reduce search space
2. **Limit results** — Always use LIMIT to avoid scanning all vectors
3. **Index tuning** — Adjust IVFFlat lists parameter based on data size
4. **Batch embedding generation** — Generate embeddings in background, not inline

### Index Tuning

```sql
-- For ~100K transactions per user
CREATE INDEX transaction_embedding_idx 
ON transaction 
USING ivfflat (embedding vector_cosine_ops)
WITH (lists = 100);
```

**Rule of thumb:** `lists = sqrt(row_count)`

---

## Null Embeddings

Transactions may have `embedding = NULL` if:
- Created before embedding feature was added
- Embedding generation failed temporarily
- Description is empty or too short

**Handling:**
- Background job retries failed embeddings
- Null embeddings are excluded from semantic search
- Fallback to text search if embedding is null

---

## Future Enhancements

1. **Hybrid search** — Combine vector similarity with text matching
2. **Category embeddings** — Semantic search across categories
3. **Invoice embeddings** — Search by invoice content
4. **Personalized embeddings** — Fine-tune on user's transaction patterns
