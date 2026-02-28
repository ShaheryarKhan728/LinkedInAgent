"""
LinkedIn Job Scraper
=====================
Finds .NET Developer remote jobs using Playwright (headless browser).
Supports Easy Apply filter and location-based searches.
"""

import asyncio
import logging
import random
import re
from dataclasses import dataclass, field
from typing import List, Optional
from datetime import datetime

logger = logging.getLogger("job_scraper")

@dataclass
class JobListing:
    job_id: str
    title: str
    company: str
    location: str
    description: str
    easy_apply: bool
    url: str
    posted_date: str = ""
    applied: bool = False
    apply_status: str = "pending"
    error: str = ""

# LinkedIn search URL builder
def build_linkedin_search_url(keyword: str, location: str, easy_apply: bool = True) -> str:
    """Build LinkedIn job search URL with filters."""
    import urllib.parse
    base = "https://www.linkedin.com/jobs/search/?"
    params = {
        "keywords": keyword,
        "location": location,
        "f_WT": "2",        # Remote
        "f_AL": "true" if easy_apply else "",  # Easy Apply
        "f_E": "3,4",       # Mid-Senior level (3=Associate, 4=Mid-Senior)
        "sortBy": "DD",     # Most recent
    }
    # Remove empty params
    params = {k: v for k, v in params.items() if v}
    return base + urllib.parse.urlencode(params)


class LinkedInJobScraper:
    def __init__(self, page, config):
        self.page = page
        self.config = config
        self.jobs: List[JobListing] = []

    async def _random_delay(self, min_s=2, max_s=6):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def find_jobs(self) -> List[JobListing]:
        """Scrape job listings across all keywords and locations."""
        all_jobs = []
        seen_ids = set()

        for keyword in self.config.search_keywords:
            for location in self.config.target_locations:
                logger.info(f"🔍 Searching: '{keyword}' in '{location}'")
                jobs = await self._scrape_search_page(keyword, location)
                for job in jobs:
                    if job.job_id not in seen_ids:
                        seen_ids.add(job.job_id)
                        all_jobs.append(job)
                await self._random_delay(3, 7)

                if len(all_jobs) >= self.config.max_jobs_per_session:
                    logger.info(f"Reached session limit of {self.config.max_jobs_per_session} jobs.")
                    return all_jobs[:self.config.max_jobs_per_session]

        logger.info(f"✅ Total unique jobs found: {len(all_jobs)}")
        return all_jobs[:self.config.max_jobs_per_session]

    async def _scrape_search_page(self, keyword: str, location: str) -> List[JobListing]:
        """Navigate to LinkedIn job search and extract listings."""
        url = build_linkedin_search_url(keyword, location, self.config.easy_apply_only)
        jobs = []

        try:
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._random_delay(3, 5)

            # Wait for job cards to load
            await self.page.wait_for_selector(".job-card-container", timeout=15000)

            # Get all job cards
            job_cards = await self.page.query_selector_all(".job-card-container")
            logger.info(f"   Found {len(job_cards)} job cards")

            for card in job_cards[:15]:  # Max 15 per search combo
                try:
                    job = await self._extract_job_from_card(card)
                    if job and job.easy_apply:
                        jobs.append(job)
                        logger.info(f"   ✓ {job.title} @ {job.company} [{job.location}]")
                except Exception as e:
                    logger.debug(f"   Card extraction error: {e}")
                    continue

        except Exception as e:
            logger.error(f"   Search page error for '{keyword}' in '{location}': {e}")

        return jobs

    async def _extract_job_from_card(self, card) -> Optional[JobListing]:
        """Extract job data from a job card element."""
        try:
            # Job ID from data attribute or link
            job_link = await card.query_selector("a.job-card-container__link")
            if not job_link:
                return None

            href = await job_link.get_attribute("href") or ""
            job_id_match = re.search(r'/jobs/view/(\d+)', href)
            if not job_id_match:
                return None
            job_id = job_id_match.group(1)

            # Title
            title_el = await card.query_selector(".job-card-container__link span[aria-hidden='true']")
            title = (await title_el.inner_text()).strip() if title_el else "Unknown Title"

            # Company
            company_el = await card.query_selector(".job-card-container__company-name")
            if not company_el:
                company_el = await card.query_selector(".artdeco-entity-lockup__subtitle")
            company = (await company_el.inner_text()).strip() if company_el else "Unknown Company"

            # Location
            location_el = await card.query_selector(".job-card-container__metadata-item")
            location = (await location_el.inner_text()).strip() if location_el else ""

            # Easy Apply badge
            easy_apply_el = await card.query_selector(".job-card-container__apply-method")
            easy_apply_text = (await easy_apply_el.inner_text()).strip() if easy_apply_el else ""
            is_easy_apply = "easy apply" in easy_apply_text.lower()

            # Full URL
            full_url = f"https://www.linkedin.com/jobs/view/{job_id}/"

            return JobListing(
                job_id=job_id,
                title=title,
                company=company,
                location=location,
                description="",  # Fetched later during application
                easy_apply=is_easy_apply,
                url=full_url,
                posted_date=datetime.now().strftime("%Y-%m-%d"),
            )

        except Exception as e:
            logger.debug(f"Extraction error: {e}")
            return None

    async def fetch_job_description(self, job: JobListing) -> str:
        """Navigate to job page and extract full description."""
        try:
            await self.page.goto(job.url, wait_until="domcontentloaded", timeout=20000)
            await self._random_delay(2, 4)

            desc_el = await self.page.query_selector(".jobs-description__content")
            if not desc_el:
                desc_el = await self.page.query_selector(".job-view-layout")
            if desc_el:
                return (await desc_el.inner_text()).strip()
        except Exception as e:
            logger.debug(f"JD fetch error for {job.job_id}: {e}")
        return ""
