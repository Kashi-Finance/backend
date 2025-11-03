"""
Quick demo script to test the /invoices/ocr endpoint.

This script starts a local server and shows how to make requests to the endpoint.
"""

import uvicorn

if __name__ == "__main__":
    print("=" * 60)
    print("Starting Kashi Finances Backend Demo")
    print("=" * 60)
    print()
    print("📌 API Endpoints:")
    print("   - Health Check:  GET  http://localhost:8000/health")
    print("   - Invoice OCR:   POST http://localhost:8000/invoices/ocr")
    print("   - API Docs:           http://localhost:8000/docs")
    print("   - ReDoc:              http://localhost:8000/redoc")
    print()
    print("🔐 Authentication:")
    print("   All endpoints (except /health) require:")
    print("   Authorization: Bearer <token>")
    print()
    print("📝 Test with curl:")
    print('   curl -X POST "http://localhost:8000/invoices/ocr" \\')
    print('     -H "Authorization: Bearer test-token" \\')
    print('     -F "image=@/path/to/receipt.jpg"')
    print()
    print("=" * 60)
    print("Starting server on http://localhost:8000")
    print("Press Ctrl+C to stop")
    print("=" * 60)
    print()
    
    uvicorn.run(
        "backend.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
