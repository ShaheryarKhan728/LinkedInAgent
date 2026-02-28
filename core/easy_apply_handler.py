"""
LinkedIn Easy Apply Handler
============================
Autonomously fills and submits LinkedIn Easy Apply forms.
Handles multi-step flows, file uploads, and cover letters.
"""

import asyncio
import logging
import random
import os
from typing import Optional
from core.job_scraper import JobListing
from core.resume_optimizer import ResumeOptimizer

logger = logging.getLogger("easy_apply")

# Candidate profile for form auto-fill
CANDIDATE_PROFILE = {
    "first_name": "Shaheryar",
    "last_name": "Khan",
    "email": "emailshaheryar@gmail.com",
    "phone": "+923113206213",
    "phone_country_code": "Pakistan (+92)",
    "city": "Karachi",
    "country": "Pakistan",
    "linkedin": "linkedin.com/in/shaheryarkhan28",
    "github": "github.com/ShaheryarKhan728",
    "years_of_experience": "2",
    "current_company": "Pakistan Single Window",
    "current_title": "Software Engineer",
    "highest_education": "Bachelor",
    "degree": "Bachelor of Computer Science",
    "university": "University of Karachi",
    "graduation_year": "2023",
    "willing_to_relocate": "No",
    "work_authorization": "No",   # Will require visa sponsorship questions
    "salary_expectation": "",     # Leave blank if asked
    "notice_period": "1 month",
}

# Common yes/no question patterns and answers
YES_NO_ANSWERS = {
    # Experience questions
    r'do you have.*\.net': "Yes",
    r'experience.*c#': "Yes",
    r'experience.*sql': "Yes",
    r'experience.*microservice': "Yes",
    r'experience.*rest api': "Yes",
    r'experience.*azure': "Yes",
    r'years.*experience': "2",
    r'do you have.*bachelor': "Yes",
    r'authorized to work': "No",        # Needs sponsorship
    r'require.*sponsorship': "Yes",
    r'willing to work remote': "Yes",
    r'comfortable.*remote': "Yes",
    r'agile': "Yes",
    r'scrum': "Yes",
    r'rabbitmq': "Yes",
    r'docker': "No",
    r'kubernetes': "No",
}


class EasyApplyHandler:
    def __init__(self, page, config):
        self.page = page
        self.config = config
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)

    async def _random_delay(self, min_s=1, max_s=4):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _type_humanlike(self, element, text: str):
        """Type text with human-like delays between keystrokes."""
        await element.click()
        await element.fill("")
        for char in text:
            await element.type(char, delay=random.uniform(40, 120))
        await self._random_delay(0.3, 0.8)

    async def apply_to_job(self, job: JobListing, job_description: str) -> bool:
        """
        Main entry point to apply to a single job.
        Returns True if application submitted successfully.
        """
        logger.info(f"📝 Applying to: {job.title} @ {job.company}")

        try:
            # Navigate to job
            await self.page.goto(job.url, wait_until="domcontentloaded", timeout=20000)
            await self._random_delay(2, 4)

            # Click Easy Apply button
            applied = await self._click_easy_apply_button()
            if not applied:
                logger.warning(f"   ⚠️  Easy Apply button not found for {job.job_id}")
                return False

            await self._random_delay(1, 3)

            # Create tailored resume
            resume_path, resume_text = self.optimizer.create_tailored_resume_text(
                job.job_id, job.title, job.company, job_description
            )

            # Generate cover letter
            cover_letter = self.optimizer.generate_cover_letter(
                job.title, job.company, job_description
            )

            # Handle multi-step form
            max_steps = 10
            step = 0
            while step < max_steps:
                step += 1
                logger.debug(f"   Step {step} of form")

                # Check for modal
                modal = await self.page.query_selector(".jobs-easy-apply-modal")
                if not modal:
                    logger.info(f"   ✅ Application submitted (modal closed)!")
                    return True

                # Check if we're on review/submit step
                if await self._is_submit_step():
                    success = await self._click_submit()
                    if success:
                        logger.info(f"   ✅ Submitted: {job.title} @ {job.company}")
                        return True
                    break

                # Fill current form step
                await self._fill_form_step(resume_path, cover_letter, job_description)
                await self._random_delay(1, 2)

                # Click Next
                next_clicked = await self._click_next_or_review()
                if not next_clicked:
                    logger.warning(f"   ⚠️  Could not proceed to next step at step {step}")
                    break

                await self._random_delay(1, 3)

            return False

        except Exception as e:
            logger.error(f"   ❌ Application error for {job.job_id}: {e}")
            return False

    async def _click_easy_apply_button(self) -> bool:
        """Find and click the Easy Apply button."""
        selectors = [
            "button.jobs-apply-button",
            "button[aria-label*='Easy Apply']",
            ".jobs-s-apply button",
            "button:has-text('Easy Apply')",
        ]
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await self._random_delay(1, 2)
                    return True
            except:
                continue
        return False

    async def _fill_form_step(self, resume_path: str, cover_letter: str, job_description: str):
        """Fill all fields on the current form step."""
        await self._fill_text_inputs()
        await self._fill_dropdowns()
        await self._fill_radio_buttons()
        await self._handle_resume_upload(resume_path)
        await self._handle_cover_letter_field(cover_letter)

    async def _fill_text_inputs(self):
        """Fill text input fields with candidate data."""
        try:
            inputs = await self.page.query_selector_all(".fb-text-selectable__form-element input, input[type='text'], input[type='tel'], input[type='email']")
            for inp in inputs:
                try:
                    label = await self._get_field_label(inp)
                    value = self._get_answer_for_label(label)
                    if value:
                        current = await inp.input_value()
                        if not current:  # Don't overwrite pre-filled fields
                            await self._type_humanlike(inp, value)
                except:
                    continue
        except Exception as e:
            logger.debug(f"Text input error: {e}")

    async def _fill_dropdowns(self):
        """Handle select dropdowns."""
        try:
            selects = await self.page.query_selector_all("select")
            for sel in selects:
                try:
                    label = await self._get_field_label(sel)
                    label_lower = label.lower()

                    if "country" in label_lower:
                        await sel.select_option(label="Pakistan")
                    elif "experience" in label_lower or "year" in label_lower:
                        # Try to select "2 years" or similar
                        await sel.select_option(index=2)
                    elif "education" in label_lower or "degree" in label_lower:
                        await sel.select_option(label="Bachelor's")
                except:
                    continue
        except Exception as e:
            logger.debug(f"Dropdown error: {e}")

    async def _fill_radio_buttons(self):
        """Handle yes/no radio button questions."""
        try:
            # Find all fieldsets (common container for radio groups)
            fieldsets = await self.page.query_selector_all("fieldset")
            for fieldset in fieldsets:
                try:
                    legend = await fieldset.query_selector("legend span[aria-hidden='true']")
                    question = (await legend.inner_text()).lower() if legend else ""

                    answer = self._get_yes_no_answer(question)
                    if answer:
                        # Find radio with matching label
                        radios = await fieldset.query_selector_all("input[type='radio']")
                        for radio in radios:
                            radio_id = await radio.get_attribute("id") or ""
                            label_el = await self.page.query_selector(f"label[for='{radio_id}']")
                            if label_el:
                                label_text = (await label_el.inner_text()).strip().lower()
                                if label_text == answer.lower():
                                    await radio.click()
                                    await self._random_delay(0.3, 0.8)
                                    break
                except:
                    continue
        except Exception as e:
            logger.debug(f"Radio button error: {e}")

    async def _handle_resume_upload(self, resume_path: str):
        """Upload tailored resume if file input is present."""
        try:
            file_input = await self.page.query_selector("input[type='file']")
            if file_input and os.path.exists(resume_path):
                await file_input.set_input_files(resume_path)
                logger.debug("   📎 Resume uploaded")
                await self._random_delay(1, 2)
        except Exception as e:
            logger.debug(f"Resume upload error: {e}")

    async def _handle_cover_letter_field(self, cover_letter: str):
        """Fill cover letter textarea if present."""
        try:
            # Look for textarea with cover letter label
            textareas = await self.page.query_selector_all("textarea")
            for ta in textareas:
                label = await self._get_field_label(ta)
                if "cover" in label.lower() or "letter" in label.lower() or "message" in label.lower():
                    current = await ta.input_value()
                    if not current:
                        await ta.fill(cover_letter)
                        logger.debug("   📄 Cover letter filled")
                        await self._random_delay(0.5, 1)
                    break
        except Exception as e:
            logger.debug(f"Cover letter error: {e}")

    async def _is_submit_step(self) -> bool:
        """Check if current step is the final submit step."""
        try:
            submit_btn = await self.page.query_selector("button[aria-label*='Submit application']")
            return submit_btn is not None
        except:
            return False

    async def _click_submit(self) -> bool:
        """Click the submit button."""
        selectors = [
            "button[aria-label*='Submit application']",
            "button:has-text('Submit application')",
            "button:has-text('Submit')",
        ]
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    await btn.click()
                    await self._random_delay(2, 4)
                    return True
            except:
                continue
        return False

    async def _click_next_or_review(self) -> bool:
        """Click Next or Review button to advance the form."""
        selectors = [
            "button[aria-label='Continue to next step']",
            "button[aria-label='Review your application']",
            "button:has-text('Next')",
            "button:has-text('Review')",
            "button:has-text('Continue')",
        ]
        for sel in selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    is_visible = await btn.is_visible()
                    is_enabled = await btn.is_enabled()
                    if is_visible and is_enabled:
                        await btn.click()
                        return True
            except:
                continue
        return False

    async def _get_field_label(self, element) -> str:
        """Get the label text associated with an input element."""
        try:
            # Try aria-label
            aria = await element.get_attribute("aria-label")
            if aria:
                return aria

            # Try associated label via id
            el_id = await element.get_attribute("id")
            if el_id:
                label_el = await self.page.query_selector(f"label[for='{el_id}']")
                if label_el:
                    return (await label_el.inner_text()).strip()

            # Try placeholder
            placeholder = await element.get_attribute("placeholder")
            if placeholder:
                return placeholder

        except:
            pass
        return ""

    def _get_answer_for_label(self, label: str) -> Optional[str]:
        """Map field label to candidate answer."""
        label_lower = label.lower()

        mapping = {
            "first name": CANDIDATE_PROFILE["first_name"],
            "last name": CANDIDATE_PROFILE["last_name"],
            "email": CANDIDATE_PROFILE["email"],
            "phone": CANDIDATE_PROFILE["phone"],
            "mobile": CANDIDATE_PROFILE["phone"],
            "city": CANDIDATE_PROFILE["city"],
            "linkedin": CANDIDATE_PROFILE["linkedin"],
            "github": CANDIDATE_PROFILE["github"],
            "years of experience": CANDIDATE_PROFILE["years_of_experience"],
            "years experience": CANDIDATE_PROFILE["years_of_experience"],
            "notice period": CANDIDATE_PROFILE["notice_period"],
            "current company": CANDIDATE_PROFILE["current_company"],
            "current title": CANDIDATE_PROFILE["current_title"],
            "current role": CANDIDATE_PROFILE["current_title"],
            "university": CANDIDATE_PROFILE["university"],
            "school": CANDIDATE_PROFILE["university"],
            "degree": CANDIDATE_PROFILE["degree"],
            "graduation": CANDIDATE_PROFILE["graduation_year"],
        }

        for key, value in mapping.items():
            if key in label_lower:
                return value
        return None

    def _get_yes_no_answer(self, question: str) -> Optional[str]:
        """Determine yes/no answer for a question."""
        import re
        for pattern, answer in YES_NO_ANSWERS.items():
            if re.search(pattern, question, re.IGNORECASE):
                return answer
        return None
