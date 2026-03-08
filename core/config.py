"""
Configuration for the LinkedIn Job Agent.
"""

from dataclasses import dataclass, field
from typing import List

@dataclass
class AgentConfig:
    # LinkedIn credentials (in-memory only, never written to disk)
    linkedin_email: str
    linkedin_password: str
    
    # Gemini API credentials
    gemini_api_key: str = ""

    # Candidate info
    candidate_name: str = "Shaheryar Khan"
    candidate_email: str = "emailshaheryar@gmail.com"
    candidate_phone: str = "+923113206213"
    candidate_linkedin: str = "linkedin.com/in/shaheryarkhan28"
    resume_path: str = "resumes/ShaheryarKhan_Resume.pdf"

    # Search parameters
    target_locations: List[str] = field(default_factory=lambda: ["Pakistan"])
    search_keywords: List[str] = field(default_factory=lambda: [".NET Developer"])
    job_type: str = "remote"
    easy_apply_only: bool = True

    # Safety / rate limiting
    max_jobs_per_session: int = 25
    min_delay_seconds: int = 4
    max_delay_seconds: int = 12

    # Paths
    log_dir: str = "logs"
    output_dir: str = "output"
    tailored_resume_dir: str = "resumes/tailored"
    review_dir: str = "reviews"

    # LLM Configuration
    resume_optimization_level: str = "light"  # "light" or "medium"
    max_api_calls_per_minute: int = 30  # Gemini free tier limit
    
    # Feature flags
    user_review_forms: bool = True        # Always ask user to review forms
    user_review_resume: bool = True       # Always ask user to review resume
    user_review_cover_letter: bool = True # Always ask user to review cover letter
    skip_review_identical_forms: bool = True  # Skip review if form same as previous
