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

    # Candidate info
    candidate_name: str
    candidate_email: str
    candidate_phone: str
    candidate_linkedin: str
    resume_path: str

    # Search parameters
    target_locations: List[str] = field(default_factory=lambda: ["United States"])
    search_keywords: List[str] = field(default_factory=lambda: [".NET Developer"])
    # experience_filter: str = "2"   # LinkedIn experience level code
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
