"""
LinkedIn Job Agent — Main Orchestrator  (v3)
=============================================
Coordinates: Login → Job Search → Resume Optimization → Easy Apply → Logging

FIXES:
- Replaced wait_until="networkidle" with "domcontentloaded" + explicit settle wait
  (LinkedIn never goes network-idle due to background polling — caused 30s timeouts)
- Page recovery: detects dead/crashed page and recreates it without restarting the agent
- Per-job timeout wrapper: one stuck job can no longer crash the entire session
- Browser launch hardened with extra anti-detection flags
- Login handles 2FA prompt wait gracefully
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
from core.logger import setup_logger

logger = setup_logger("agent")

# Max seconds to spend on a single job before giving up and moving on
PER_JOB_TIMEOUT = 120


class LinkedInJobAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tracker = ApplicationTracker(config.output_dir)
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

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
            handler = EasyApplyHandler(self.page, self.config)
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
        # Navigate to job page
        nav_ok = await self._safe_goto(job.url)
        if not nav_ok:
            logger.warning(f"   ⚠️  Could not load job page: {job.url}")
            return False

        # Fetch full job description
        job.description = await scraper.fetch_job_description_from_current_page()
        await self._delay(1, 2)

        # Apply
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
