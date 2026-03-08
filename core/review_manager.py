"""
Review Manager
==============
Handles user review prompts for form data, resume, and cover letter before submission.
Stores pending/approved reviews as JSON for audit trail.
"""

import json
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger("review_manager")


class ReviewManager:
    """Manage user reviews of application data before submission."""
    
    def __init__(self, review_dir: str = "reviews"):
        self.review_dir = review_dir
        os.makedirs(review_dir, exist_ok=True)
        logger.debug(f"📋 Review Manager initialized. Review dir: {review_dir}")
    
    def create_review_session(self, job_id: str, company: str, job_title: str) -> Dict:
        """
        Create a new review session for a job.
        
        Args:
            job_id: LinkedIn job ID
            company: Company name
            job_title: Job title
        
        Returns:
            Review session dict
        """
        logger.debug(f"📋 Creating review session...")
        logger.debug(f"   Job ID: {job_id}, Company: {company}, Title: {job_title}")
        
        session = {
            "session_id": f"{job_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "job_id": job_id,
            "company": company,
            "job_title": job_title,
            "created_at": datetime.now().isoformat(),
            "form_data": {},
            "form_reviewed": False,
            "form_approved": False,
            "form_notes": "",
            "resume_text": "",
            "resume_reviewed": False,
            "resume_approved": False,
            "resume_notes": "",
            "cover_letter_text": "",
            "cover_letter_reviewed": False,
            "cover_letter_approved": False,
            "cover_letter_notes": "",
            "all_approved": False,
            "submitted": False
        }
        
        logger.info(f"✅ Review session created: {session['session_id']}")
        return session
    
    def add_form_data(self, session: Dict, form_data: Dict) -> Dict:
        """Add form data to review session."""
        logger.debug(f"📝 Adding form data to session: {session['session_id']}")
        logger.debug(f"   Form fields: {len(form_data)} fields")
        session["form_data"] = form_data
        return session
    
    def add_resume(self, session: Dict, resume_text: str) -> Dict:
        """Add resume to review session."""
        logger.debug(f"📄 Adding resume to session: {session['session_id']}")
        logger.debug(f"   Resume length: {len(resume_text)} chars")
        session["resume_text"] = resume_text
        return session
    
    def add_cover_letter(self, session: Dict, cover_letter_text: str) -> Dict:
        """Add cover letter to review session."""
        logger.debug(f"💌 Adding cover letter to session: {session['session_id']}")
        logger.debug(f"   Cover letter length: {len(cover_letter_text)} chars")
        session["cover_letter_text"] = cover_letter_text
        return session
    
    def prompt_form_review(self, session: Dict) -> bool:
        """
        Prompt user to review form data.
        
        Args:
            session: Review session dict
        
        Returns:
            True if approved, False if rejected
        """
        logger.info(f"📋 Prompting user for form review...")
        
        form_data = session.get("form_data", {})
        
        print("\n" + "="*70)
        print("📋  FORM DATA REVIEW")
        print("="*70)
        print(f"Job: {session['job_title']} @ {session['company']}")
        print(f"Job ID: {session['job_id']}")
        print("-"*70)
        print("DETECTED FORM FIELDS:\n")
        
        for field_name, field_value in form_data.items():
            print(f"  • {field_name}: {field_value}")
        
        print("\n" + "-"*70)
        
        while True:
            response = input("❓ Review OK? (yes/no/edit): ").strip().lower()
            
            if response in ["yes", "y"]:
                logger.info(f"✅ Form approved by user")
                session["form_reviewed"] = True
                session["form_approved"] = True
                return True
            
            elif response in ["no", "n"]:
                logger.warning(f"❌ Form rejected by user")
                session["form_reviewed"] = True
                session["form_approved"] = False
                return False
            
            elif response in ["edit", "e"]:
                field_name = input("Edit field name (or 'cancel'): ").strip()
                if field_name.lower() == "cancel":
                    logger.debug(f"Edit cancelled")
                    continue
                
                if field_name in form_data:
                    new_value = input(f"New value for '{field_name}': ").strip()
                    form_data[field_name] = new_value
                    session["form_data"] = form_data
                    logger.debug(f"✏️  Form field updated: {field_name} = {new_value}")
                    
                    # Show updated value
                    print(f"\n✓ Updated: {field_name} = {new_value}\n")
                else:
                    print(f"❌ Field '{field_name}' not found\n")
            
            else:
                print("Invalid response. Please enter: yes, no, or edit\n")
    
    def prompt_resume_review(self, session: Dict) -> bool:
        """
        Prompt user to review tailored resume.
        
        Args:
            session: Review session dict
        
        Returns:
            True if approved, False if rejected
        """
        logger.info(f"📄 Prompting user for resume review...")
        
        resume_text = session.get("resume_text", "")
        
        print("\n" + "="*70)
        print("📄  TAILORED RESUME REVIEW")
        print("="*70)
        print(f"Job: {session['job_title']} @ {session['company']}")
        print(f"Resume Length: {len(resume_text)} chars (~{len(resume_text)//5} words)")
        print("-"*70)
        print("RESUME PREVIEW:\n")
        
        # Show first 80 lines
        resume_lines = resume_text.split('\n')[:80]
        for line in resume_lines:
            print(line)
        
        if len(resume_text.split('\n')) > 80:
            print("\n... [truncated] ...\n")
        
        print("\n" + "-"*70)
        
        while True:
            response = input("❓ Resume Review OK? (yes/no/show-all): ").strip().lower()
            
            if response in ["yes", "y"]:
                logger.info(f"✅ Resume approved by user")
                session["resume_reviewed"] = True
                session["resume_approved"] = True
                return True
            
            elif response in ["no", "n"]:
                logger.warning(f"❌ Resume rejected by user")
                session["resume_reviewed"] = True
                session["resume_approved"] = False
                return False
            
            elif response in ["show-all", "show", "all"]:
                print("\n" + "="*70)
                print("FULL RESUME:")
                print("="*70)
                print(resume_text)
                print("="*70 + "\n")
            
            else:
                print("Invalid response. Please enter: yes, no, or show-all\n")
    
    def prompt_cover_letter_review(self, session: Dict) -> bool:
        """
        Prompt user to review cover letter.
        
        Args:
            session: Review session dict
        
        Returns:
            True if approved, False if rejected
        """
        logger.info(f"💌 Prompting user for cover letter review...")
        
        cover_letter = session.get("cover_letter_text", "")
        
        print("\n" + "="*70)
        print("💌  COVER LETTER REVIEW")
        print("="*70)
        print(f"Job: {session['job_title']} @ {session['company']}")
        print(f"Cover Letter Length: {len(cover_letter)} chars (~{len(cover_letter)//5} words)")
        print("-"*70)
        print("COVER LETTER:\n")
        print(cover_letter)
        print("\n" + "-"*70)
        
        while True:
            response = input("❓ Cover Letter OK? (yes/no): ").strip().lower()
            
            if response in ["yes", "y"]:
                logger.info(f"✅ Cover letter approved by user")
                session["cover_letter_reviewed"] = True
                session["cover_letter_approved"] = True
                return True
            
            elif response in ["no", "n"]:
                logger.warning(f"❌ Cover letter rejected by user")
                session["cover_letter_reviewed"] = True
                session["cover_letter_approved"] = False
                return False
            
            else:
                print("Invalid response. Please enter: yes or no\n")
    
    def check_all_approved(self, session: Dict) -> bool:
        """Check if all reviews are approved."""
        all_approved = (
            session.get("form_approved", False) and
            session.get("resume_approved", False) and
            session.get("cover_letter_approved", False)
        )
        session["all_approved"] = all_approved
        logger.debug(f"🔍 All approved check: {all_approved}")
        return all_approved
    
    def save_session(self, session: Dict) -> str:
        """
        Save review session to JSON file.
        
        Args:
            session: Review session dict
        
        Returns:
            Path to saved file
        """
        logger.debug(f"💾 Saving review session...")
        
        filename = f"session_{session['session_id']}.json"
        filepath = os.path.join(self.review_dir, filename)
        
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(session, f, indent=2, ensure_ascii=False)
            
            file_size = os.path.getsize(filepath)
            logger.info(f"✅ Review session saved: {filename} ({file_size} bytes)")
            logger.debug(f"   Path: {filepath}")
            return filepath
        
        except Exception as e:
            logger.error(f"❌ Error saving review session: {e}")
            return None
    
    def compare_form_fields(self, current_fields: Dict, previous_fields: Dict) -> bool:
        """
        Compare current form fields with previous.
        
        Args:
            current_fields: Current form fields
            previous_fields: Previous form fields
        
        Returns:
            True if identical (skip review), False if different
        """
        are_same = current_fields == previous_fields
        logger.debug(f"📊 Form comparison: {'Same fields' if are_same else 'Different fields'}")
        logger.debug(f"   Current: {len(current_fields)} fields")
        logger.debug(f"   Previous: {len(previous_fields)} fields")
        
        if are_same:
            logger.info(f"✓ Form fields identical to previous job - skipping review")
        else:
            logger.debug(f"   Changes detected")
        
        return are_same
