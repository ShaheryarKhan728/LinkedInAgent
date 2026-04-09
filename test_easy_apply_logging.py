"""
Test script to diagnose Easy Apply button clicking issue with aggressive logging
Runs the agent with pre-configured credentials and logs everything
"""

import asyncio
import sys
import os
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.agent import LinkedInJobAgent
from core.config import AgentConfig
from core.enhanced_logger import setup_enhanced_logger
from core.llm_service import create_gemini_service

logger, api_tracker = setup_enhanced_logger("test_logging")

async def test_with_logging():
    """Test the agent with aggressive logging enabled."""
    
    print("\n" + "=" * 70)
    print("TEST: Easy Apply Button Detection with Aggressive Logging")
    print("=" * 70)
    
    # Use saved credentials (from your previous run)
    config = AgentConfig(
        linkedin_email="emailshaheryar@gmail.com",
        linkedin_password="your_password_here",  # REPLACE with your password
        gemini_api_key="AIzaSyA5RV...",  # REPLACE with your API key
        candidate_name="Shaheryar Khan",
        candidate_email="emailshaheryar@gmail.com",
        candidate_phone="+923113206213",
        candidate_linkedin="linkedin.com/in/shaheryarkhan28",
        target_locations=["United States"],
        search_keywords=[".NET Developer"],
        job_type="remote",
        easy_apply_only=True,
        max_jobs_per_session=3,  # Just 3 jobs for this test
        min_delay_seconds=2,
        max_delay_seconds=5,
    )
    
    logger.info("📋 Config loaded")
    logger.info(f"   Email: {config.linkedin_email}")
    logger.info(f"   Keywords: {config.search_keywords}")
    logger.info(f"   Max jobs: {config.max_jobs_per_session}")
    
    # Initialize Gemini
    logger.info("🤖 Initializing Gemini service...")
    config.gemini_service = await create_gemini_service(
        config.gemini_api_key,
        api_tracker=api_tracker,
        force_mock=False
    )
    
    # Run agent
    logger.info("🚀 Starting agent...")
    agent = LinkedInJobAgent(config, api_tracker=api_tracker)
    await agent.run()
    
    logger.info("\n✅ Test completed - Check logs above for Easy Apply button diagnostics")

if __name__ == "__main__":
    # USER MUST EDIT THESE CREDENTIALS IN THIS FILE
    print("""
    ⚠️  IMPORTANT: Edit this script and add your credentials:
    
    Line 23: linkedin_password="your_password_here"
    Line 24: gemini_api_key="AIzaSyA5..."
    
    Then run again.
    """)
    
    # Uncomment to run with your credentials (after editing above)
    # asyncio.run(test_with_logging())
