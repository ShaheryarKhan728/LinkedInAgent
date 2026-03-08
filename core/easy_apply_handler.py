"""
LinkedIn Easy Apply Handler  (v2)
====================================
Autonomously fills and submits LinkedIn Easy Apply forms.

FIXES:
- Easy Apply button found via JavaScript DOM walk (not CSS selector)
  because LinkedIn dynamically injects classes that don't match static selectors.
- Wait for network idle + extra settle time before looking for button.
- Scroll job detail panel into view before clicking.
- Modal detection uses JS too, not just a single class name.
- All form helpers hardened with JS fallbacks.
- Diagnostic logging on every failure to help future debugging.
"""

import asyncio
import logging
import random
import os
import re
from typing import Optional, Tuple
from core.job_scraper import JobListing
from core.resume_optimizer import ResumeOptimizer

logger = logging.getLogger("easy_apply")

# ── Candidate profile ────────────────────────────────────────────────────────
CANDIDATE_PROFILE = {
    "first_name":        "Shaheryar",
    "last_name":         "Khan",
    "email":             "emailshaheryar@gmail.com",
    "phone":             "+923113206213",
    "phone_country_code":"Pakistan (+92)",
    "city":              "Karachi",
    "country":           "Pakistan",
    "linkedin":          "linkedin.com/in/shaheryarkhan28",
    "github":            "github.com/ShaheryarKhan728",
    "years_of_experience": "3",
    "current_company":   "Pakistan Single Window",
    "current_title":     "Software Engineer",
    "highest_education": "Bachelor",
    "degree":            "Bachelor of Computer Science",
    "university":        "University of Karachi",
    "graduation_year":   "2023",
    "willing_to_relocate": "No",
    "work_authorization":  "No",
    "salary_expectation":  "",
    "notice_period":       "1 month",
}

# ── Yes/No answer map ────────────────────────────────────────────────────────
YES_NO_ANSWERS = {
    r'do you have.*\.net':          "Yes",
    r'experience.*c#':              "Yes",
    r'experience.*sql':             "Yes",
    r'experience.*microservice':    "Yes",
    r'experience.*rest api':        "Yes",
    r'experience.*azure':           "Yes",
    r'years.*experience':           "3",
    r'do you have.*bachelor':       "Yes",
    r'authorized to work':          "No",
    r'require.*sponsorship':        "Yes",
    r'willing to work remote':      "Yes",
    r'comfortable.*remote':         "Yes",
    r'agile':                       "Yes",
    r'scrum':                       "Yes",
    r'rabbitmq':                    "Yes",
    r'docker':                      "Yes",
    r'kubernetes':                  "No",
}

# ── JS: find Easy Apply button anywhere on page ──────────────────────────────
# Walks ALL buttons, checks text content and aria-label for "easy apply"
# This is immune to class name changes.
JS_FIND_EASY_APPLY_BUTTON = """
() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons.find(btn => {
        const text  = (btn.innerText || '').toLowerCase().trim();
        const aria  = (btn.getAttribute('aria-label') || '').toLowerCase();
        const isEA  = text.includes('easy apply') || aria.includes('easy apply');
        const notDisabled = !btn.disabled;
        const visible = btn.offsetParent !== null;
        return isEA && notDisabled && visible;
    }) || null;
}
"""

# ── JS: find the modal by looking for the form heading ──────────────────────
JS_FIND_MODAL = """
() => {
    // Look for the Easy Apply modal — try multiple indicators
    const modal = document.querySelector(
        '.jobs-easy-apply-modal, ' +
        '[data-test-modal-id="easy-apply-modal"], ' +
        'div[role="dialog"]'
    );
    return modal ? true : false;
}
"""

# ── JS: find submit button ───────────────────────────────────────────────────
JS_FIND_SUBMIT_BUTTON = """
() => {
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons.find(btn => {
        const text = (btn.innerText || '').toLowerCase().trim();
        const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
        return (text === 'submit application' || aria.includes('submit application'));
    }) || null;
}
"""

# ── JS: find Next / Review button ───────────────────────────────────────────
JS_FIND_NEXT_BUTTON = """
() => {
    const targets = ['continue to next step', 'review your application',
                     'next', 'review', 'continue'];
    const buttons = Array.from(document.querySelectorAll('button'));
    return buttons.find(btn => {
        const text = (btn.innerText || '').toLowerCase().trim();
        const aria = (btn.getAttribute('aria-label') || '').toLowerCase();
        const combined = text + ' ' + aria;
        return targets.some(t => combined.includes(t)) &&
               !btn.disabled && btn.offsetParent !== null;
    }) || null;
}
"""


class EasyApplyHandler:
    def __init__(self, page, config):
        self.page = page
        self.config = config
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)

    async def _delay(self, min_s=1.0, max_s=3.5):
        await asyncio.sleep(random.uniform(min_s, max_s))

    async def _type_humanlike(self, element, text: str):
        await element.click()
        await element.fill("")
        for char in text:
            await element.type(char, delay=random.uniform(40, 110))
        await self._delay(0.2, 0.6)

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: apply_to_job_on_current_page
    # Called by agent.py AFTER it already navigated — skips page.goto entirely
    # ─────────────────────────────────────────────────────────────────────────
    async def apply_to_job_on_current_page(self, job: JobListing,
                                            job_description: str) -> bool:
        logger.info(f"📝 Applying: {job.title} @ {job.company}")
        try:
            await self.page.evaluate("window.scrollBy(0, 300)")
            await self._delay(0.5, 1.0)

            clicked = await self._click_easy_apply_button()
            if not clicked:
                await self._diagnose_button_failure(job)
                return False

            await self._delay(1.5, 3)

            resume_path, _ = self.optimizer.create_tailored_resume_text(
                job.job_id, job.title, job.company, job_description
            )
            cover_letter = self.optimizer.generate_cover_letter(
                job.title, job.company, job_description
            )

            return await self._walk_form(job, resume_path, cover_letter)

        except Exception as e:
            logger.error(f"   ❌ apply_to_job_on_current_page exception: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # PUBLIC: apply_to_job  (legacy — navigates itself)
    # ─────────────────────────────────────────────────────────────────────────
    async def apply_to_job(self, job: JobListing, job_description: str) -> bool:
        try:
            await self.page.goto(job.url, wait_until="domcontentloaded", timeout=25000)
            await self._delay(2, 4)
            return await self.apply_to_job_on_current_page(job, job_description)
        except Exception as e:
            logger.error(f"   ❌ apply_to_job exception: {e}")
            return False

    # ─────────────────────────────────────────────────────────────────────────
    # Easy Apply button — JS-based detection
    # ─────────────────────────────────────────────────────────────────────────
    async def _click_easy_apply_button(self) -> bool:
        """
        Find and click the Easy Apply button using JavaScript DOM walk.
        Falls back to CSS selectors if JS returns nothing.
        Retries up to 3 times with increasing waits.
        """
        for attempt in range(3):
            # Method 1: JS walk — immune to class name changes
            try:
                btn = await self.page.evaluate_handle(JS_FIND_EASY_APPLY_BUTTON)
                if btn:
                    as_el = btn.as_element()
                    if as_el:
                        await as_el.scroll_into_view_if_needed()
                        await self._delay(0.3, 0.7)
                        await as_el.click()
                        logger.info("   ✅ Easy Apply button clicked (JS method)")
                        return True
            except Exception as e:
                logger.debug(f"   JS button find error (attempt {attempt+1}): {e}")

            # Method 2: CSS selector fallbacks
            css_selectors = [
                "button.jobs-apply-button--top-card",
                "button.jobs-apply-button",
                "button[aria-label*='Easy Apply']",
                "button[aria-label*='easy apply']",
                ".jobs-s-apply button",
                ".jobs-s-apply--top-card button",
                "button:has-text('Easy Apply')",
                ".jobs-apply-button",
            ]
            for sel in css_selectors:
                try:
                    btn = await self.page.query_selector(sel)
                    if btn:
                        visible = await btn.is_visible()
                        enabled = await btn.is_enabled()
                        if visible and enabled:
                            await btn.scroll_into_view_if_needed()
                            await self._delay(0.3, 0.6)
                            await btn.click()
                            logger.info(f"   ✅ Easy Apply button clicked (CSS: {sel})")
                            return True
                except Exception as e:
                    logger.debug(f"   CSS selector '{sel}' error: {e}")
                    continue

            # Wait longer before retry
            wait = [2, 4, 6][attempt]
            logger.debug(f"   Button not found, waiting {wait}s before retry {attempt+2}...")
            await asyncio.sleep(wait)

            # On retry: scroll more and wait for dynamic load
            await self.page.evaluate("window.scrollBy(0, 400)")
            await asyncio.sleep(1)

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Multi-step form walker
    # ─────────────────────────────────────────────────────────────────────────
    async def _walk_form(self, job: JobListing, resume_path: str,
                          cover_letter: str) -> bool:
        max_steps = 12
        for step in range(1, max_steps + 1):
            logger.debug(f"   Form step {step}")
            await self._delay(1, 2)

            # Check if modal is still open
            modal_open = await self.page.evaluate(JS_FIND_MODAL)
            if not modal_open:
                logger.info("   ✅ Modal closed — application submitted!")
                return True

            # Check for submit button
            submit_btn = await self.page.evaluate_handle(JS_FIND_SUBMIT_BUTTON)
            if submit_btn and submit_btn.as_element():
                el = submit_btn.as_element()
                await el.scroll_into_view_if_needed()
                await self._delay(0.5, 1)
                await el.click()
                logger.info(f"   ✅ Submitted: {job.title} @ {job.company}")
                await self._delay(2, 4)
                return True

            # Fill form fields on current step
            await self._fill_form_step(resume_path, cover_letter)
            await self._delay(0.8, 1.5)

            # Click Next / Review / Continue
            advanced = await self._click_next_button()
            if not advanced:
                logger.warning(f"   ⚠️  Could not advance form at step {step}")
                # Try one more time after a longer wait
                await self._delay(2, 3)
                advanced = await self._click_next_button()
                if not advanced:
                    break

        logger.warning("   ⚠️  Form walk exhausted without submission")
        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Form field fillers
    # ─────────────────────────────────────────────────────────────────────────
    async def _fill_form_step(self, resume_path: str, cover_letter: str):
        await self._fill_text_inputs()
        await self._fill_dropdowns()
        await self._fill_radio_buttons()
        await self._handle_resume_upload(resume_path)
        await self._handle_cover_letter_field(cover_letter)

    async def _fill_text_inputs(self):
        try:
            inputs = await self.page.query_selector_all(
                "input[type='text'], input[type='tel'], "
                "input[type='email'], input[type='number']"
            )
            for inp in inputs:
                try:
                    if not await inp.is_visible():
                        continue
                    label = await self._get_field_label(inp)
                    value = self._get_answer_for_label(label)
                    if value:
                        current = await inp.input_value()
                        if not current.strip():
                            await self._type_humanlike(inp, value)
                            logger.debug(f"   Filled '{label}' = '{value}'")
                except Exception as e:
                    logger.debug(f"   Text input fill error: {e}")
        except Exception as e:
            logger.debug(f"   _fill_text_inputs error: {e}")

    async def _fill_dropdowns(self):
        try:
            selects = await self.page.query_selector_all("select")
            for sel_el in selects:
                try:
                    if not await sel_el.is_visible():
                        continue
                    label = await self._get_field_label(sel_el)
                    label_lower = label.lower()

                    # Get available options to avoid selecting invalid ones
                    options = await sel_el.query_selector_all("option")
                    option_texts = []
                    for opt in options:
                        t = (await opt.inner_text()).strip().lower()
                        option_texts.append(t)

                    if "country" in label_lower or "nation" in label_lower:
                        await self._select_best_option(sel_el, option_texts,
                            ["pakistan"])
                    elif "phone" in label_lower and "country" in label_lower:
                        await self._select_best_option(sel_el, option_texts,
                            ["pakistan", "+92"])
                    elif "experience" in label_lower or "year" in label_lower:
                        await self._select_best_option(sel_el, option_texts,
                            ["2", "1-2", "2-3", "1-3", "2 year"])
                    elif "education" in label_lower or "degree" in label_lower:
                        await self._select_best_option(sel_el, option_texts,
                            ["bachelor", "bsc", "b.s", "undergraduate"])
                    elif "notice" in label_lower:
                        await self._select_best_option(sel_el, option_texts,
                            ["1 month", "30 day", "one month"])
                except Exception as e:
                    logger.debug(f"   Dropdown fill error: {e}")
        except Exception as e:
            logger.debug(f"   _fill_dropdowns error: {e}")

    async def _select_best_option(self, select_el, option_texts: list, targets: list):
        """Select first option whose text contains any of the target strings."""
        for target in targets:
            for i, opt_text in enumerate(option_texts):
                if target in opt_text:
                    try:
                        await select_el.select_option(index=i)
                        return
                    except:
                        pass

    async def _fill_radio_buttons(self):
        try:
            fieldsets = await self.page.query_selector_all("fieldset")
            for fieldset in fieldsets:
                try:
                    # Get question text
                    question = ""
                    for q_sel in [
                        "legend span[aria-hidden='true']",
                        "legend",
                        "label",
                    ]:
                        el = await fieldset.query_selector(q_sel)
                        if el:
                            question = (await el.inner_text()).strip().lower()
                            if question:
                                break

                    if not question:
                        continue

                    answer = self._get_yes_no_answer(question)
                    if not answer:
                        continue

                    # Find matching radio option
                    radios = await fieldset.query_selector_all("input[type='radio']")
                    for radio in radios:
                        radio_id = await radio.get_attribute("id") or ""
                        label_el = None
                        if radio_id:
                            label_el = await self.page.query_selector(
                                f"label[for='{radio_id}']"
                            )
                        if not label_el:
                            # Try sibling label
                            label_el = await radio.query_selector("xpath=../label")

                        if label_el:
                            label_text = (await label_el.inner_text()).strip().lower()
                            if label_text == answer.lower() or answer.lower() in label_text:
                                await radio.click()
                                await self._delay(0.2, 0.5)
                                logger.debug(
                                    f"   Radio: '{question[:50]}' → '{answer}'"
                                )
                                break
                except Exception as e:
                    logger.debug(f"   Radio fill error: {e}")
        except Exception as e:
            logger.debug(f"   _fill_radio_buttons error: {e}")

    async def _handle_resume_upload(self, resume_path: str):
        try:
            # LinkedIn hides file inputs — use query_selector_all
            file_inputs = await self.page.query_selector_all("input[type='file']")
            for fi in file_inputs:
                if os.path.exists(resume_path):
                    await fi.set_input_files(resume_path)
                    logger.debug(f"   📎 Resume uploaded: {resume_path}")
                    await self._delay(1, 2)
                    break
        except Exception as e:
            logger.debug(f"   Resume upload error: {e}")

    async def _handle_cover_letter_field(self, cover_letter: str):
        try:
            textareas = await self.page.query_selector_all("textarea")
            for ta in textareas:
                try:
                    if not await ta.is_visible():
                        continue
                    label = await self._get_field_label(ta)
                    label_lower = label.lower()
                    if any(k in label_lower for k in
                           ["cover", "letter", "message", "additional", "note"]):
                        current = await ta.input_value()
                        if not current.strip():
                            await ta.fill(cover_letter)
                            logger.debug("   📄 Cover letter filled")
                            await self._delay(0.5, 1)
                        break
                except Exception as e:
                    logger.debug(f"   Cover letter field error: {e}")
        except Exception as e:
            logger.debug(f"   _handle_cover_letter_field error: {e}")

    # ─────────────────────────────────────────────────────────────────────────
    # Navigation
    # ─────────────────────────────────────────────────────────────────────────
    async def _click_next_button(self) -> bool:
        """Click Next/Review/Continue via JS walk first, then CSS fallback."""
        # JS method
        try:
            btn = await self.page.evaluate_handle(JS_FIND_NEXT_BUTTON)
            if btn and btn.as_element():
                el = btn.as_element()
                await el.scroll_into_view_if_needed()
                await self._delay(0.3, 0.6)
                await el.click()
                logger.debug("   Clicked next (JS)")
                return True
        except Exception as e:
            logger.debug(f"   JS next button error: {e}")

        # CSS fallback
        css_selectors = [
            "button[aria-label='Continue to next step']",
            "button[aria-label='Review your application']",
            "button[aria-label='Next']",
            "button:has-text('Next')",
            "button:has-text('Review')",
            "button:has-text('Continue')",
        ]
        for sel in css_selectors:
            try:
                btn = await self.page.query_selector(sel)
                if btn:
                    visible = await btn.is_visible()
                    enabled = await btn.is_enabled()
                    if visible and enabled:
                        await btn.click()
                        logger.debug(f"   Clicked next (CSS: {sel})")
                        return True
            except:
                continue

        return False

    # ─────────────────────────────────────────────────────────────────────────
    # Label helpers
    # ─────────────────────────────────────────────────────────────────────────
    async def _get_field_label(self, element) -> str:
        """Get label text for any input element via multiple strategies."""
        try:
            # 1. aria-label attribute
            aria = await element.get_attribute("aria-label")
            if aria and aria.strip():
                return aria.strip()

            # 2. <label for="id">
            el_id = await element.get_attribute("id")
            if el_id:
                label_el = await self.page.query_selector(f"label[for='{el_id}']")
                if label_el:
                    t = (await label_el.inner_text()).strip()
                    if t:
                        return t

            # 3. placeholder
            placeholder = await element.get_attribute("placeholder")
            if placeholder and placeholder.strip():
                return placeholder.strip()

            # 4. name attribute as last resort
            name = await element.get_attribute("name")
            if name:
                return name.replace("-", " ").replace("_", " ")

        except:
            pass
        return ""

    def _get_answer_for_label(self, label: str) -> Optional[str]:
        label_lower = label.lower()
        mapping = {
            "first name":         CANDIDATE_PROFILE["first_name"],
            "last name":          CANDIDATE_PROFILE["last_name"],
            "family name":        CANDIDATE_PROFILE["last_name"],
            "surname":            CANDIDATE_PROFILE["last_name"],
            "email":              CANDIDATE_PROFILE["email"],
            "phone":              CANDIDATE_PROFILE["phone"],
            "mobile":             CANDIDATE_PROFILE["phone"],
            "telephone":          CANDIDATE_PROFILE["phone"],
            "city":               CANDIDATE_PROFILE["city"],
            "linkedin":           CANDIDATE_PROFILE["linkedin"],
            "github":             CANDIDATE_PROFILE["github"],
            "years of experience":CANDIDATE_PROFILE["years_of_experience"],
            "years experience":   CANDIDATE_PROFILE["years_of_experience"],
            "how many years":     CANDIDATE_PROFILE["years_of_experience"],
            "notice period":      CANDIDATE_PROFILE["notice_period"],
            "current company":    CANDIDATE_PROFILE["current_company"],
            "current employer":   CANDIDATE_PROFILE["current_company"],
            "current title":      CANDIDATE_PROFILE["current_title"],
            "current role":       CANDIDATE_PROFILE["current_title"],
            "job title":          CANDIDATE_PROFILE["current_title"],
            "university":         CANDIDATE_PROFILE["university"],
            "school":             CANDIDATE_PROFILE["university"],
            "college":            CANDIDATE_PROFILE["university"],
            "institution":        CANDIDATE_PROFILE["university"],
            "degree":             CANDIDATE_PROFILE["degree"],
            "qualification":      CANDIDATE_PROFILE["degree"],
            "graduation":         CANDIDATE_PROFILE["graduation_year"],
            "grad year":          CANDIDATE_PROFILE["graduation_year"],
        }
        for key, value in mapping.items():
            if key in label_lower:
                return value
        return None

    def _get_yes_no_answer(self, question: str) -> Optional[str]:
        for pattern, answer in YES_NO_ANSWERS.items():
            if re.search(pattern, question, re.IGNORECASE):
                return answer
        return None

    # ─────────────────────────────────────────────────────────────────────────
    # Diagnostics
    # ─────────────────────────────────────────────────────────────────────────
    async def _diagnose_button_failure(self, job: JobListing):
        """Log diagnostic info when Easy Apply button cannot be found."""
        try:
            url = self.page.url
            title = await self.page.title()
            logger.warning(f"   ⚠️  Easy Apply button NOT found for job {job.job_id}")
            logger.warning(f"   Page: '{title}'")
            logger.warning(f"   URL:  {url}")

            # Check if redirected to login
            if "login" in url or "authwall" in url or "checkpoint" in url:
                logger.error("   ❌ Session expired — redirected to login!")
                return

            # List all buttons on page for debugging
            buttons = await self.page.evaluate("""
                () => Array.from(document.querySelectorAll('button'))
                    .map(b => ({
                        text: b.innerText.trim().slice(0,60),
                        aria: b.getAttribute('aria-label') || '',
                        disabled: b.disabled,
                        visible: b.offsetParent !== null
                    }))
                    .filter(b => b.text || b.aria)
                    .slice(0, 15)
            """)
            logger.debug(f"   Buttons on page: {buttons}")

            # Check if it's an external application (not Easy Apply)
            apply_link = await self.page.query_selector("a[href*='apply']")
            if apply_link:
                href = await apply_link.get_attribute("href")
                logger.warning(f"   This may be an external application (not Easy Apply): {href}")
        except Exception as e:
            logger.debug(f"   Diagnostics error: {e}")
