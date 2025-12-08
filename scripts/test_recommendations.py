#!/usr/bin/env python3
"""
Recommendation System Test Script

This script allows you to test the recommendation system locally without
deploying to Cloud Run or using the mobile app.

The recommendation system uses Gemini with Google Search grounding,
so all product recommendations come from real, current web data.

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
    # Map countries to locales
    country_locales = {
        "GT": "es-GT",
        "MX": "es-MX",
        "SV": "es-SV",
        "US": "en-US",
        "CA": "en-CA",
        "GB": "en-GB",
        "BR": "pt-BR",
    }
    locale = country_locales.get(country, f"es-{country}")
    
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.data = [{
        "country": country,
        "currency_preference": currency,
        "locale": locale
    }]
    
    mock_client.table.return_value.select.return_value.eq.return_value.execute.return_value = mock_response
    
    return mock_client


def print_result(result):
    """Pretty print the recommendation result."""
    print("\n" + "=" * 60)
    print(f"STATUS: {result.status}")
    print("=" * 60)
    
    if isinstance(result, RecommendationQueryResponseOK):
        print(f"\n✅ Found {len(result.results_for_user)} recommendation(s) (web-grounded):\n")
        
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
    
    # Check if Google API key is configured
    if not os.getenv("GOOGLE_API_KEY"):
        print("\n⚠️  ERROR: GOOGLE_API_KEY environment variable not set!")
        print("   Please set it in your .env file or export it:")
        print("   export GOOGLE_API_KEY=your-gemini-api-key")
        print("\n   Get your API key at: https://aistudio.google.com/app/apikey")
        return
    
    print("\n" + "=" * 60)
    print("RECOMMENDATION SYSTEM TEST (Gemini with Google Search)")
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
    print("\nCalling Gemini API (with Google Search grounding)...")
    
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
        # =================================================================
        # BASIC QUERIES
        # =================================================================
        {
            "name": "Basic laptop query (Spanish/Guatemala)",
            "query": "laptop para diseño gráfico",
            "budget": 7000,
            "country": "GT",
            "currency": "GTQ",
        },
        {
            "name": "Basic headphones query",
            "query": "audífonos bluetooth",
            "budget": 600,
            "country": "GT",
            "currency": "GTQ",
        },
        
        # =================================================================
        # CONFLICTING QUERY AND USER_NOTE
        # =================================================================
        {
            "name": "CONFLICT: Gaming laptop query + No gamer design note",
            "query": "laptop gaming potente con buena tarjeta gráfica",
            "budget": 10000,
            "country": "GT",
            "currency": "GTQ",
            "note": "No quiero diseño gamer con luces RGB, prefiero algo sobrio para oficina. Necesito que sea potente pero elegante.",
        },
        {
            "name": "CONFLICT: Budget query + Premium expectations",
            "query": "laptop barata económica",
            "budget": 8000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Que tenga mínimo 32GB RAM, SSD de 1TB, pantalla 4K y procesador i9 o Ryzen 9",
        },
        
        # =================================================================
        # SPECIFIC BRAND PREFERENCES
        # =================================================================
        {
            "name": "BRAND: Lenovo ThinkPad or Dell XPS preference",
            "query": "laptop para programación y desarrollo de software",
            "budget": 12000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Prefiero marcas empresariales como Lenovo ThinkPad o Dell XPS. No HP consumer ni Acer. Buena durabilidad y teclado cómodo para escribir mucho código.",
        },
        {
            "name": "BRAND: Apple ecosystem preference",
            "query": "auriculares inalámbricos premium",
            "budget": 3000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Tengo iPhone y Mac, prefiero algo compatible con el ecosistema Apple. AirPods o Beats idealmente.",
        },
        {
            "name": "BRAND: Sony or Bose preference for audio",
            "query": "audífonos con cancelación de ruido",
            "budget": 4000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Solo marcas reconocidas en audio: Sony, Bose, o Sennheiser. No quiero marcas genéricas chinas.",
        },
        
        # =================================================================
        # NEGATIVE CONSTRAINTS (Things to avoid)
        # =================================================================
        {
            "name": "NEGATIVE: No earbuds, only over-ear",
            "query": "audífonos inalámbricos para escuchar música",
            "budget": 1500,
            "country": "GT",
            "currency": "GTQ",
            "note": "NO quiero earbuds ni in-ear, SOLO audífonos over-ear que cubran toda la oreja. Me duelen los oídos con los pequeños.",
        },
        {
            "name": "NEGATIVE: No RGB, no gamer aesthetic",
            "query": "teclado mecánico para oficina",
            "budget": 800,
            "country": "GT",
            "currency": "GTQ",
            "note": "NO luces RGB, NO diseño gamer. Necesito algo sobrio y profesional para oficina. Color negro o gris preferiblemente.",
        },
        {
            "name": "NEGATIVE: No Chinese unknown brands",
            "query": "cargador portátil power bank",
            "budget": 500,
            "country": "GT",
            "currency": "GTQ",
            "note": "NO marcas chinas desconocidas como Anker, Baseus, etc. Prefiero Samsung, Apple, o Sony por seguridad.",
        },
        
        # =================================================================
        # USE CASE CONTEXT
        # =================================================================
        {
            "name": "USE CASE: Design work - color accuracy",
            "query": "monitor para computadora",
            "budget": 4000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Es para trabajo de diseño gráfico y edición de fotos profesional. Necesito excelente reproducción de colores, mínimo 100% sRGB, idealmente Adobe RGB. Panel IPS o mejor. No necesita ser gamer, no me importa el refresh rate alto.",
        },
        {
            "name": "USE CASE: Gift for woman - elegant smartwatch",
            "query": "smartwatch",
            "budget": 3000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Es para regalo de cumpleaños de mi esposa (35 años). Debe verse elegante y femenino, no muy deportivo ni grande. Compatibilidad con iPhone es importante. Colores dorado, rosado o blanco ideales.",
        },
        {
            "name": "USE CASE: Student laptop - portable and long battery",
            "query": "laptop para estudiante universitario",
            "budget": 5000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Mi hija va a empezar la universidad. Necesita algo liviano para llevar a clases todos los días, buena batería (mínimo 8 horas), pantalla no muy pequeña para estudiar. Va a estudiar administración de empresas, no necesita algo muy potente.",
        },
        {
            "name": "USE CASE: Home office setup",
            "query": "webcam para videoconferencias",
            "budget": 800,
            "country": "GT",
            "currency": "GTQ",
            "note": "Trabajo desde casa y tengo reuniones en Zoom/Teams todo el día. Necesito buena calidad de video, mínimo 1080p, buena iluminación en condiciones de poca luz, y que tenga buen micrófono integrado.",
        },
        
        # =================================================================
        # URGENCY AND AVAILABILITY CONSTRAINTS
        # =================================================================
        {
            "name": "URGENCY: Need today/tomorrow",
            "query": "impresora láser",
            "budget": 2500,
            "country": "GT",
            "currency": "GTQ",
            "store": "Intelaf",
            "note": "La necesito URGENTE, tiene que estar disponible para recoger HOY o mañana máximo. Preferiblemente en zona 10 o zona 15 de Guatemala. Es para la oficina, solo blanco y negro está bien.",
        },
        {
            "name": "URGENCY: Last minute gift",
            "query": "bocina bluetooth portátil",
            "budget": 1000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Es regalo de último minuto, necesito algo que pueda comprar hoy mismo. Resistente al agua sería ideal porque es para alguien que va a la playa.",
        },
        
        # =================================================================
        # CONTRADICTORY BUDGET EXPECTATIONS
        # =================================================================
        {
            "name": "BUDGET IMPOSSIBLE: iPhone Pro Max with Q500",
            "query": "iPhone 15 Pro Max nuevo sellado",
            "budget": 500,
            "country": "GT",
            "currency": "GTQ",
            "note": "Tiene que ser nuevo, sellado, con garantía Apple oficial. No reacondicionado ni usado.",
        },
        {
            "name": "BUDGET IMPOSSIBLE: MacBook Pro with Q2000",
            "query": "MacBook Pro M3 nuevo",
            "budget": 2000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Para programación, necesito el de 14 pulgadas mínimo con 16GB RAM.",
        },
        {
            "name": "BUDGET IMPOSSIBLE: Professional camera with Q1000",
            "query": "cámara profesional full frame para fotografía",
            "budget": 1000,
            "country": "GT",
            "currency": "GTQ",
            "note": "Necesito cuerpo y lente, Sony Alpha o Canon EOS R. Nueva con garantía.",
        },
        
        # =================================================================
        # MULTIPLE LOCALES AND LANGUAGES
        # =================================================================
        {
            "name": "LOCALE: US English - laptop for coding",
            "query": "laptop for software development and coding",
            "budget": 1500,
            "country": "US",
            "currency": "USD",
            "note": "Need good keyboard, at least 16GB RAM, SSD. Linux compatible preferred.",
        },
        {
            "name": "LOCALE: US English - wireless headphones",
            "query": "wireless noise cancelling headphones",
            "budget": 350,
            "country": "US",
            "currency": "USD",
            "note": "For office use, comfortable for 8+ hours, good for video calls.",
        },
        {
            "name": "LOCALE: Mexico Spanish - smartphone",
            "query": "celular con buena cámara para fotos",
            "budget": 8000,
            "country": "MX",
            "currency": "MXN",
            "note": "Me gusta tomar muchas fotos, la cámara es lo más importante. No me importa tanto el procesador.",
        },
        {
            "name": "LOCALE: Brazil Portuguese - tablet",
            "query": "tablet para estudar e assistir vídeos",
            "budget": 2000,
            "country": "BR",
            "currency": "BRL",
            "note": "Para minha filha de 12 anos usar na escola. Precisa ser resistente.",
        },
        
        # =================================================================
        # PROHIBITED / OUT OF SCOPE (Expect NO_VALID_OPTION)
        # =================================================================
        {
            "name": "PROHIBITED: Weapons",
            "query": "pistola 9mm para defensa personal",
            "budget": 5000,
            "country": "GT",
            "currency": "GTQ",
        },
        {
            "name": "OUT OF SCOPE: Personal advice",
            "query": "consejos para superar una ruptura amorosa",
            "budget": 1000,
            "country": "GT",
            "currency": "GTQ",
        },
        {
            "name": "OUT OF SCOPE: Medical advice",
            "query": "medicamento para el dolor de cabeza fuerte",
            "budget": 500,
            "country": "GT",
            "currency": "GTQ",
        },
        
        # =================================================================
        # VERY LOW BUDGET (Expect NO_VALID_OPTION with helpful message)
        # =================================================================
        {
            "name": "LOW BUDGET: Laptop for Q100",
            "query": "laptop nueva",
            "budget": 100,
            "country": "GT",
            "currency": "GTQ",
        },
        {
            "name": "LOW BUDGET: Smartphone for Q50",
            "query": "smartphone nuevo con garantía",
            "budget": 50,
            "country": "GT",
            "currency": "GTQ",
        },
    ]
    
    print("\n" + "=" * 70)
    print("COMPREHENSIVE RECOMMENDATION SYSTEM TEST SUITE")
    print("=" * 70)
    print(f"Total tests: {len(test_cases)}")
    print("Using REAL Gemini API with Google Search grounding")
    print("=" * 70)
    
    results = []
    passed = 0
    failed = 0
    
    for i, test in enumerate(test_cases, 1):
        print(f"\n\n{'#' * 70}")
        print(f"# TEST {i}/{len(test_cases)}: {test['name']}")
        print(f"{'#' * 70}")
        
        result = await run_test(
            query=test["query"],
            budget=test.get("budget"),
            country=test.get("country", "GT"),
            currency=test.get("currency", "GTQ"),
            store=test.get("store"),
            note=test.get("note"),
        )
        
        # Determine expected result based on test category
        test_name = test["name"]
        expected_no_valid = any(keyword in test_name for keyword in [
            "PROHIBITED", "OUT OF SCOPE", "LOW BUDGET", "BUDGET IMPOSSIBLE"
        ])
        
        if result:
            actual_status = result.status
            if expected_no_valid:
                # We expect NO_VALID_OPTION for these
                test_passed = actual_status == "NO_VALID_OPTION"
            else:
                # We expect OK for regular queries
                test_passed = actual_status == "OK"
            
            if test_passed:
                passed += 1
            else:
                failed += 1
            
            results.append({
                "name": test["name"],
                "status": actual_status,
                "expected": "NO_VALID_OPTION" if expected_no_valid else "OK",
                "passed": test_passed,
            })
        else:
            failed += 1
            results.append({
                "name": test["name"],
                "status": "ERROR",
                "expected": "NO_VALID_OPTION" if expected_no_valid else "OK",
                "passed": False,
            })
        
        # Delay between tests to avoid rate limits
        print("\n⏳ Waiting 2 seconds before next test...")
        await asyncio.sleep(2)
    
    # Print summary
    print("\n\n" + "=" * 70)
    print("TEST SUITE SUMMARY")
    print("=" * 70)
    print(f"Total: {len(test_cases)} | Passed: {passed} | Failed: {failed}")
    print("=" * 70)
    
    # Group results by category
    categories = {}
    for r in results:
        # Extract category from test name
        if ":" in r["name"]:
            category = r["name"].split(":")[0]
        else:
            category = "BASIC"
        
        if category not in categories:
            categories[category] = []
        categories[category].append(r)
    
    for category, tests in categories.items():
        print(f"\n📁 {category}")
        for r in tests:
            if r["passed"]:
                icon = "✅"
            else:
                icon = "❌"
            
            test_name = r["name"].split(": ", 1)[-1] if ": " in r["name"] else r["name"]
            print(f"   {icon} {test_name}")
            print(f"      Status: {r['status']} (expected: {r['expected']})")
    
    print("\n" + "=" * 70)
    if failed == 0:
        print("🎉 ALL TESTS PASSED!")
    else:
        print(f"⚠️  {failed} TESTS FAILED - Review results above")
    print("=" * 70 + "\n")


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
