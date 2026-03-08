"""
Resume Optimizer
=================
Analyzes job descriptions and tailors the resume with ATS-friendly keywords.
Uses the candidate's actual experience — no fabrication.
"""

import os
import re
import json
import logging
from pathlib import Path
from typing import Dict, List, Tuple

logger = logging.getLogger("resume_optimizer")

# ── Shaheryar's verified skill inventory (from resume) ──────────────────────
CANDIDATE_SKILLS = {
    "languages":      ["C#", ".NET", ".NET Core", "LINQ", "ADO.NET"],
    "frameworks":     ["ASP.NET MVC", "ASP.NET Core", "Web API", "Entity Framework Core",
                       "Dapper", "SignalR", "Worker Service"],
    "architecture":   ["Microservices", "REST", "RESTful APIs", "Distributed Systems",
                       "Design Patterns", "Repository Pattern", "Factory Pattern",
                       "Strategy Pattern", "Singleton Pattern", "CQRS"],
    "auth":           ["IdentityServer4", "OpenID Connect", "JWT", "OAuth2", "RBAC",
                       "Role-Based Access Control"],
    "messaging":      ["RabbitMQ", "Dead Letter Queue", "DLQ", "Message Queue", "Event-Driven"],
    "gateway":        ["Ocelot API Gateway", "API Gateway"],
    "database":       ["SQL Server", "MS SQL Server", "Stored Procedures", "T-SQL"],
    "frontend":       ["React", "ReactJS", "HTML5", "DevExtreme"],
    "cloud":          ["Microsoft Azure", "Azure", "AZ-900"],
    "devops":         ["Jenkins", "CI/CD", "GitHub", "GitLab", "Git"],
    "tools":          ["Postman", "Roslyn", "Git CLI"],
    "methodologies":  ["Agile", "Scrum", "SaaS", "Multi-tenant", "L3 Support", "Production Support"],
}

# Flat set for quick lookup
ALL_CANDIDATE_SKILLS = {s.lower() for skills in CANDIDATE_SKILLS.values() for s in skills}

# ── Base resume text template (from Shaheryar's resume) ─────────────────────
BASE_RESUME = """Shaheryar Khan
emailshaheryar@gmail.com | +923113206213 | linkedin.com/in/shaheryarkhan28 | github.com/ShaheryarKhan728

PROFESSIONAL SUMMARY
{summary}

PROFESSIONAL EXPERIENCE

Software Engineer — Pakistan Single Window (PSW)                          Mar 2024 – Present
• Built a role-based announcement service using .NET Core, SignalR, and SQL Server,
  delivering real-time notifications to 100K+ users.
• Implemented workflow-driven document routing using .NET Core Worker Service, Workflow
  Engine, and SQL Server, automating approvals — reducing manual processing by 90% and
  cutting turnaround time by 70%.
• Designed a distributed transaction mechanism across .NET microservices, persisting
  execution checkpoints to ensure consistency and reducing debugging effort by 60%.
• Provided L3 production support in a .NET microservices environment with SQL Server and
  RabbitMQ, resolving critical issues and maintaining high availability.
• Implemented authentication and authorization using IdentityServer4, OpenID Connect, and
  JWT policies, enforcing access control and securing APIs.
• Configured RabbitMQ Dead Letter Queues (DLQ) with retry handling, reducing message
  loss by 90% and improving system reliability.
• Developed external integration via Ocelot API Gateway and .NET Core REST services,
  enabling interoperability between distributed systems.

Software Engineer — BailsSoft                                             Dec 2022 – Feb 2024
• Developed RESTful APIs and SQL Server Stored Procedures (.NET) to generate analytics
  datasets, improving reporting performance by 40%.
• Built responsive frontend components using DevExtreme and HTML5, optimizing rendering
  and reducing load times by 35%.
• Implemented custom authorization middleware in .NET to enforce RBAC and secure endpoints.
• Contributed to a multi-tenant SaaS fintech platform (.NET, SQL Server) in an Agile
  environment, enhancing core modules and system scalability for 6+ clients.

PROJECTS

Requirement Traceability & Impact Analysis Tool
Developed a CLI-based analysis tool using .NET, C#, Roslyn, and Git CLI to map requirements
to commits, files, and methods. Implemented static code analysis, hotspot detection, and
automated report generation (HTML/JSON/CSV).

External Party Bridge System
Secure communication bridge using .NET Core and SQL Server, with comprehensive logging,
retry mechanisms, and fault handling for high-volume transaction processing.

Automated Attendance System
Eliminated missed employee check-ins by automating attendance based on office entry during
work hours — improving accuracy and reducing administrative overhead.

EDUCATION
Bachelor of Computer Science — UBIT, University of Karachi               2020 – 2023

CERTIFICATIONS
Microsoft Certified: Azure Fundamentals (AZ-900) | Credential: 19094B79B3B22636

SKILLS
Languages & Frameworks: C#, .NET Core, ASP.NET MVC, Web API, Entity Framework Core, Dapper, LINQ, ADO.NET
Architecture: Microservices, Distributed Systems, REST APIs, API Gateway, Event-Driven Architecture, Design Patterns
Messaging & Auth: RabbitMQ, IdentityServer4, JWT, OpenID Connect, OAuth2, RBAC
Database: MS SQL Server, Stored Procedures, T-SQL
Frontend: ReactJS, HTML5, DevExtreme
Cloud & DevOps: Microsoft Azure (AZ-900), Jenkins CI/CD, GitHub, GitLab, Git, Postman
"""


class ResumeOptimizer:
    def __init__(self, output_dir: str = "resumes/tailored", gemini_service=None):
        self.output_dir = output_dir
        self.gemini_service = gemini_service
        os.makedirs(output_dir, exist_ok=True)
        if gemini_service:
            logger.info(f"✓ ResumeOptimizer initialized with Gemini service")
        else:
            logger.info(f"✓ ResumeOptimizer initialized (regex-based mode)")

    def extract_keywords_from_jd(self, job_title: str, job_description: str) -> Dict[str, List[str]]:
        """Extract relevant keywords from job description that match candidate skills."""
        jd_lower = job_description.lower()
        matched = {"found": [], "missing_but_capable": []}

        # Check which of our skills appear in the JD
        for category, skills in CANDIDATE_SKILLS.items():
            for skill in skills:
                if skill.lower() in jd_lower:
                    matched["found"].append(skill)

        # Extract additional JD keywords to naturally weave in
        extra_patterns = [
            r'\bclean architecture\b', r'\bddd\b', r'\bdomain.driven\b',
            r'\bkubernetes\b', r'\bdocker\b', r'\bazure service bus\b',
            r'\bkafka\b', r'\bgrpc\b', r'\bgraphql\b', r'\bsolid\b',
            r'\bunit test\b', r'\bxunit\b', r'\bnunit\b', r'\bmoq\b',
            r'\blazor\b', r'\bminimal api\b', r'\b\.net 6\b', r'\b\.net 7\b',
            r'\b\.net 8\b', r'\bef core\b', r'\bazure devops\b',
        ]

        jd_extras = []
        for pat in extra_patterns:
            if re.search(pat, jd_lower):
                jd_extras.append(re.sub(r'\\b', '', pat).strip())

        matched["jd_extras"] = jd_extras
        return matched

    def generate_summary(self, job_title: str, keywords: Dict) -> str:
        """Generate a tailored professional summary for the job."""
        found = keywords.get("found", [])
        extras = keywords.get("jd_extras", [])

        # Pick top 5 most relevant skills to highlight
        highlight = found[:5] if found else [".NET Core", "Microservices", "SQL Server", "REST APIs", "C#"]

        summary = (
            f"Results-driven .NET Software Engineer with 2+ years of hands-on experience building "
            f"scalable, distributed backend systems using {', '.join(highlight[:3])}. "
            f"Proven track record delivering high-availability microservices, event-driven architectures "
            f"with RabbitMQ, and secure APIs with JWT/OpenID Connect for enterprise-grade platforms "
            f"serving 100K+ users. Experienced in Agile environments, production support (L3), "
            f"and multi-tenant SaaS development. Microsoft Azure certified (AZ-900)."
        )
        return summary

    def create_tailored_resume_text(self, job_id: str, job_title: str,
                                    company: str, job_description: str) -> Tuple[str, str]:
        """Create a tailored resume text for a specific job."""
        keywords = self.extract_keywords_from_jd(job_title, job_description)
        summary = self.generate_summary(job_title, keywords)
        resume_text = BASE_RESUME.format(summary=summary)

        # Save as text file (PDF generation requires local libraries)
        safe_company = re.sub(r'[^\w]', '_', company)[:30]
        filename = f"ShaheryarKhan_{safe_company}_{job_id}.txt"
        filepath = os.path.join(self.output_dir, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(resume_text)

        logger.info(f"✅ Tailored resume saved: {filename}")
        logger.info(f"   Matched keywords: {keywords['found'][:8]}")

        return filepath, resume_text

    def generate_cover_letter(self, job_title: str, company: str,
                               job_description: str) -> str:
        """Generate a tailored cover letter for the job."""
        keywords = self.extract_keywords_from_jd(job_title, job_description)
        top_skills = keywords["found"][:4] if keywords["found"] else [".NET Core", "Microservices", "SQL Server"]

        cover_letter = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. With over 2 years of professional experience building production-grade .NET Core applications, I am confident in my ability to contribute meaningfully to your team from day one.

In my current role at Pakistan Single Window, I designed and delivered a microservices-based real-time notification system serving 100,000+ users using .NET Core, SignalR, and SQL Server. I also built distributed transaction mechanisms and implemented end-to-end authentication pipelines using IdentityServer4, JWT, and OpenID Connect — ensuring both system reliability and security at scale.

Your requirement for expertise in {', '.join(top_skills)} aligns closely with my core competencies. I have hands-on production experience with these technologies, including RabbitMQ-based event-driven communication, Ocelot API Gateway integrations, and Worker Service-based workflow automation — skills I developed while supporting enterprise clients in high-throughput environments.

What excites me most about this opportunity is the chance to work remotely with a globally distributed team while solving complex backend challenges. I thrive in Agile environments and have a consistent track record of delivering measurable outcomes: 90% reduction in manual processing, 70% faster turnaround times, and 60% reduction in debugging overhead.

I would welcome the opportunity to discuss how my background and passion for clean, scalable .NET architecture can add value to {company}.

Thank you for your time and consideration.

Best regards,
Shaheryar Khan
emailshaheryar@gmail.com | +923113206213
linkedin.com/in/shaheryarkhan28
"""
        return cover_letter
    
    # ───────────────────────────────────────────────────────────────────────
    # Async Gemini-powered methods
    # ───────────────────────────────────────────────────────────────────────
    async def create_tailored_resume_gemini(self, job_id: str, job_title: str,
                                           company: str, job_description: str,
                                           base_resume_text: str,
                                           optimization_level: str = "light") -> Tuple[str, str]:
        """
        Create Gemini-tailored resume with both text and PDF output.
        
        Args:
            job_id, job_title, company, job_description: Job details
            base_resume_text: The base resume text to tailor
            optimization_level: "light" (keywords only) or "medium" (reorder + keywords)
        
        Returns:
            (filepath_to_text_file, tailored_resume_text)
        """
        try:
            logger.debug(f"🔄 Calling Gemini to tailor resume...")
            
            # Call Gemini to tailor the resume
            result = await self.gemini_service.generate_tailored_resume(
                base_resume_text, job_description, job_title, company,
                optimization_level=optimization_level
            )
            
            tailored_resume = result.get("resume", base_resume_text)
            logger.info(f"✅ Gemini-tailored resume generated ({len(tailored_resume)} chars)")
            
            # Save tailored resume text
            safe_company = re.sub(r'[^\w]', '_', company)[:30]
            filename = f"ShaheryarKhan_{safe_company}_{job_id}_GEMINI.txt"
            filepath = os.path.join(self.output_dir, filename)
            
            with open(filepath, "w", encoding="utf-8") as f:
                f.write(tailored_resume)
            
            logger.info(f"✅ Saved: {filename}")
            logger.debug(f"   Length: {len(tailored_resume)} chars")
            
            return filepath, tailored_resume
        
        except Exception as e:
            logger.error(f"❌ Gemini resume tailoring failed: {e}")
            logger.debug(f"   Falling back to regex-based resume")
            return self.create_tailored_resume_text(job_id, job_title, company, job_description)
    
    async def generate_cover_letter_gemini(self, job_title: str, company: str,
                                          job_description: str) -> str:
        """
        Generate Gemini-tailored cover letter.
        
        Args:
            job_title, company, job_description: Job details
        
        Returns:
            Cover letter text (200-250 words)
        """
        try:
            logger.debug(f"🔄 Calling Gemini to generate cover letter...")
            
            candidate_info = {
                "name": "Shaheryar Khan",
                "email": "emailshaheryar@gmail.com",
                "phone": "+923113206213",
                "years_exp": "3",
                "current_company": "Pakistan Single Window",
                "current_title": "Software Engineer",
            }
            
            result = await self.gemini_service.generate_cover_letter(
                job_title, company, job_description, candidate_info
            )
            
            cover_letter = result.get("cover_letter", "")
            if not cover_letter:
                logger.warning(f"⚠️  Gemini returned empty cover letter")
                return self.generate_cover_letter(job_title, company, job_description)
            
            logger.info(f"✅ Gemini cover letter generated ({len(cover_letter)} chars)")
            logger.debug(f"   Approximately {len(cover_letter) // 5} words")
            
            return cover_letter
        
        except Exception as e:
            logger.error(f"❌ Gemini cover letter generation failed: {e}")
            logger.debug(f"   Falling back to template-based cover letter")
            return self.generate_cover_letter(job_title, company, job_description)
