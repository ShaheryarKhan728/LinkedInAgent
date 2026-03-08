"""
Test Script for Gemini LLM Integration
=======================================
Tests all new modules and Gemini API integration before running main agent.
Run this to verify setup before launching the full agent.
"""

import asyncio
import json
import sys
import os
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.enhanced_logger import setup_enhanced_logger, APICallTracker
from core.llm_service import GeminiService
from core.pdf_generator import PDFGenerator
from core.pdf_validator import PDFValidator
from core.review_manager import ReviewManager

logger, api_tracker = setup_enhanced_logger("test_gemini")


async def test_gemini_service():
    """Test Gemini service with provided API key."""
    logger.info("="*70)
    logger.info("TEST 1: Gemini Service Configuration")
    logger.info("="*70)
    
    # Get API key from environment or user
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    
    if not api_key:
        print("\n❌ GEMINI_API_KEY environment variable not set")
        print("   Set it with: export GEMINI_API_KEY='your_key_here'")
        print("   Or pass it as: GEMINI_API_KEY='key' python test_gemini.py")
        logger.error("API key not provided")
        return False
    
    logger.info(f"✅ API Key configured (first 10 chars: {api_key[:10]}...)")
    
    try:
        gemini = GeminiService(api_key, api_tracker=api_tracker, max_calls_per_minute=30)
        logger.info(f"✅ Gemini service initialized")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini: {e}")
        return False


async def test_question_analysis(gemini_service):
    """Test question analysis."""
    logger.info("\n" + "="*70)
    logger.info("TEST 2: Question Analysis")
    logger.info("="*70)
    
    test_questions = [
        "Do you have experience with .NET Core?",
        "How many years of experience do you have?",
        "Are you willing to work remote?",
    ]
    
    try:
        for question in test_questions:
            logger.info(f"\nAnalyzing: {question}")
            result = await gemini_service.analyze_question(question, {})
            logger.info(f"✅ Answer: {result.get('answer')} (confidence: {result.get('confidence')}%)")
            logger.debug(f"   Reasoning: {result.get('reasoning', 'N/A')}")
        
        return True
    except Exception as e:
        logger.error(f"❌ Question analysis failed: {e}")
        return False


async def test_form_analysis(gemini_service):
    """Test form analysis."""
    logger.info("\n" + "="*70)
    logger.info("TEST 3: Form Analysis")
    logger.info("="*70)
    
    sample_form_html = """
    <form>
        <input type="text" name="first_name" placeholder="First Name" />
        <input type="text" name="last_name" placeholder="Last Name" />
        <input type="email" name="email" placeholder="Email" />
        <input type="tel" name="phone" placeholder="Phone" />
        <select name="experience">
            <option>1-2 years</option>
            <option>2-4 years</option>
            <option>4+ years</option>
        </select>
        <label><input type="checkbox" name="authorized" /> Authorized to work</label>
    </form>
    """
    
    sample_job_desc = ".NET Core developer with 3+ years experience needed. Must have SQL Server knowledge."
    
    try:
        logger.info("Analyzing sample form...")
        result = await gemini_service.analyze_form(sample_form_html, sample_job_desc)
        
        fields = result.get('fields', [])
        logger.info(f"✅ Form analysis complete: {len(fields)} fields detected")
        
        for field in fields[:3]:
            logger.info(f"   • {field.get('name')}: {field.get('value')} (confidence: {field.get('confidence')}%)")
        
        return True
    except Exception as e:
        logger.error(f"❌ Form analysis failed: {e}")
        logger.debug(f"   Exception: {str(e)}")
        return False


async def test_resume_generation(gemini_service):
    """Test resume tailoring."""
    logger.info("\n" + "="*70)
    logger.info("TEST 4: Resume Tailoring")
    logger.info("="*70)
    
    base_resume = """Shaheryar Khan
emailshaheryar@gmail.com | linkedin.com/in/shaheryarkhan28

PROFESSIONAL SUMMARY
Software engineer with 3 years experience

PROFESSIONAL EXPERIENCE
Software Engineer — Pakistan Single Window
• Built microservices using .NET Core
• Managed SQL Server databases
• Implemented REST APIs

SKILLS
Languages: C#, .NET Core
Database: SQL Server
"""
    
    job_desc = "Need .NET Core developer with microservices and Azure experience"
    
    try:
        logger.info("Generating tailored resume...")
        result = await gemini_service.generate_tailored_resume(
            base_resume, 
            job_desc,
            ".NET Developer",
            "Test Company",
            "light"
        )
        
        if result.get('error'):
            logger.error(f"❌ Resume generation failed: {result.get('error')}")
            return False
        
        resume = result.get('resume', '')
        logger.info(f"✅ Resume tailored ({len(resume)} chars)")
        logger.debug(f"   Preview: {resume[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ Resume tailoring failed: {e}")
        return False


async def test_cover_letter_generation(gemini_service):
    """Test cover letter generation."""
    logger.info("\n" + "="*70)
    logger.info("TEST 5: Cover Letter Generation")
    logger.info("="*70)
    
    job_desc = "Seeking Senior .NET Developer with 5 years experience in microservices"
    
    try:
        logger.info("Generating cover letter...")
        result = await gemini_service.generate_cover_letter(
            ".NET Developer",
            "Tech Company Inc",
            job_desc,
            {"name": "Shaheryar Khan", "years_exp": "3"}
        )
        
        if result.get('error'):
            logger.error(f"❌ Cover letter generation failed: {result.get('error')}")
            return False
        
        cover = result.get('cover_letter', '')
        logger.info(f"✅ Cover letter generated ({len(cover)} chars, ~{len(cover)//5} words)")
        logger.debug(f"   Preview: {cover[:200]}...")
        
        return True
    except Exception as e:
        logger.error(f"❌ Cover letter generation failed: {e}")
        return False


def test_pdf_generator():
    """Test PDF generation."""
    logger.info("\n" + "="*70)
    logger.info("TEST 6: PDF Generation")
    logger.info("="*70)
    
    try:
        gen = PDFGenerator("test_output")
        logger.info("✅ PDF Generator initialized")
        
        # Test resume PDF
        sample_resume = """Shaheryar Khan
Software Engineer

EXPERIENCE
Built microservices using .NET Core and SQL Server.

SKILLS
C#, .NET Core, SQL Server, RabbitMQ
"""
        
        logger.info("Generating test resume PDF...")
        path, success = gen.generate_resume_pdf(sample_resume, "test_job_1", "Test Company")
        
        if success:
            logger.info(f"✅ Resume PDF created: {path}")
            if os.path.exists(path):
                size = os.path.getsize(path)
                logger.debug(f"   File size: {size} bytes")
        else:
            logger.error(f"❌ Resume PDF generation failed")
            return False
        
        # Test cover letter PDF
        sample_letter = """Dear Hiring Manager,

I am writing to express my interest in the Software Engineer position.

Best regards,
Shaheryar Khan"""
        
        logger.info("Generating test cover letter PDF...")
        path, success = gen.generate_cover_letter_pdf(sample_letter, "test_job_1", "Test Company")
        
        if success:
            logger.info(f"✅ Cover letter PDF created: {path}")
        else:
            logger.error(f"❌ Cover letter PDF generation failed")
            return False
        
        return True
    except Exception as e:
        logger.error(f"❌ PDF generation failed: {e}")
        return False


def test_pdf_validator():
    """Test PDF validation."""
    logger.info("\n" + "="*70)
    logger.info("TEST 7: PDF Validation")
    logger.info("="*70)
    
    try:
        validator = PDFValidator(max_size_mb=5.0, max_pages=2)
        logger.info("✅ PDF Validator initialized")
        
        # Find a test PDF
        test_pdfs = list(Path("test_output").glob("*.pdf"))
        
        if test_pdfs:
            test_pdf = str(test_pdfs[0])
            logger.info(f"Validating: {test_pdf}")
            is_valid, errors = validator.validate_pdf(test_pdf)
            
            if is_valid:
                logger.info(f"✅ PDF is valid")
            else:
                logger.warning(f"⚠️  PDF validation issues: {errors}")
            
            return True
        else:
            logger.warning("⚠️  No test PDFs found to validate")
            return True
    except Exception as e:
        logger.error(f"❌ PDF validation failed: {e}")
        return False


def test_review_manager():
    """Test review manager."""
    logger.info("\n" + "="*70)
    logger.info("TEST 8: Review Manager")
    logger.info("="*70)
    
    try:
        rm = ReviewManager("test_reviews")
        logger.info("✅ Review Manager initialized")
        
        # Create a session
        session = rm.create_review_session("job_123", "Test Company", "Software Engineer")
        logger.info(f"✅ Review session created: {session['session_id']}")
        
        # Add data
        session = rm.add_form_data(session, {"name": "Shaheryar", "email": "test@email.com"})
        session = rm.add_resume(session, "Sample resume text...")
        session = rm.add_cover_letter(session, "Sample cover letter...")
        logger.info(f"✅ Session data added")
        
        # Save session
        saved_path = rm.save_session(session)
        if saved_path and os.path.exists(saved_path):
            logger.info(f"✅ Session saved: {saved_path}")
            return True
        else:
            logger.error(f"❌ Session not saved")
            return False
    
    except Exception as e:
        logger.error(f"❌ Review manager test failed: {e}")
        return False


async def main():
    """Run all tests."""
    print("\n" + "="*70)
    print("🧪 GEMINI LLM INTEGRATION TEST SUITE")
    print("="*70)
    
    results = {}
    
    # Test 1: Gemini service init
    results["Gemini Init"] = await test_gemini_service()
    
    if not results["Gemini Init"]:
        logger.error("\n❌ Gemini API not configured. Cannot continue tests.")
        return results
    
    # Initialize Gemini for remaining tests
    api_key = os.getenv("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.error("API key not available")
        return results
    
    gemini = GeminiService(api_key, api_tracker=api_tracker)
    
    # Test 2-5: LLM tests
    results["Question Analysis"] = await test_question_analysis(gemini)
    results["Form Analysis"] = await test_form_analysis(gemini)
    results["Resume Tailoring"] = await test_resume_generation(gemini)
    results["Cover Letter"] = await test_cover_letter_generation(gemini)
    
    # Test 6-8: Non-LLM tests
    results["PDF Generation"] = test_pdf_generator()
    results["PDF Validation"] = test_pdf_validator()
    results["Review Manager"] = test_review_manager()
    
    # Print summary
    print("\n" + "="*70)
    print("📊 TEST SUMMARY")
    print("="*70)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<30} {status}")
    
    all_passed = all(results.values())
    
    print("="*70)
    if all_passed:
        print("✅ All tests passed! Ready to run main agent.")
    else:
        print("❌ Some tests failed. Fix issues before running main agent.")
    
    # Print API summary
    print("\n")
    api_tracker.print_summary()
    
    return all_passed


if __name__ == "__main__":
    try:
        all_passed = asyncio.run(main())
        sys.exit(0 if all_passed else 1)
    except KeyboardInterrupt:
        logger.warning("⛔ Tests interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"💥 Test suite failed: {e}")
        raise
