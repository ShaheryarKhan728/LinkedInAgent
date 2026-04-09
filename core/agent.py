"""
LinkedIn Job Agent — Main Orchestrator (v4 - Gemini-Powered)
=============================================================
Coordinates: Login → Job Search → Gemini Analysis → Resume Tailoring → Easy Apply → Review → Logging

NEW IN v4:
- Gemini LLM integration for intelligent form analysis and field mapping
- AI-powered resume tailoring (light or medium optimization)
- AI-generated contextual cover letters
- User review layer for form, resume, and cover letter before submission
- Aggressive logging with API call tracking
- Smart form field comparison to skip reviews for identical jobs
"""

import asyncio
import logging
import random
import os
from datetime import datetime

from playwright.async_api import (
    async_playwright, Browser, BrowserContext, Page,
    TimeoutError as PlaywrightTimeout,
    Error as PlaywrightError,
)

from core.config import AgentConfig
from core.job_scraper import LinkedInJobScraper, JobListing
from core.easy_apply_handler import EasyApplyHandler
from core.resume_optimizer import ResumeOptimizer
from core.tracker import ApplicationTracker
from core.enhanced_logger import setup_enhanced_logger
from core.llm_service import GeminiService
from core.pdf_generator import PDFGenerator
from core.pdf_validator import PDFValidator
from core.review_manager import ReviewManager

logger, api_tracker = setup_enhanced_logger("agent")

# Max seconds to spend on a single job before giving up and moving on
PER_JOB_TIMEOUT = 180  # Increased to 180s for LLM + PDF generation


class LinkedInJobAgent:
    def __init__(self, config: AgentConfig, api_tracker=None):
        self.config = config
        self.api_tracker = api_tracker
        self.tracker = ApplicationTracker(config.output_dir)
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)
        self.gemini_service = GeminiService(
            config.gemini_api_key,
            api_tracker=api_tracker,
            max_calls_per_minute=config.max_api_calls_per_minute
        )
        self.pdf_generator = PDFGenerator(config.tailored_resume_dir)
        self.pdf_validator = PDFValidator(max_size_mb=5.0, max_pages=2)
        self.review_manager = ReviewManager(config.review_dir)
        
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None
        self.last_form_data = {}  # Track previous form for comparison
        
        logger.debug(f"🤖 Agent initialized with Gemini LLM service")
        logger.debug(f"   API tracker: {'Active' if api_tracker else 'Inactive'}")
        logger.debug(f"   Resume optimization: {config.resume_optimization_level}")

    async def _delay(self, min_s=None, max_s=None):
        lo = min_s or self.config.min_delay_seconds
        hi = max_s or self.config.max_delay_seconds
        delay = random.uniform(lo, hi)
        logger.debug(f"Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)

    # ─────────────────────────────────────────────────────────────────────────
    # Page health & recovery
    # ─────────────────────────────────────────────────────────────────────────
    async def _is_page_alive(self) -> bool:
        """Check if the current page is still usable."""
        if self.page is None:
            return False
        try:
            await self.page.evaluate("() => document.title")
            return True
        except Exception:
            return False

    async def _recover_page(self):
        """
        Create a fresh page in the existing browser context.
        Called when a page crashes or becomes unresponsive.
        Does NOT re-login — the session cookie is preserved in the context.
        """
        logger.warning("🔄 Page crashed or unresponsive — recovering...")
        try:
            if self.page and not self.page.is_closed():
                await self.page.close()
        except Exception:
            pass

        try:
            self.page = await self.context.new_page()
            logger.info("✅ Fresh page created. Session preserved.")
        except Exception as e:
            logger.error(f"❌ Could not create new page: {e}")
            # Last resort: restart entire browser
            await self._restart_browser()

    async def _restart_browser(self):
        """Full browser restart — only used if page recovery fails."""
        logger.warning("🔄 Restarting browser entirely...")
        try:
            await self.browser.close()
        except Exception:
            pass
        pw_instance = getattr(self, '_pw', None)
        if pw_instance:
            self.browser = await pw_instance.chromium.launch(**self._browser_args())
            self.context = await self.browser.new_context(**self._context_args())
            self.page = await self.context.new_page()
            logger.info("✅ Browser restarted. You may need to re-login if session was lost.")

    def _browser_args(self) -> dict:
        return dict(
            headless=False,
            slow_mo=30,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-gpu",
                "--disable-infobars",
                "--window-size=1366,768",
            ]
        )

    def _context_args(self) -> dict:
        return dict(
            viewport={"width": 1366, "height": 768},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            locale="en-US",
            timezone_id="Asia/Karachi",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    # ─────────────────────────────────────────────────────────────────────────
    # Safe navigation helper
    # ─────────────────────────────────────────────────────────────────────────
    async def _safe_goto(self, url: str, timeout: int = 25000) -> bool:
        """
        Navigate to URL safely.
        Uses domcontentloaded (NOT networkidle — LinkedIn never goes idle).
        Returns True on success, False on timeout/error.
        Automatically recovers page on crash.
        """
        for attempt in range(2):
            try:
                if not await self._is_page_alive():
                    await self._recover_page()

                await self.page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=timeout
                )
                # Short explicit settle — replaces networkidle
                await asyncio.sleep(random.uniform(2.5, 4.0))
                return True

            except PlaywrightTimeout:
                logger.warning(f"   ⏱️  Navigation timeout (attempt {attempt+1}): {url}")
                await self._recover_page()
                await asyncio.sleep(3)

            except PlaywrightError as e:
                err = str(e)
                if "closed" in err or "destroyed" in err or "detached" in err:
                    logger.warning(f"   💀 Page closed/detached — recovering...")
                    await self._recover_page()
                    await asyncio.sleep(3)
                else:
                    logger.error(f"   Navigation error: {e}")
                    return False

            except Exception as e:
                logger.error(f"   Unexpected navigation error: {e}")
                return False

        logger.error(f"   ❌ Navigation failed after retries: {url}")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Main run loop
    # ─────────────────────────────────────────────────────────────────────────
    async def run(self):
        """Main agent execution flow."""
        logger.info("🚀 Agent starting...")
        os.makedirs(self.config.tailored_resume_dir, exist_ok=True)

        async with async_playwright() as pw:
            self._pw = pw  # Store for potential browser restart

            self.browser = await pw.chromium.launch(**self._browser_args())
            self.context = await self.browser.new_context(**self._context_args())
            self.page = await self.context.new_page()

            # ── Step 1: Login ─────────────────────────────────────────────
            logged_in = await self._login()
            if not logged_in:
                logger.error("❌ Login failed. Aborting.")
                await self.browser.close()
                return

            await self._delay(3, 6)

            # ── Step 2: Find Jobs ─────────────────────────────────────────
            scraper = LinkedInJobScraper(self.page, self.config)
            jobs = await scraper.find_jobs()

            if not jobs:
                logger.warning("⚠️  No jobs found. Try different keywords or check your login.")
                await self.browser.close()
                return

            logger.info(f"\n🎯 Found {len(jobs)} jobs. Starting applications...\n")

            # ── Step 3: Apply — each job has its own timeout + recovery ───
            logger.info(f"🔧 Initializing EasyApplyHandler...")
            logger.info(f"   Gemini service: {self.gemini_service is not None} ({type(self.gemini_service).__name__ if self.gemini_service else 'None'})")
            logger.info(f"   Review manager: {self.review_manager is not None}")
            handler = EasyApplyHandler(
                self.page, 
                self.config,
                gemini_service=self.gemini_service,
                review_manager=self.review_manager
            )
            logger.info(f"✅ EasyApplyHandler initialized with Gemini service")
            applied_count = 0

            for i, job in enumerate(jobs, 1):
                logger.info(f"\n[{i}/{len(jobs)}] Processing: {job.title} @ {job.company}")

                # Sync handler's page reference in case it was recovered
                handler.page = self.page

                try:
                    # Wrap entire job in a timeout — one stuck job won't kill others
                    success = await asyncio.wait_for(
                        self._process_one_job(job, scraper, handler),
                        timeout=PER_JOB_TIMEOUT
                    )

                    if success:
                        job.apply_status = "applied"
                        applied_count += 1
                        logger.info(f"✅ [{applied_count}] Applied successfully!")
                    else:
                        job.apply_status = "failed"
                        logger.warning("⚠️  Application failed or skipped")

                except asyncio.TimeoutError:
                    job.apply_status = "failed"
                    job.error = f"Per-job timeout ({PER_JOB_TIMEOUT}s exceeded)"
                    logger.warning(f"⏱️  Job timed out after {PER_JOB_TIMEOUT}s — moving on")
                    await self._recover_page()

                except Exception as e:
                    job.apply_status = "failed"
                    job.error = str(e)[:200]
                    logger.error(f"❌ Unexpected error: {e}")
                    # Recover page so next job can proceed
                    if not await self._is_page_alive():
                        await self._recover_page()

                finally:
                    resume_path = os.path.join(
                        self.config.tailored_resume_dir,
                        f"ShaheryarKhan_{job.job_id}.txt"
                    )
                    self.tracker.log_application(job, resume_path)
                    # Sync page ref again after potential recovery
                    handler.page = self.page
                    scraper.page = self.page

                if i < len(jobs):
                    await self._delay()

            # ── Step 4: Summary ───────────────────────────────────────────
            self.tracker.print_summary(jobs)
            await self.browser.close()
            logger.info("🏁 Agent finished.")

    async def _process_one_job(self, job: JobListing,
                                scraper: LinkedInJobScraper,
                                handler: EasyApplyHandler) -> bool:
        """
        Process a single job: navigate → fetch JD → apply.
        Isolated so per-job timeout wraps everything cleanly.
        """
        logger.info(f"   📄 Navigating to job page: {job.url}")
        nav_ok = await self._safe_goto(job.url)
        if not nav_ok:
            logger.warning(f"   ⚠️  Could not load job page: {job.url}")
            return False

        # Dump page HTML for diagnostics
        try:
            page_title = await self.page.title()
            logger.debug(f"   Page title: {page_title}")
            
            # Check if Easy Apply button is visible
            easy_apply_btn = await self.page.query_selector("#jobs-apply-button-id")
            if easy_apply_btn:
                logger.info(f"   ✓ Easy Apply button IS present on page")
            else:
                logger.warning(f"   ⚠️  Easy Apply button NOT found by ID selector")
            
            # Get page HTML for diagnostics
            html = await self.page.content()
            html_length = len(html)
            logger.debug(f"   Page HTML length: {html_length} characters")
            
            # Log snippet of HTML around Easy Apply button
            if "jobs-apply-button" in html:
                idx = html.find("jobs-apply-button")
                snippet = html[max(0, idx-200):idx+500]
                logger.debug(f"   Easy Apply button HTML snippet:")
                logger.debug(f"   {snippet}")
            else:
                logger.warning(f"   ⚠️  'jobs-apply-button' not found in HTML")
                
        except Exception as e:
            logger.debug(f"   HTML dump error: {e}")

        # Fetch full job description
        logger.info(f"   📖 Fetching job description...")
        job.description = await scraper.fetch_job_description_from_current_page()
        logger.debug(f"   Description length: {len(job.description)} characters")
        await self._delay(1, 2)

        # Apply
        logger.info(f"   🎯 Attempting to apply...")
        return await handler.apply_to_job_on_current_page(job, job.description)

    # ─────────────────────────────────────────────────────────────────────────
    # Login
    # ─────────────────────────────────────────────────────────────────────────
    async def _login(self) -> bool:
        logger.info("🔑 Logging into LinkedIn...")
        try:
            nav_ok = await self._safe_goto("https://www.linkedin.com/login", timeout=20000)
            if not nav_ok:
                logger.error("Could not load LinkedIn login page.")
                return False

            email_input = await self.page.wait_for_selector("#username", timeout=10000)
            await email_input.click()
            for char in self.config.linkedin_email:
                await email_input.type(char, delay=random.uniform(50, 130))

            await asyncio.sleep(random.uniform(0.5, 1.5))

            pass_input = await self.page.query_selector("#password")
            await pass_input.click()
            for char in self.config.linkedin_password:
                await pass_input.type(char, delay=random.uniform(50, 130))

            await asyncio.sleep(random.uniform(0.5, 1.5))
            await self.page.click("button[type='submit']")
            await asyncio.sleep(random.uniform(4, 7))

            current_url = self.page.url

            # Security challenge / 2FA
            if "checkpoint" in current_url or "challenge" in current_url or "2fa" in current_url:
                logger.warning("⚠️  LinkedIn security challenge or 2FA detected!")
                logger.warning("   Complete it in the browser window.")
                logger.warning("   Waiting up to 90 seconds...")
                try:
                    await self.page.wait_for_url("**/feed/**", timeout=90000)
                except PlaywrightTimeout:
                    logger.error("Timed out waiting for challenge completion.")
                    return False

            if "/feed" in self.page.url or "/mynetwork" in self.page.url:
                logger.info("✅ Login successful!")
                return True

            error_el = await self.page.query_selector(".alert-content, .error-for-username, .error-for-password")
            if error_el:
                logger.error(f"Login error: {await error_el.inner_text()}")

            return False

        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False
