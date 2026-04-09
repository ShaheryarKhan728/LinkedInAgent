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
        # "f_E": "3,4",       # Mid-Senior level (3=Associate, 4=Mid-Senior)
        "sortBy": "R",      # Most relevant
        "f_TPR": "r86400",  # Past 24 hours
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
            logger.info(f"   📍 URL: {url}")
            await self.page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await self._random_delay(3, 5)

            # Log page state BEFORE searching for cards
            page_url = self.page.url
            page_title = await self.page.title()
            logger.info(f"   ✓ Page loaded: {page_title}")
            logger.debug(f"   Current URL: {page_url}")
            
            # Get full HTML to diagnose
            html_content = await self.page.content()
            logger.debug(f"   Page HTML size: {len(html_content)} bytes")
            
            # Check if page contains any job-related keywords
            if "job" not in html_content.lower():
                logger.warning(f"   ⚠️  'job' keyword not found in HTML - page may not have loaded properly")
            if "apply" not in html_content.lower():
                logger.warning(f"   ⚠️  'apply' keyword not found in HTML")

            # Try multiple selectors for job cards (LinkedIn structure varies)
            job_card_selectors = [
                ".job-card-container",                    # Standard
                "[data-job-id]",                          # Data attribute
                ".jobs-search-results__list-item",        # Alternative
                "div[class*='job-card']",                 # Wildcard
            ]
            
            job_cards = []
            found_selector = None
            
            for selector in job_card_selectors:
                try:
                    logger.debug(f"   Trying selector: {selector}")
                    job_cards = await self.page.query_selector_all(selector)
                    if len(job_cards) > 0:
                        found_selector = selector
                        logger.info(f"   ✓ Found {len(job_cards)} cards using: {selector}")
                        break
                    else:
                        logger.debug(f"   - No results with: {selector}")
                except Exception as e:
                    logger.debug(f"   - Error with {selector}: {e}")
                    continue
            
            if len(job_cards) == 0:
                logger.warning(f"   ❌ NO JOB CARDS FOUND on page!")
                logger.warning(f"   Possible reasons:")
                logger.warning(f"      - Search returned empty results")
                logger.warning(f"      - LinkedIn page layout has changed")
                logger.warning(f"      - Page did not fully load")
                
                # Log HTML snippet for debugging
                if ".job-card-container" in html_content:
                    logger.debug(f"   ℹ️  HTML contains '.job-card-container' class but selector failed")
                    idx = html_content.find(".job-card-container")
                    snippet = html_content[idx:idx+500]
                    logger.debug(f"   HTML snippet: {snippet}")
                
                return []

            logger.info(f"   ✓ Found {len(job_cards)} job cards total")

            for idx, card in enumerate(job_cards[:15], 1):  # Max 15 per search combo
                try:
                    job = await self._extract_job_from_card(card)
                    if job:
                        jobs.append(job)
                        easy_apply_status = "✓" if job.easy_apply else "?"
                        logger.info(f"   [{idx}/{len(job_cards)}] {easy_apply_status} {job.title} @ {job.company}")
                    else:
                        logger.debug(f"   [{idx}/{len(job_cards)}] ⊘ Could not extract job data")
                except Exception as e:
                    logger.debug(f"   [{idx}/{len(job_cards)}] Error: {e}")
                    continue

            logger.info(f"   📊 Extracted {len(jobs)} jobs from {len(job_cards)} cards")

        except Exception as e:
            logger.error(f"   ❌ Search page error: {e}", exc_info=True)

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

            # Easy Apply detection - use stable selectors + aria-labels
            # Prioritize: ID > data-attribute > aria-label > class-based
            easy_apply_selectors = [
                "button#jobs-apply-button-id",                  # Stable ID
                "button[data-live-test-job-apply-button]",      # Stable data-attribute
                ".jobs-apply-button--top-card button",          # Container + button
                "button[aria-label*='Easy Apply']",             # Aria-label
                ".job-card-container__apply-method",            # Legacy selector
                "[class*='apply-method']",                      # Broader match
            ]
            
            is_easy_apply = False
            
            for selector in easy_apply_selectors:
                try:
                    easy_apply_el = await card.query_selector(selector)
                    if easy_apply_el:
                        # Check text content
                        easy_apply_text = (await easy_apply_el.inner_text()).strip() if easy_apply_el else ""
                        if "easy apply" in easy_apply_text.lower():
                            is_easy_apply = True
                            break
                        # Check aria-label attribute
                        aria_label = await easy_apply_el.get_attribute("aria-label") or ""
                        if "easy apply" in aria_label.lower():
                            is_easy_apply = True
                            break
                except Exception:
                    continue

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
            return await self.fetch_job_description_from_current_page()
        except Exception as e:
            logger.debug(f"JD fetch error for {job.job_id}: {e}")
        return ""

    async def fetch_job_description_from_current_page(self) -> str:
        """
        Extract job description from whatever page is currently loaded.
        Called by agent.py after it has already navigated — avoids double navigation.
        """
        try:
            for sel in [
                ".jobs-description__content",
                ".jobs-description-content__text",
                "#job-details",
                ".jobs-box__html-content",
                ".job-view-layout",
                "[class*='description']",
            ]:
                el = await self.page.query_selector(sel)
                if el:
                    text = (await el.inner_text()).strip()
                    if text:
                        return text
        except Exception as e:
            logger.debug(f"JD extraction error: {e}")
        return ""
