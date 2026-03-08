"""Quick test of Gemini API"""
import os
import sys
import io

# Fix encoding for Windows console
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Test 1: Check if packages are installed
print("=" * 70)
print("QUICK TEST: Package Import Check")
print("=" * 70)

try:
    import google.generativeai as genai
    print("[OK] google.generativeai imported")
except ImportError as e:
    print(f"[FAIL] Failed to import google.generativeai: {e}")
    sys.exit(1)

try:
    from reportlab.lib.pagesizes import letter
    print("[OK] reportlab imported")
except ImportError as e:
    print(f"[FAIL] Failed to import reportlab: {e}")
    sys.exit(1)

try:
    from PyPDF2 import PdfReader
    print("[OK] PyPDF2 imported")
except ImportError as e:
    print(f"[FAIL] Failed to import PyPDF2: {e}")
    sys.exit(1)

# Test 2: Check API key
print("\n" + "=" * 70)
print("TEST: Gemini API Key")
print("=" * 70)

api_key = os.getenv("GEMINI_API_KEY", "").strip()
if not api_key:
    print("[FAIL] GEMINI_API_KEY not set")
    sys.exit(1)

print(f"[OK] API Key found (first 10 chars: {api_key[:10]}...)")

# Test 3: Initialize Gemini
print("\n" + "=" * 70)
print("TEST: Gemini Service Init")
print("=" * 70)

try:
    genai.configure(api_key=api_key)
    print("[OK] Gemini configured")
except Exception as e:
    print(f"[FAIL] Failed to configure Gemini: {e}")
    sys.exit(1)

# Test 4: Make a simple API call
print("\n" + "=" * 70)
print("TEST: Simple API Call")
print("=" * 70)

try:
    model = genai.GenerativeModel('gemini-pro')
    print("[OK] Model loaded: gemini-pro")
    
    response = model.generate_content("Say 'Hello' briefly in one word")
    print(f"[OK] API call successful")
    print(f"     Response: {response.text[:100]}")
    
except Exception as e:
    print(f"[FAIL] API call failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("[OK] ALL QUICK TESTS PASSED")
print("=" * 70)
