"""
LinkedIn Job Agent — Main Orchestrator
========================================
Coordinates: Login → Job Search → Resume Optimization → Easy Apply → Logging
"""

import asyncio
import logging
import random
import os
from datetime import datetime

from playwright.async_api import async_playwright, Browser, BrowserContext, Page

from core.config import AgentConfig
from core.job_scraper import LinkedInJobScraper, JobListing
from core.easy_apply_handler import EasyApplyHandler
from core.resume_optimizer import ResumeOptimizer
from core.tracker import ApplicationTracker
from core.logger import setup_logger

logger = setup_logger("agent")


class LinkedInJobAgent:
    def __init__(self, config: AgentConfig):
        self.config = config
        self.tracker = ApplicationTracker(config.output_dir)
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)
        self.browser: Browser = None
        self.context: BrowserContext = None
        self.page: Page = None

    async def _random_delay(self):
        delay = random.uniform(self.config.min_delay_seconds, self.config.max_delay_seconds)
        logger.debug(f"Waiting {delay:.1f}s...")
        await asyncio.sleep(delay)

    async def run(self):
        """Main agent execution flow."""
        logger.info("🚀 Agent starting...")
        os.makedirs(self.config.tailored_resume_dir, exist_ok=True)

        async with async_playwright() as pw:
            # Launch browser — headless=False so you can see it work
            self.browser = await pw.chromium.launch(
                headless=False,
                slow_mo=50,
                args=["--disable-blink-features=AutomationControlled"]
            )

            # Create realistic browser context
            self.context = await self.browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                locale="en-US",
                timezone_id="Asia/Karachi",
            )

            self.page = await self.context.new_page()

            # ── Step 1: Login ─────────────────────────────────────────────
            logged_in = await self._login()
            if not logged_in:
                logger.error("❌ Login failed. Aborting.")
                await self.browser.close()
                return

            await self._random_delay()

            # ── Step 2: Find Jobs ─────────────────────────────────────────
            scraper = LinkedInJobScraper(self.page, self.config)
            jobs = await scraper.find_jobs()

            if not jobs:
                logger.warning("⚠️  No jobs found. Try different keywords or check your login.")
                await self.browser.close()
                return

            logger.info(f"\n🎯 Found {len(jobs)} jobs. Starting applications...\n")

            # ── Step 3: Apply to each job ─────────────────────────────────
            handler = EasyApplyHandler(self.page, self.config)
            applied_count = 0

            for i, job in enumerate(jobs, 1):
                logger.info(f"\n[{i}/{len(jobs)}] Processing: {job.title} @ {job.company}")

                try:
                    # Fetch full job description for keyword optimization
                    job.description = await scraper.fetch_job_description(job)
                    await self._random_delay()

                    # Apply
                    success = await handler.apply_to_job(job, job.description)

                    if success:
                        job.apply_status = "applied"
                        applied_count += 1
                        logger.info(f"✅ [{applied_count}] Applied successfully!")
                    else:
                        job.apply_status = "failed"
                        logger.warning(f"⚠️  Application failed or skipped")

                except Exception as e:
                    job.apply_status = "failed"
                    job.error = str(e)[:200]
                    logger.error(f"❌ Error: {e}")

                finally:
                    # Always log the attempt
                    resume_path = os.path.join(
                        self.config.tailored_resume_dir,
                        f"ShaheryarKhan_{job.job_id}.txt"
                    )
                    self.tracker.log_application(job, resume_path)

                # Human-like delay between applications
                if i < len(jobs):
                    await self._random_delay()

            # ── Step 4: Summary ───────────────────────────────────────────
            self.tracker.print_summary(jobs)
            await self.browser.close()
            logger.info("🏁 Agent finished.")

    async def _login(self) -> bool:
        """Log into LinkedIn with provided credentials."""
        logger.info("🔑 Logging into LinkedIn...")

        try:
            await self.page.goto("https://www.linkedin.com/login", wait_until="domcontentloaded")
            await asyncio.sleep(random.uniform(2, 4))

            # Fill email
            email_input = await self.page.wait_for_selector("#username", timeout=10000)
            await email_input.click()
            for char in self.config.linkedin_email:
                await email_input.type(char, delay=random.uniform(50, 130))

            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Fill password
            pass_input = await self.page.query_selector("#password")
            await pass_input.click()
            for char in self.config.linkedin_password:
                await pass_input.type(char, delay=random.uniform(50, 130))

            await asyncio.sleep(random.uniform(0.5, 1.5))

            # Click login
            await self.page.click("button[type='submit']")
            await asyncio.sleep(random.uniform(3, 6))

            # Check for CAPTCHA or security challenge
            current_url = self.page.url
            if "checkpoint" in current_url or "challenge" in current_url:
                logger.warning("⚠️  LinkedIn security challenge detected!")
                logger.warning("   Please complete the challenge in the browser window.")
                logger.warning("   Waiting up to 60 seconds for you to complete it...")
                # Wait for user to solve challenge manually
                await self.page.wait_for_url("**/feed/**", timeout=60000)

            # Verify login success
            if "/feed" in self.page.url or "/in/" in self.page.url:
                logger.info("✅ Login successful!")
                return True

            # Check for wrong credentials
            error_el = await self.page.query_selector(".alert-content")
            if error_el:
                error_text = await error_el.inner_text()
                logger.error(f"Login error: {error_text}")

            return False

        except Exception as e:
            logger.error(f"Login exception: {e}")
            return False
