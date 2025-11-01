"""
Logging utilities for Kashi Finances Backend.

Provides standardized logger configuration following security and privacy rules.

CRITICAL SECURITY RULES:
- NEVER log raw invoice images or binary data
- NEVER log full invoice extracted_text (contains PII and financial data)
- NEVER log personal financial amounts in clear form
- NEVER log Supabase Auth tokens, API keys, or secrets
- NEVER log account balances, card numbers, or PII

Acceptable logging:
- High-level events (e.g., "InvoiceAgent invoked", "OCR completed")
- Non-sensitive metadata (e.g., "store_name='SuperMercado XYZ'")
- Agent orchestration flow (e.g., "RecommendationCoordinatorAgent → SearchAgent")
- Error codes and sanitized error messages (no stack traces with secrets)
"""

import logging
from typing import Optional


def get_logger(name: str, level: Optional[int] = None) -> logging.Logger:
    """
    Get a configured logger for the specified module.
    
    Args:
        name: Module name (typically __name__)
        level: Optional logging level (defaults to INFO)
    
    Returns:
        Configured logger instance
    
    Usage:
        >>> from backend.utils.logging import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("High-level event occurred")
    """
    logger = logging.getLogger(name)
    
    if level is None:
        level = logging.INFO
    
    logger.setLevel(level)
    
    # Add handler if not already configured (avoid duplicate handlers)
    if not logger.handlers:
        handler = logging.StreamHandler()
        formatter = logging.Formatter(
            fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    
    return logger
