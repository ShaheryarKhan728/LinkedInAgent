#!/usr/bin/env python3
"""
Full End-to-End Integration Test with Gemini
============================================
Tests the complete LinkedIn Agent system with Gemini AI integration.
Uses the new model: gemini-3.1-flash-lite-preview
"""

import asyncio
import sys
import json
import os
import io
from pathlib import Path

# Fix Windows console encoding UTF-8
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Setup path for imports
sys.path.insert(0, str(Path(__file__).parent))

from core.enhanced_logger import setup_enhanced_logger
from core.llm_service import create_gemini_service
from core.pdf_generator import PDFGenerator
from core.pdf_validator import PDFValidator
from core.review_manager import ReviewManager
from core.resume_optimizer import ResumeOptimizer


async def test_api_key():
    """Step 1: Test API key connectivity."""
    print("\n" + "=" * 70)
    print("STEP 1: Testing API Key Connectivity")
    print("=" * 70)
    
    api_key = "AIzaSyDStKXpDkpDTEZiUwd81H7MmISBWFHKYkg"
    print(f"API Key: {api_key[:20]}...{api_key[-10:]}")
    
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-3.1-flash-lite-preview")
        response = model.generate_content("Say hello in 5 words.")
        print(f"✅ API Key Valid - Model accessible")
        print(f"   Response: {response.text[:50]}...")
        return True
    except Exception as e:
        print(f"❌ API Key Test Failed: {e}")
        return False


async def test_service_creation():
    """Step 2: Test LLM service initialization."""
    print("\n" + "=" * 70)
    print("STEP 2: Testing LLM Service Initialization")
    print("=" * 70)
    
    api_key = "AIzaSyDStKXpDkpDTEZiUwd81H7MmISBWFHKYkg"
    logger, api_tracker = setup_enhanced_logger("test_integration")
    
    try:
        service = await create_gemini_service(api_key, api_tracker, force_mock=False)
        print(f"✅ Service created: {type(service).__name__}")
        print(f"   Model: {getattr(service, 'model', 'N/A')}")
        return service, logger, api_tracker
    except Exception as e:
        print(f"❌ Service creation failed: {e}")
        return None, logger, api_tracker


async def test_form_analysis(service, logger):
    """Step 3: Test form analysis."""
    print("\n" + "=" * 70)
    print("STEP 3: Testing Form Analysis")
    print("=" * 70)
    
    form_html = """
    <form>
        <input type="text" name="first_name" placeholder="First Name" />
        <input type="text" name="last_name" placeholder="Last Name" />
        <input type="email" name="email" placeholder="Email" />
        <input type="tel" name="phone" placeholder="Phone" />
        <select name="years_exp">
            <option>1-2</option>
            <option>2-3</option>
            <option>3-5</option>
        </select>
        <textarea name="cover_letter" placeholder="Cover Letter"></textarea>
    </form>
    """
    
    job_description = """
    We are looking for a .NET Developer with 2+ years of experience
    in microservices, SQL Server, and REST APIs. Must have experience
    with Azure cloud platforms.
    """
    
    try:
        result = await service.analyze_form(form_html, job_description)
        print(f"✅ Form analysis complete")
        print(f"   Fields detected: {len(result.get('fields', []))}")
        print(f"   Sample fields: {[f['name'] for f in result.get('fields', [])[:3]]}")
        return result
    except Exception as e:
        print(f"❌ Form analysis failed: {e}")
        print(f"   This may be due to API model restrictions")
        return None


async def test_question_analysis(service, logger):
    """Step 4: Test question analysis."""
    print("\n" + "=" * 70)
    print("STEP 4: Testing Question Analysis")
    print("=" * 70)
    
    test_questions = [
        "Do you have experience with .NET Core?",
        "Are you willing to work remote?",
        "Years of experience required: 2-3",
    ]
    
    candidate = {
        "first_name": "Shaheryar",
        "years_exp": "3",
        "willing_remote": True,
    }
    
    try:
        for question in test_questions:
            result = await service.analyze_question(question, candidate)
            answer = result.get("answer", "")
            confidence = result.get("confidence", 0)
            print(f"✅ Q: {question[:40]}...")
            print(f"   A: {answer} (confidence: {confidence}%)")
        return True
    except Exception as e:
        print(f"❌ Question analysis failed: {e}")
        return False


async def test_resume_generation(service, logger, optimizer):
    """Step 5: Test resume tailoring."""
    print("\n" + "=" * 70)
    print("STEP 5: Testing Resume Tailoring")
    print("=" * 70)
    
    # Get base resume from optimizer
    _, base_resume_text = optimizer.create_tailored_resume_text(
        "test_job", "Software Engineer", "TechCorp", 
        "We need .NET expert with microservices experience"
    )
    
    job_description = """
    Senior .NET Developer at TechCorp
    Required: 3+ years C#, .NET Core, microservices, SQL Server
    Nice to have: Azure, RabbitMQ, Docker
    """
    
    try:
        result = await service.generate_tailored_resume(
            base_resume_text, job_description, "Senior Software Engineer", 
            "TechCorp", optimization_level="light"
        )
        tailored = result.get("resume", "")
        print(f"✅ Resume tailoring complete")
        print(f"   Base length: {len(base_resume_text)} chars")
        print(f"   Tailored length: {len(tailored)} chars")
        print(f"   Change: {len(tailored) - len(base_resume_text):+d} chars")
        return tailored
    except Exception as e:
        print(f"❌ Resume generation failed: {e}")
        return None


async def test_cover_letter_generation(service, logger):
    """Step 6: Test cover letter generation."""
    print("\n" + "=" * 70)
    print("STEP 6: Testing Cover Letter Generation")
    print("=" * 70)
    
    job_description = """
    Senior Backend Engineer at DataSystems Corp
    Requirements: 3+ years C#/.NET, microservices, event-driven architecture
    We build high-scale systems for 100K+ users
    """
    
    candidate = {
        "name": "Shaheryar Khan",
        "email": "emailshaheryar@gmail.com",
        "phone": "+923113206213",
        "years_exp": "3",
        "current_company": "Pakistan Single Window",
        "current_title": "Software Engineer",
    }
    
    try:
        result = await service.generate_cover_letter(
            "Senior Backend Engineer", "DataSystems Corp", 
            job_description, candidate
        )
        cover_letter = result.get("cover_letter", "")
        word_count = len(cover_letter.split())
        print(f"✅ Cover letter generation complete")
        print(f"   Length: {len(cover_letter)} chars (~{word_count} words)")
        
        # Show first 200 chars
        preview = cover_letter[:200].replace("\n", " ")
        print(f"   Preview: {preview}...")
        return cover_letter
    except Exception as e:
        print(f"❌ Cover letter generation failed: {e}")
        return None


async def test_pdf_generation(resume_text, cover_letter):
    """Step 7: Test PDF generation."""
    print("\n" + "=" * 70)
    print("STEP 7: Testing PDF Generation")
    print("=" * 70)
    
    try:
        pdf_gen = PDFGenerator("resumes/tailored")
        
        # Generate resume PDF
        resume_pdf = os.path.join("resumes/tailored", "ShaheryarKhan_TechCorp_test.pdf")
        if resume_text:
            pdf_gen.generate_resume_pdf("TechCorp", "test", resume_text)
            print(f"✅ Resume PDF generated: ShaheryarKhan_TechCorp_test.pdf")
        
        # Generate cover letter PDF
        cover_pdf = os.path.join("resumes/tailored", "CoverLetter_TechCorp_test.pdf")
        if cover_letter:
            pdf_gen.generate_cover_letter_pdf("TechCorp", "test", cover_letter)
            print(f"✅ Cover letter PDF generated: CoverLetter_TechCorp_test.pdf")
        
        return True
    except Exception as e:
        print(f"❌ PDF generation failed: {e}")
        return False


async def test_pdf_validation():
    """Step 8: Test PDF validation."""
    print("\n" + "=" * 70)
    print("STEP 8: Testing PDF Validation")
    print("=" * 70)
    
    try:
        validator = PDFValidator()
        
        # Check generated PDFs
        pdf_dir = Path("resumes/tailored")
        for pdf_file in pdf_dir.glob("*.pdf"):
            is_valid, errors = validator.validate_pdf(str(pdf_file))
            status = "✅" if is_valid else "❌"
            print(f"{status} {pdf_file.name}")
            if errors:
                print(f"   Errors: {errors}")
        
        return True
    except Exception as e:
        print(f"❌ PDF validation failed: {e}")
        return False


async def test_review_manager():
    """Step 9: Test review manager."""
    print("\n" + "=" * 70)
    print("STEP 9: Testing Review Manager")
    print("=" * 70)
    
    try:
        rm = ReviewManager()
        
        # Create a review session
        session = rm.create_review_session("job123", "TechCorp", "Software Engineer")
        print(f"✅ Review session created: {session['session_id']}")
        
        # Add data to session (pass session dict, not session_id string)
        rm.add_form_data(session, {
            "first_name": "Shaheryar",
            "last_name": "Khan",
            "email": "emailshaheryar@gmail.com"
        })
        
        rm.add_resume(session, 
                     "This is a tailored resume for TechCorp...")
        
        rm.add_cover_letter(session,
                           "This is a cover letter for the role...")
        
        print(f"✅ Session data added successfully")
        print(f"   Form fields: 3")
        print(f"   Resume: Added")
        print(f"   Cover letter: Added")
        
        return True
    except Exception as e:
        print(f"❌ Review manager test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """Run all integration tests."""
    print("\n")
    print("=" * 70)
    print(" " * 15 + "FULL GEMINI INTEGRATION TEST")
    print(" " * 10 + "Model: gemini-3.1-flash-lite-preview")
    print("=" * 70)
    
    results = {}
    
    # 1. API Key test
    results["API Key"] = await test_api_key()
    if not results["API Key"]:
        print("\n❌ STOPPING: API key test failed")
        return results
    
    # 2. Service creation
    service, logger, api_tracker = await test_service_creation()
    results["Service Creation"] = service is not None
    if not service:
        print("\n❌ STOPPING: Could not create service")
        return results
    
    # 3. Form analysis
    results["Form Analysis"] = await test_form_analysis(service, logger) is not None
    
    # 4. Question analysis
    results["Question Analysis"] = await test_question_analysis(service, logger)
    
    # 5. Resume generation
    optimizer = ResumeOptimizer()
    resume_text = await test_resume_generation(service, logger, optimizer)
    results["Resume Generation"] = resume_text is not None
    
    # 6. Cover letter generation
    cover_letter = await test_cover_letter_generation(service, logger)
    results["Cover Letter Generation"] = cover_letter is not None
    
    # 7. PDF generation
    results["PDF Generation"] = await test_pdf_generation(resume_text, cover_letter)
    
    # 8. PDF validation
    results["PDF Validation"] = await test_pdf_validation()
    
    # 9. Review manager
    results["Review Manager"] = await test_review_manager()
    
    # Results summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name:25s}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    # API usage
    if api_tracker:
        print(f"\n" + "=" * 70)
        print("API CALL SUMMARY")
        print("=" * 70)
        api_tracker.print_summary()
    
    print("\n" + "=" * 70)
    if passed == total:
        print("✅ ALL TESTS PASSED!")
        print("=" * 70 + "\n")
        return 0
    else:
        print(f"❌ {total - passed} TEST(S) FAILED")
        print("=" * 70 + "\n")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
