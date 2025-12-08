"""
Recommendation System - Web-Grounded LLM Architecture

This module contains the prompt templates for the Gemini-based recommendation system.

Architecture:
- Pattern: Web-Grounded LLM (single API call with Google Search tool)
- Model: Gemini 2.5 Flash (with Google Search grounding)
- Temperature: 0.2 (near-deterministic)
- Output: Structured JSON (via response_schema with Pydantic)

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
