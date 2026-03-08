#!/usr/bin/env python3
"""Test API key with new model: gemini-3.1-flash-lite-preview"""

import asyncio
import google.generativeai as genai
import logging

# Setup logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# API key from environment or user input
API_KEY = "AIzaSyDStKXpDkpDTEZiUwd81H7MmISBWFHKYkg"

async def test_api_key():
    """Test if API key works with new model."""
    print("=" * 60)
    print("🧪 Testing API Key with Model: gemini-3.1-flash-lite-preview")
    print("=" * 60)
    
    try:
        # Configure Gemini
        genai.configure(api_key=API_KEY)
        print("✓ API key configured")
        
        # Try to get model info
        model_name = "gemini-3.1-flash-lite-preview"
        print(f"\n📋 Attempting to use model: {model_name}")
        
        # Try a simple API call
        model = genai.GenerativeModel(model_name)
        response = model.generate_content("Say hello in 10 words.")
        
        print(f"\n✅ SUCCESS! API key works with model {model_name}")
        print(f"📝 Response: {response.text}")
        print(f"\n✓ Model is accessible and responding correctly")
        return True
        
    except Exception as e:
        print(f"\n❌ ERROR: {type(e).__name__}")
        print(f"Details: {str(e)}")
        return False

if __name__ == "__main__":
    result = asyncio.run(test_api_key())
    exit(0 if result else 1)
