"""
LinkedIn Job Application Agent with Gemini LLM Integration
===========================================================
Autonomously finds .NET Developer remote jobs and applies via LinkedIn Easy Apply.
Uses Google Gemini to intelligently fill forms, tailor resumes, and generate cover letters.
Run this on your LOCAL machine. Credentials are entered securely at runtime.
"""

import asyncio
import getpass
import sys
from core.agent import LinkedInJobAgent
from core.config import AgentConfig
from core.enhanced_logger import setup_enhanced_logger

logger, api_tracker = setup_enhanced_logger("main")

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║    LinkedIn Job Application Agent v2.0 (Gemini-Powered)      ║
║    .NET Developer | Remote | with AI Resume Tailoring        ║
╚══════════════════════════════════════════════════════════════╝
    """)

def get_credentials():
    """Securely collect LinkedIn credentials at runtime — never stored."""
    print("🔐 Enter your LinkedIn credentials (not stored anywhere):\n")
    email = input("   LinkedIn Email: ").strip()
    password = getpass.getpass("   LinkedIn Password: ")
    return email, password

def get_gemini_api_key():
    """Get Gemini API key for LLM features."""
    print("\n🔑 Google Gemini API Key")
    print("   Get one from: https://aistudio.google.com/app/apikeys")
    key = getpass.getpass("   Gemini API Key (hidden): ").strip()
    
    if not key:
        logger.error("❌ Gemini API key is required for LLM features")
        sys.exit(1)
    
    logger.info(f"✅ Gemini API key configured (first 10 chars: {key[:10]}...)")
    return key

async def main():
    print_banner()
    logger.info("🚀 LinkedIn Agent starting with Gemini LLM integration...")

    # Collect credentials securely
    email, password = get_credentials()
    gemini_key = get_gemini_api_key()

    # Load config
    config = AgentConfig(
        linkedin_email=email,
        linkedin_password=password,
        gemini_api_key=gemini_key,
        resume_path="resumes/ShaheryarKhan_Resume.pdf",
        candidate_name="Shaheryar Khan",
        candidate_email="emailshaheryar@gmail.com",
        candidate_phone="+923113206213",
        candidate_linkedin="linkedin.com/in/shaheryarkhan28",
        target_locations=["Pakistan"],
        search_keywords=[
            ".NET Developer",
            ".NET Core Developer",
            "C# Developer",
            "Backend .NET Engineer",
            "Software Engineer .NET",
        ],
        job_type="remote",
        easy_apply_only=True,
        max_jobs_per_session=25,
        min_delay_seconds=4,
        max_delay_seconds=12,
        resume_optimization_level="light",  # "light" or "medium"
        user_review_forms=True,
        user_review_resume=True,
        user_review_cover_letter=True,
    )

    logger.debug(f"📋 Config loaded:")
    logger.debug(f"   Email: {email}")
    logger.debug(f"   Target locations: {config.target_locations}")
    logger.debug(f"   Search keywords: {config.search_keywords}")
    logger.debug(f"   Max jobs: {config.max_jobs_per_session}")
    logger.debug(f"   Resume optimization: {config.resume_optimization_level}")

    # Initialize Gemini service
    from core.llm_service import create_gemini_service
    logger.debug(f"🤖 Initializing Gemini service...")
    config.gemini_service = await create_gemini_service(
        gemini_key, 
        api_tracker=api_tracker,
        force_mock=False  # Set to True to use mock service for testing
    )
    
    # Run the agent
    agent = LinkedInJobAgent(config, api_tracker=api_tracker)
    await agent.run()
    
    # Print API usage summary
    print("\n")
    api_tracker.print_summary()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.warning("⛔ Agent interrupted by user")
        sys.exit(0)
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        raise
