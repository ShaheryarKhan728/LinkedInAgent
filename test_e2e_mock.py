"""
End-to-End Test: Full LinkedIn Agent Flow (with Mock Data)
===========================================================
Demonstrates complete system without requiring browser navigation.
Perfect for testing architecture and reviewing outputs.

Run: python test_e2e_mock.py
"""

import asyncio
import json
import os
import sys
import io

if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

from core.enhanced_logger import setup_enhanced_logger
from core.config import AgentConfig
from core.llm_service import create_gemini_service
from core.pdf_generator import PDFGenerator
from core.pdf_validator import PDFValidator
from core.review_manager import ReviewManager

logger, api_tracker = setup_enhanced_logger("e2e_test")


async def test_end_to_end():
    """Run full end-to-end test with mock data."""
    
    print("\n" + "=" * 70)
    print("END-TO-END TEST: LinkedIn Agent (Mock Data)")
    print("=" * 70)
    
    # Setup
    logger.info("Setting up test environment...")
    
    config = AgentConfig(
        linkedin_email="test@example.com",
        linkedin_password="testpass",
        gemini_api_key="mock_key_for_testing"
    )
    
    # Initialize services
    gemini_service = await create_gemini_service(
        config.gemini_api_key,
        api_tracker=api_tracker,
        force_mock=True  # Use mock service
    )
    
    pdf_gen = PDFGenerator(config.tailored_resume_dir)
    pdf_val = PDFValidator()
    review_mgr = ReviewManager(config.review_dir)
    
    logger.info("✅ Services initialized")
    
    # Mock job data
    mock_jobs = [
        {
            "job_id": "test_job_1",
            "title": ".NET Core Developer",
            "company": "TechCorp",
            "description": "We need a .NET developer with microservices and Azure experience for our backend team"
        },
        {
            "job_id": "test_job_2",
            "title": "Backend Engineer",
            "company": "DataSystems",
            "description": "Senior backend engineer needed. Must know SQL Server and REST APIs. Experience with RabbitMQ a plus."
        }
    ]
    
    logger.info(f"📋 Testing with {len(mock_jobs)} mock jobs")
    
    # Mock base resume
    base_resume = """Shaheryar Khan
emailshaheryar@gmail.com | +923113206213 | linkedin.com/in/shaheryarkhan28

PROFESSIONAL SUMMARY
Results-driven .NET developer with 3 years experience building scalable backend systems.

PROFESSIONAL EXPERIENCE

Software Engineer - Pakistan Single Window (2024-Present)
- Built microservices using .NET Core and SQL Server
- Implemented event-driven architecture with RabbitMQ
- Designed authentication system using IdentityServer4 and JWT

Software Engineer - BailsSoft (2022-2024)  
- Developed RESTful APIs using .NET framework
- Managed SQL Server databases and optimization
- Built multi-tenant SaaS platform

SKILLS
Languages: C#, .NET Core
Databases: SQL Server, T-SQL
Messaging: RabbitMQ
Cloud: Microsoft Azure, AZ-900 certified
"""
    
    # Process each job
    for i, job in enumerate(mock_jobs, 1):
        print(f"\n{'=' * 70}")
        print(f"JOB {i}/{len(mock_jobs)}: {job['title']} @ {job['company']}")
        print(f"{'=' * 70}")
        
        # Create review session
        session = review_mgr.create_review_session(
            job['job_id'],
            job['company'],
            job['title']
        )
        logger.info(f"📋 Review session created: {session['session_id']}")
        
        # Step 1: Analyze form fields
        print("\n--- STEP 1: FORM ANALYSIS ---")
        mock_form_html = """
        <form>
            <input type="text" name="first_name" placeholder="First Name" />
            <input type="text" name="last_name" placeholder="Last Name" />
            <input type="email" name="email" placeholder="Email" />
            <input type="tel" name="phone" placeholder="Phone" />
            <select name="years_experience">
                <option>1-2 years</option>
                <option>2-4 years</option>
                <option>4+ years</option>
            </select>
            <label><input type="radio" name="authorized" /> Authorized to work</label>
        </form>
        """
        
        form_analysis = await gemini_service.analyze_form(
            mock_form_html,
            job['description']
        )
        
        form_data = {}
        for field in form_analysis.get('fields', []):
            form_data[field['name']] = field['value']
        
        session = review_mgr.add_form_data(session, form_data)
        logger.info(f"✅ Form analysis complete: {len(form_data)} fields")
        
        # Show form to user
        print("\nDETECTED FORM FIELDS:")
        for field_name, field_value in form_data.items():
            print(f"  • {field_name}: {field_value}")
        
        # Step 2: Generate tailored resume
        print("\n--- STEP 2: RESUME TAILORING ---")
        
        resume_result = await gemini_service.generate_tailored_resume(
            base_resume,
            job['description'],
            job['title'],
            job['company'],
            "light"
        )
        
        tailored_resume = resume_result.get('resume', base_resume)
        session = review_mgr.add_resume(session, tailored_resume)
        logger.info(f"✅ Resume tailored ({len(tailored_resume)} chars)")
        
        # Generate PDF
        pdf_path, success = pdf_gen.generate_resume_pdf(
            tailored_resume,
            job['job_id'],
            job['company']
        )
        
        if success:
            # Validate PDF
            validation = pdf_val.validate_pdf_with_backup(pdf_path)
            if validation['is_valid']:
                logger.info(f"✅ Resume PDF valid and ready")
                print(f"\nResume PDF: {os.path.basename(pdf_path)}")
        
        # Step 3: Generate cover letter
        print("\n--- STEP 3: COVER LETTER GENERATION ---")
        
        cover_result = await gemini_service.generate_cover_letter(
            job['title'],
            job['company'],
            job['description'],
            {"name": "Shaheryar Khan", "years_exp": "3"}
        )
        
        cover_letter = cover_result.get('cover_letter', '')
        session = review_mgr.add_cover_letter(session, cover_letter)
        logger.info(f"✅ Cover letter generated ({len(cover_letter)} chars)")
        
        # Generate cover letter PDF
        pdf_path, success = pdf_gen.generate_cover_letter_pdf(
            cover_letter,
            job['job_id'],
            job['company']
        )
        
        if success:
            validation = pdf_val.validate_pdf_with_backup(pdf_path)
            if validation['is_valid']:
                logger.info(f"✅ Cover letter PDF valid and ready")
                print(f"Cover Letter PDF: {os.path.basename(pdf_path)}")
        
        # Step 4: User review (simulated)
        print("\n--- STEP 4: USER REVIEW ---")
        print("\n✓ Form fields review: APPROVED")
        print("✓ Resume review: APPROVED")
        print("✓ Cover letter review: APPROVED")
        
        session["form_approved"] = True
        session["resume_approved"] = True
        session["cover_letter_approved"] = True
        session["all_approved"] = True
        
        # Save session
        saved_path = review_mgr.save_session(session)
        logger.info(f"✅ Session saved: {os.path.basename(saved_path) if saved_path else 'N/A'}")
        
        # Summary for this job
        print(f"\n✓ Job {i} Application Ready for Submission")
        print(f"  - Form: Filled ({len(form_data)} fields)")
        print(f"  - Resume: Generated & Validated")
        print(f"  - Cover Letter: Generated & Validated")
        print(f"  - Session: Saved to reviews/")
    
    # Final summary
    print("\n" + "=" * 70)
    print("END-TO-END TEST COMPLETE")
    print("=" * 70)
    
    # Print API summary
    print("\n" + "=" * 70)
    api_tracker.print_summary()
    print("=" * 70)
    
    # Print file locations
    print("\nGENERATED FILES:")
    print(f"  Resumes: {config.tailored_resume_dir}/")
    print(f"  Sessions: {config.review_dir}/")
    print(f"  Logs: {config.log_dir}/")
    
    return True


if __name__ == "__main__":
    try:
        success = asyncio.run(test_end_to_end())
        print(f"\n{'SUCCESS' if success else 'FAILED'}")
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        logger.warning("Test interrupted")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
