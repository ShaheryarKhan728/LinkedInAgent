"""Test Gemini REST API"""
import asyncio
import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

async def main():
    print("=" * 70)
    print("Testing Gemini REST API")
    print("=" * 70)
    
    # Import
    try:
        from core.gemini_rest import GeminiRestService
        print("[OK] GeminiRestService imported")
    except Exception as e:
        print(f"[FAIL] Import failed: {e}")
        return
    
    # Get API key
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        print("[FAIL] No GEMINI_API_KEY set")
        return
    
    print(f"[OK] API Key: {api_key[:10]}...")
    
    # Initialize
    try:
        service = GeminiRestService(api_key)
        print("[OK] Service initialized")
    except Exception as e:
        print(f"[FAIL] Initialization failed: {e}")
        return
    
    # Test simple call
    print("\n" + "=" * 70)
    print("Test: Simple API Call")
    print("=" * 70)
    
    try:
        result = await service.analyze_question("Do you have .NET experience?", {})
        print(f"[OK] API call successful")
        print(f"     Answer: {result.get('answer')}")
        print(f"     Confidence: {result.get('confidence')}%")
    except Exception as e:
        print(f"[FAIL] API call failed: {e}")
        import traceback
        traceback.print_exc()
    
    print("\n[OK] REST API test complete")

if __name__ == "__main__":
    asyncio.run(main())
