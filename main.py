"""
LinkedIn Job Application Agent
================================
Autonomously finds .NET Developer remote jobs and applies via LinkedIn Easy Apply.
Run this on your LOCAL machine. Credentials are entered securely at runtime.
"""

import asyncio
import getpass
import sys
from core.agent import LinkedInJobAgent
from core.config import AgentConfig
from core.logger import setup_logger

logger = setup_logger("main")

def print_banner():
    print("""
╔══════════════════════════════════════════════════════════════╗
║         LinkedIn Job Application Agent v1.0                 ║
║         .NET Developer | Remote | EU / SG / US              ║
╚══════════════════════════════════════════════════════════════╝
    """)

def get_credentials():
    """Securely collect LinkedIn credentials at runtime — never stored."""
    print("🔐 Enter your LinkedIn credentials (not stored anywhere):\n")
    email = input("   LinkedIn Email: ").strip()
    password = getpass.getpass("   LinkedIn Password: ")
    return email, password

async def main():
    print_banner()

    # Collect credentials securely
    email, password = get_credentials()

    # Load config
    config = AgentConfig(
        linkedin_email=email,
        linkedin_password=password,
        resume_path="resumes/ShaheryarKhan_Resume.pdf",
        candidate_name="Shaheryar Khan",
        candidate_email="emailshaheryar@gmail.com",
        candidate_phone="+923113206213",
        candidate_linkedin="linkedin.com/in/shaheryarkhan28",
        # target_locations=["Europe", "Singapore", "United States"],
        target_locations=["United States"],
        search_keywords=[
            ".NET Developer",
            ".NET Core Developer",
            "C# Developer",
            "Backend .NET Engineer",
            "Software Engineer .NET",
        ],
        # experience_filter="3",       # LinkedIn: 2 = Mid-Senior
        job_type="remote",
        easy_apply_only=True,
        max_jobs_per_session=25,     # Safe daily limit to avoid flagging
        min_delay_seconds=4,
        max_delay_seconds=12,
    )

    # Run the agent
    agent = LinkedInJobAgent(config)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
