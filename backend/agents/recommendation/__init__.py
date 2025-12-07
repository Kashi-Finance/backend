"""
Recommendation System - Prompt Chaining Architecture

This module contains the prompt templates for the Prompt Chaining recommendation system.

Architecture:
- Pattern: Prompt Chaining (single LLM call)
- Model: Perplexity Sonar (with native web grounding)
- Temperature: 0.2 (near-deterministic)
- Output: Structured JSON

The service layer is in:
- backend/services/recommendation_service.py

Prompt templates are in:
- backend/agents/recommendation/prompts.py
"""

from backend.agents.recommendation.prompts import (
    RECOMMENDATION_SYSTEM_PROMPT,
    build_recommendation_user_prompt,
)

__all__ = [
    "RECOMMENDATION_SYSTEM_PROMPT",
    "build_recommendation_user_prompt",
]
