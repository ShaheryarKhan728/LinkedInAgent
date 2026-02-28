"""
Application Tracker
====================
Logs all job applications to a CSV file for review.
"""

import csv
import os
import logging
from datetime import datetime
from typing import List
from core.job_scraper import JobListing

logger = logging.getLogger("tracker")

COLUMNS = [
    "date_applied", "job_id", "title", "company", "location",
    "url", "apply_status", "error", "resume_version"
]

class ApplicationTracker:
    def __init__(self, output_dir: str = "output"):
        os.makedirs(output_dir, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.filepath = os.path.join(output_dir, f"applications_{timestamp}.csv")
        self._init_csv()

    def _init_csv(self):
        with open(self.filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
        logger.info(f"📊 Tracker initialized: {self.filepath}")

    def log_application(self, job: JobListing, resume_version: str = ""):
        """Log a single application attempt."""
        row = {
            "date_applied": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "job_id": job.job_id,
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "url": job.url,
            "apply_status": job.apply_status,
            "error": job.error,
            "resume_version": resume_version,
        }
        with open(self.filepath, "a", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writerow(row)

    def print_summary(self, jobs: List[JobListing]):
        """Print final session summary."""
        total = len(jobs)
        success = sum(1 for j in jobs if j.apply_status == "applied")
        failed = sum(1 for j in jobs if j.apply_status == "failed")
        skipped = sum(1 for j in jobs if j.apply_status == "skipped")

        print(f"""
╔══════════════════════════════════════════════════╗
║              SESSION SUMMARY                     ║
╠══════════════════════════════════════════════════╣
║  Total Jobs Found:   {total:<27}║
║  Successfully Applied: {success:<25}║
║  Failed:             {failed:<27}║
║  Skipped:            {skipped:<27}║
╠══════════════════════════════════════════════════╣
║  Log saved to: {self.filepath[:33]:<33}║
╚══════════════════════════════════════════════════╝
        """)
