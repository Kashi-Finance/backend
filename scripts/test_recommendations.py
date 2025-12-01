#!/usr/bin/env python3
"""
Recommendation System Test Script

This script allows you to test the recommendation system locally without
deploying to Cloud Run or using the mobile app.

Usage:
    python scripts/test_recommendations.py
    python scripts/test_recommendations.py --query "laptop para diseño" --budget 7000
    python scripts/test_recommendations.py --query "auriculares gaming" --budget 500 --country GT

For more details, see: docs/testing/recommendation-local-testing.md
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from decimal import Decimal
from typing import Optional
from unittest.mock import MagicMock

# Add the project root to the path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env file if it exists
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # dotenv not installed, rely on environment variables

from backend.services.recommendation_service import query_recommendations
from backend.schemas.recommendations import (
    RecommendationQueryResponseOK,
    RecommendationQueryResponseNoValidOption,
)


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def create_mock_supabase_client(country: str = "GT", currency: str = "GTQ") -> MagicMock:
    """
    Create a mock Supabase client that returns a default user profile.
    
    This allows testing without a real Supabase connection.
    """
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{
        "country": country,
        "currency_preference": currency,
        "locale": f"es-{country}" if country != "US" else "en-US"
    }]
    
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    return mock_client


def print_result(result):
    """Pretty print the recommendation result."""
    print("\n" + "=" * 60)
    print(f"STATUS: {result.status}")
    print("=" * 60)
    
    if isinstance(result, RecommendationQueryResponseOK):
        print(f"\n✅ Found {len(result.results_for_user)} recommendation(s):\n")
        
        for i, product in enumerate(result.results_for_user, 1):
            print(f"--- Product #{i} ---")
            print(f"  Title:     {product.product_title}")
            print(f"  Price:     {product.price_total}")
            print(f"  Seller:    {product.seller_name}")
            print(f"  URL:       {product.url}")
            print(f"  Pickup:    {'Yes' if product.pickup_available else 'No'}")
            print(f"  Warranty:  {product.warranty_info}")
            print(f"  Copy:      {product.copy_for_user}")
            print(f"  Badges:    {', '.join(product.badges)}")
            print()
    
    elif isinstance(result, RecommendationQueryResponseNoValidOption):
        print(f"\n❌ No valid options found")
        print(f"  Reason: {result.reason}\n")


async def run_test(
    query: str,
    budget: Optional[float] = None,
    country: str = "GT",
    currency: str = "GTQ",
    store: Optional[str] = None,
    note: Optional[str] = None,
    user_id: str = "test-user-123"
):
    """Run a single recommendation test."""
    
    # Check if DeepSeek API key is configured
    if not os.getenv("DEEPSEEK_API_KEY"):
        print("\n⚠️  ERROR: DEEPSEEK_API_KEY environment variable not set!")
        print("   Please set it in your .env file or export it:")
        print("   export DEEPSEEK_API_KEY=sk-your-key")
        return
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION SYSTEM TEST")
    print("=" * 60)
    print(f"\nQuery:    {query}")
    if budget:
        print(f"Budget:   {budget} {currency}")
    print(f"Country:  {country}")
    print(f"Currency: {currency}")
    if store:
        print(f"Store:    {store}")
    if note:
        print(f"Note:     {note}")
    print("\nCalling DeepSeek API...")
    
    # Create mock Supabase client
    mock_client = create_mock_supabase_client(country, currency)
    
    # Call the recommendation service
    result = await query_recommendations(
        supabase_client=mock_client,
        user_id=user_id,
        query_raw=query,
        budget_hint=Decimal(str(budget)) if budget else None,
        preferred_store=store,
        user_note=note,
    )
    
    # Print the result
    print_result(result)
    
    return result


async def run_test_suite():
    """Run a suite of predefined test cases."""
    
    test_cases = [
        {
            "name": "Basic laptop query",
            "query": "laptop para diseño gráfico",
            "budget": 7000,
            "note": "nada gamer con luces RGB"
        },
        {
            "name": "Budget headphones",
            "query": "auriculares inalámbricos",
            "budget": 500,
        },
        {
            "name": "Very low budget (expect NO_VALID_OPTION)",
            "query": "laptop gaming profesional",
            "budget": 100,
        },
        {
            "name": "Out of scope query (expect NO_VALID_OPTION)",
            "query": "consejos para mejorar mi vida personal",
            "budget": 1000,
        },
        {
            "name": "Smartphone with store preference",
            "query": "smartphone con buena cámara",
            "budget": 3000,
            "store": "iShop"
        }
    ]
    
    print("\n" + "=" * 60)
    print("RUNNING TEST SUITE")
    print(f"Total tests: {len(test_cases)}")
    print("=" * 60)
    
    results = []
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n\n{'#' * 60}")
        print(f"# TEST {i}/{len(test_cases)}: {test['name']}")
        print(f"{'#' * 60}")
        
        result = await run_test(
            query=test["query"],
            budget=test.get("budget"),
            store=test.get("store"),
            note=test.get("note"),
        )
        
        results.append({
            "name": test["name"],
            "status": result.status if result else "ERROR",
        })
        
        # Small delay between tests to avoid rate limits
        await asyncio.sleep(1)
    
    # Print summary
    print("\n\n" + "=" * 60)
    print("TEST SUITE SUMMARY")
    print("=" * 60)
    
    for r in results:
        status_icon = "✅" if r["status"] == "OK" else "❌" if r["status"] == "NO_VALID_OPTION" else "⚠️"
        print(f"{status_icon} {r['name']}: {r['status']}")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Test the recommendation system locally",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run a single query
  python scripts/test_recommendations.py --query "laptop para diseño" --budget 7000
  
  # Run with all options
  python scripts/test_recommendations.py \\
    --query "laptop para editar videos" \\
    --budget 8000 \\
    --country GT \\
    --currency GTQ \\
    --store "TecnoMundo" \\
    --note "nada gamer con luces RGB"
  
  # Run the full test suite
  python scripts/test_recommendations.py --suite
        """
    )
    
    parser.add_argument(
        "--query", "-q",
        type=str,
        help="Product query (e.g., 'laptop para diseño gráfico')"
    )
    parser.add_argument(
        "--budget", "-b",
        type=float,
        help="Maximum budget in local currency"
    )
    parser.add_argument(
        "--country", "-c",
        type=str,
        default="GT",
        help="Country code (default: GT)"
    )
    parser.add_argument(
        "--currency",
        type=str,
        default="GTQ",
        help="Currency code (default: GTQ)"
    )
    parser.add_argument(
        "--store", "-s",
        type=str,
        help="Preferred store (optional)"
    )
    parser.add_argument(
        "--note", "-n",
        type=str,
        help="User preferences/constraints (optional)"
    )
    parser.add_argument(
        "--suite",
        action="store_true",
        help="Run the full test suite"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Enable debug logging"
    )
    
    args = parser.parse_args()
    
    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)
    
    if args.suite:
        asyncio.run(run_test_suite())
    elif args.query:
        asyncio.run(run_test(
            query=args.query,
            budget=args.budget,
            country=args.country,
            currency=args.currency,
            store=args.store,
            note=args.note,
        ))
    else:
        # Run with default query if no arguments provided
        print("\nNo query provided. Running default test...\n")
        asyncio.run(run_test(
            query="laptop para diseño gráfico bajo Q7000",
            budget=7000,
            note="nada gamer con luces RGB"
        ))


if __name__ == "__main__":
    main()
