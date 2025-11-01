---
description: "Generate pytest-style tests for an existing adk agent"
mode: Beast Mode
---

You are writing tests for an existing adk agent in this backend.

Follow ALL rules below. Do not introduce new agents or new endpoints unless explicitly told.

1. Scope of these tests
   - We test ONE of the allowed adk agents:
     - InvoiceAgent
     - RecommendationCoordinatorAgent
     - SearchAgent (AgentTool)
     - FormatterAgent (AgentTool)
   - We DO NOT create or test any other agent.
   - SearchAgent and FormatterAgent are AgentTools used internally by RecommendationCoordinatorAgent. They are not public HTTP surfaces.

2. Imports and structure
   - Use pytest style.
   - Use clear test function names like `test_invoice_agent_valid_invoice()` or `test_recommendation_agent_out_of_scope()`.
   - If the agent depends on Gemini / ADK calls, MOCK those calls.
     - Do NOT perform real network calls.
     - Do NOT require real credentials.
     - Do NOT require Supabase or DB.
   - Always use the most recent version of the Google ADK documentation for mocking patterns if applicable.

3. Auth context (API responsibilities)
   - The FastAPI layer handles Supabase Auth and passes `user_id`, country, currency_preference, etc.
   - In tests, you can simulate those values with safe placeholders like:
     user_id = "demo-user-id"
     country = "GT"
     currency_preference = "GTQ"
   - NEVER include real user data.

4. In-scope vs out-of-scope tests
   - For EVERY agent, you MUST test both:
     a) A valid, in-scope request.
        - Example: InvoiceAgent gets an invoice-like payload (store_name, total_amount, etc.) and returns structured invoice data, including all fields needed to build the canonical multi-line template for `invoice.extracted_text`.
        - Example: RecommendationCoordinatorAgent gets a purchase goal + budget_hint + country, and returns structured recommendations.
     b) An out-of-scope (irrelevant) request.
        - The agent MUST refuse it and return an "out_of_scope" style response WITHOUT calling Gemini / ADK business logic.
        - Assert that behavior.

   - This enforces the rule: "adk agents MUST NOT answer questions outside their domain."

5. Output validation
   - Assert that the agent output matches the expected typed structure.
   - For InvoiceAgent:
     - The output MUST contain everything needed to render:

           Store Name: {store_name}
           Transaction Time: {transaction_time}
           Total Amount: {total_amount}
           Currency: {currency}
           Purchased Items:
           {purchased_items}
           Receipt Image ID: {receipt_id}

     - The test SHOULD verify these keys exist and are well-formed.
   - For RecommendationCoordinatorAgent:
     - The output SHOULD already be "frontend-friendly":
       - structured list of recommended options
       - normalized price strings (including currency)
       - short justification fields
       - budget flags (e.g. "over_budget": true/false)

6. Privacy and logging
   - Assert that the agent does NOT log sensitive data.
   - If logging is part of the agent, capture logs and verify they do NOT include:
     - full invoice image content,
     - personal financial history,
     - Supabase tokens,
     - raw auth headers.

7. Persistence boundary
   - Tests MUST confirm that the agent itself does NOT attempt to write to the database.
   - The agent should instead return structured data and (optionally) comments that persistence will be handled by the API/db layer under RLS.
   - If you see any direct DB calls, flag it as a test failure.

8. No deployment concerns
   - Do NOT assert anything about Cloud Run, container images, or deployment steps.

9. Final output of this prompt
   - Produce ONLY pytest-style test code (plus any necessary fixtures/mocks).
   - Include any helper fixtures for mocking Gemini / ADK calls.
   - Use explicit type hints on helper functions.
   - Use only safe demo data (never real production data or secrets).
