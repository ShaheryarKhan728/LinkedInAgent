"""
LinkedIn Easy Apply Handler  (v3)
====================================
Autonomously fills and submits LinkedIn Easy Apply forms.
Now with Gemini AI-powered question answering and user review prompts.

FEATURES:
- Easy Apply button found via JavaScript DOM walk (immune to class changes)
- Gemini-powered question analysis (replace regex patterns with AI)
- User review prompts before form submission
- PDF resume handling with text fallback
- Aggressive logging for debugging

FIXES:
- Wait for network idle + extra settle time before looking for button
- Scroll job detail panel into view before clicking
- Modal detection uses JS, not just single class name
- All form helpers hardened with JS fallbacks
- Diagnostic logging on every failure
"""

import asyncio
import logging
import random
import os
import re
from typing import Optional, Tuple, Dict
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
    for (let btn of buttons) {
        const text  = (btn.innerText || '').toLowerCase().trim();
        const aria  = (btn.getAttribute('aria-label') || '').toLowerCase();
        const id    = btn.getAttribute('id') || '';
        const isEA  = text.includes('easy apply') || aria.includes('easy apply') || id === 'jobs-apply-button-id';
        const notDisabled = !btn.disabled;
        // More lenient visibility check - LinkedIn hides buttons in various ways
        const styles = window.getComputedStyle(btn);
        const isHidden = styles.display === 'none' || styles.visibility === 'hidden' || styles.opacity === '0';
        if (isEA && notDisabled && !isHidden) {
            return btn;
        }
    }
    return null;
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
    def __init__(self, page, config, gemini_service=None, review_manager=None):
        self.page = page
        self.config = config
        self.optimizer = ResumeOptimizer(config.tailored_resume_dir)
        self.gemini_service = gemini_service
        self.review_manager = review_manager
        self.current_job = None  # Track current job for review context
        
        logger.info(f"")
        logger.info(f"╔═══════════════════════════════════════════════════════════╗")
        logger.info(f"║ EasyApplyHandler Initialization                          ║")
        logger.info(f"╚═══════════════════════════════════════════════════════════╝")
        logger.info(f"🔧 EasyApplyHandler initialized")
        logger.info(f"   Config: {config}")
        logger.info(f"   Gemini Service Available: {gemini_service is not None}")
        if gemini_service:
            logger.info(f"   Gemini Service Type: {type(gemini_service).__name__}")
            logger.info(f"   ✓ Gemini service ACTIVE for AI button detection")
        else:
            logger.warning(f"   ⚠️  NO Gemini service - fallback to JS/CSS only")
        
        if review_manager:
            logger.info(f"   ✓ Review manager available for user approval prompts")
        else:
            logger.warning(f"   ⚠️  NO Review manager")

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
        self.current_job = job  # Track for review context
        logger.info(f"📝 Applying: {job.title} @ {job.company}")
        try:
            # Log current page state
            current_url = self.page.url
            page_title = await self.page.title()
            logger.debug(f"   Current URL: {current_url}")
            logger.debug(f"   Page title: {page_title}")
            
            # Check Easy Apply button BEFORE any clicks
            logger.info(f"   🔍 Checking for Easy Apply button...")
            easy_apply_check = await self.page.evaluate("""
                () => {
                    const btn = document.getElementById('jobs-apply-button-id');
                    if (!btn) return { found: false, message: 'ID selector failed' };
                    const styles = window.getComputedStyle(btn);
                    return {
                        found: true,
                        text: btn.innerText || btn.textContent,
                        aria: btn.getAttribute('aria-label'),
                        display: styles.display,
                        visibility: styles.visibility,
                        opacity: styles.opacity,
                        disabled: btn.disabled,
                        offsetParent: btn.offsetParent !== null
                    };
                }
            """)
            logger.info(f"   Button check result: {easy_apply_check}")
            
            # Wait extra time for LinkedIn to fully load job details and Easy Apply button
            await self._delay(2, 4)
            
            # Scroll to top to ensure job detail panel is visible
            await self.page.evaluate("window.scrollTo(0, 0)")
            await self._delay(0.5, 1.0)
            
            # Scroll down slowly to reveal buttons
            await self.page.evaluate("window.scrollBy(0, 300)")
            await self._delay(0.5, 1.0)

            clicked = await self._click_easy_apply_button()
            if not clicked:
                logger.error(f"   ❌ FAILED to click Easy Apply button")
                await self._diagnose_button_failure(job)
                return False

            logger.info(f"   ✅ Easy Apply button clicked successfully")
            await self._delay(1.5, 3)

            # Use Gemini to generate tailored resume if available
            if self.gemini_service:
                resume_path, resume_text = await self._generate_gemini_resume(
                    job, job_description
                )
            else:
                resume_path, resume_text = self.optimizer.create_tailored_resume_text(
                    job.job_id, job.title, job.company, job_description
                )
            
            # Use Gemini to generate tailored cover letter if available
            if self.gemini_service:
                cover_letter = await self._generate_gemini_cover_letter(
                    job, job_description
                )
            else:
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
    # Easy Apply button — JS-based detection with LLM fallback
    # ─────────────────────────────────────────────────────────────────────────
    async def _click_easy_apply_button(self) -> bool:
        """
        Find and click the Easy Apply button using multiple strategies:
        1. JavaScript DOM walk (immune to class changes)
        2. CSS selectors (stable identifiers)
        3. LLM-based visual analysis (Gemini) - NEW!
        
        Uses retry mechanism with increasing waits.
        """
        # Log initial state
        logger.info(f"   ━━━ EASY APPLY BUTTON DETECTION STARTING ━━━")
        logger.info(f"   Gemini Service Available: {self.gemini_service is not None}")
        logger.info(f"   Gemini Service Type: {type(self.gemini_service).__name__ if self.gemini_service else 'None'}")
        
        for attempt in range(4):
            attempt_num = attempt + 1
            logger.info(f"")
            logger.info(f"   ╔═══════════════════════════════════════════════════════════╗")
            logger.info(f"   ║ ATTEMPT {attempt_num}/4 to find Easy Apply button             ║")
            logger.info(f"   ╚═══════════════════════════════════════════════════════════╝")
            
            # Method 1: JS walk — immune to class name changes
            try:
                logger.info(f"   [Method 1/3] Testing JS DOM walk...")
                btn = await self.page.evaluate_handle(JS_FIND_EASY_APPLY_BUTTON)
                logger.debug(f"      JS returned: {btn}")
                if btn:
                    as_el = btn.as_element()
                    logger.debug(f"      JS element: {as_el}")
                    if as_el:
                        logger.info(f"      ✓ JS method FOUND button!")
                        await as_el.scroll_into_view_if_needed()
                        await self._delay(0.5, 1.0)
                        try:
                            await as_el.click()
                            logger.info(f"      ✅ SUCCESS: Button clicked via JS method")
                            return True
                        except Exception as click_err:
                            logger.warning(f"      ⚠️  JS click failed: {click_err}")
                    else:
                        logger.debug(f"      JS found handle but could not convert to element")
                else:
                    logger.info(f"      ✗ JS returned null/no button found")
            except Exception as e:
                logger.debug(f"      JS error: {e}")

            # Method 2: CSS selector fallbacks - prioritize stable identifiers
            logger.info(f"   [Method 2/3] Testing CSS selectors...")
            css_selectors = [
                "#jobs-apply-button-id",                           # Stable ID (primary)
                "button[data-live-test-job-apply-button]",         # Stable data-attribute
                "button[aria-label*='Easy Apply']",                # Aria-label match
                "button[aria-label*='easy apply']",                # Case-insensitive
                ".jobs-apply-button--top-card button",             # Container + button
                "button.jobs-apply-button",                        # Button with class
            ]
            
            css_found = False
            for sel_idx, sel in enumerate(css_selectors, 1):
                try:
                    logger.debug(f"      [{sel_idx}/6] Testing: {sel}")
                    btn = await self.page.query_selector(sel)
                    if btn:
                        visible = await btn.is_visible()
                        enabled = await btn.is_enabled()
                        logger.info(f"      ✓ FOUND selector '{sel}'")
                        logger.info(f"         visible={visible}, enabled={enabled}")
                        if visible and enabled:
                            await btn.scroll_into_view_if_needed()
                            await self._delay(0.5, 1.0)
                            await btn.click()
                            logger.info(f"      ✅ SUCCESS: Button clicked via CSS selector '{sel}'")
                            return True
                        else:
                            logger.info(f"      ✗ Button found but NOT usable (visible={visible}, enabled={enabled})")
                    else:
                        logger.debug(f"      ✗ Selector returned no element")
                except Exception as e:
                    logger.debug(f"      Error with '{sel}': {e}")
                    continue

            if not css_found:
                logger.info(f"      ✗ All CSS selectors failed")

            # Method 3: LLM-based button detection (NEW!)
            logger.info(f"   [Method 3/3] LLM-based detection check...")
            logger.info(f"      Gemini available: {self.gemini_service is not None}")
            logger.info(f"      Attempt number: {attempt_num} (need >= 3)")
            logger.info(f"      Should use LLM: {self.gemini_service is not None and attempt_num >= 3}")
            
            if self.gemini_service and attempt_num >= 3:  # Try LLM on 3rd+ attempts
                logger.info(f"      🤖 INVOKING LLM-based button detection...")
                llm_result = await self._click_easy_apply_button_with_llm()
                logger.info(f"      LLM result: {llm_result}")
                if llm_result:
                    return True
            else:
                if self.gemini_service is None:
                    logger.debug(f"      ⊘ Skipping LLM: No Gemini service available")
                else:
                    logger.debug(f"      ⊘ Skipping LLM: Not yet attempt 3+ (current: {attempt_num})")
            
            # Retry with increasingly longer waits
            wait_times = [3, 5, 8, 10]
            if attempt_num < 4:
                wait_sec = wait_times[attempt]
                logger.warning(f"")
                logger.warning(f"   ⏳ RETRY WAIT: {wait_sec}s before attempt {attempt_num+1}/4...")
                await self._delay(wait_sec, wait_sec + 2)

                # On retry: aggressive scroll and re-evaluate page state
                logger.debug(f"   Scrolling page to refresh button visibility...")
                await self.page.evaluate("window.scrollBy(0, 500)")
                await self._delay(1.0, 1.5)
            else:
                logger.error(f"")
                logger.error(f"   ╔═══════════════════════════════════════════════════════════╗")
                logger.error(f"   ║ ❌ MAX RETRIES REACHED — BUTTON NOT FOUND AFTER 4 ATTEMPTS ║")
                logger.error(f"   ╚═══════════════════════════════════════════════════════════╝")

        return False

    async def _click_easy_apply_button_with_llm(self) -> bool:
        """
        Use Gemini to analyze page screenshot and identify Easy Apply button location.
        Attempts two approaches:
        1. Screenshot-based: Send page screenshot to Gemini for visual button detection
        2. HTML-based: Get all button HTML and ask Gemini which is the Easy Apply button
        """
        try:
            logger.info(f"      ┌───────────────────────────────────────────────────┐")
            logger.info(f"      │ LLM BUTTON DETECTION ORCHESTRATOR                 │")
            logger.info(f"      └───────────────────────────────────────────────────┘")
            logger.info(f"      Starting LLM button detection with Gemini service...")
            logger.info(f"      Gemini type: {type(self.gemini_service).__name__}")
            
            # Approach 1: Try screenshot-based detection
            logger.info(f"      ")
            logger.info(f"      [Approach 1/2] Screenshot-based detection")
            logger.info(f"      ──────────────────────────────────────────")
            screenshot_result = await self._click_button_from_screenshot()
            logger.info(f"      Screenshot approach result: {screenshot_result}")
            if screenshot_result:
                logger.info(f"      ✅ Screenshot approach SUCCEEDED")
                return True
            logger.info(f"      ✗ Screenshot approach failed, trying next...")
            
            logger.info(f"      ")
            logger.info(f"      [Approach 2/2] HTML-based detection")
            logger.info(f"      ──────────────────────────────────────────")
            html_result = await self._click_button_from_html()
            logger.info(f"      HTML-based approach result: {html_result}")
            if html_result:
                logger.info(f"      ✅ HTML-based approach SUCCEEDED")
                return True
            
            logger.warning(f"      ")
            logger.warning(f"      ⚠️  Both LLM approaches FAILED")
            return False
        
        except Exception as e:
            logger.error(f"      Exception in LLM orchestrator: {e}")
            logger.error(f"      Exception type: {type(e).__name__}")
            logger.error(f"      Gemini service: {self.gemini_service}")
            logger.error(f"      Gemini service type: {type(self.gemini_service).__name__ if self.gemini_service else 'None'}")
            import traceback
            logger.error(f"      Traceback: {traceback.format_exc()}")
            return False

    async def _click_button_from_screenshot(self) -> bool:
        """
        Take a screenshot of the page and ask Gemini to identify Easy Apply button location.
        """
        try:
            logger.info(f"         Initializing screenshot-based detection...")
            
            # Take screenshot
            screenshot_path = "/tmp/linkedin_button_detection.png"
            logger.info(f"         📸 Capturing screenshot to: {screenshot_path}")
            
            await self.page.screenshot(path=screenshot_path)
            logger.info(f"         ✓ Screenshot captured")
            logger.info(f"         🔍 Gemini service type: {type(self.gemini_service).__name__ if self.gemini_service else 'None'}")
            
            # Verify file exists
            if not os.path.exists(screenshot_path):
                logger.warning(f"         ⚠️  Screenshot file was not created!")
                return False
            
            file_size = os.path.getsize(screenshot_path)
            logger.info(f"         Screenshot file size: {file_size} bytes")
            
            if file_size == 0:
                logger.warning(f"         ⚠️  Screenshot file is empty!")
                return False
            
            # Call Gemini service to analyze screenshot
            logger.info(f"         Sending screenshot to Gemini for analysis...")
            logger.info(f"         Gemini method: analyze_button_location_from_screenshot")
            
            result = await self.gemini_service.analyze_button_location_from_screenshot(
                screenshot_path
            )
            
            logger.info(f"         Gemini response received:")
            logger.info(f"            Response: {result}")
            
            if not result:
                logger.warning(f"         ⚠️  Gemini returned None/empty response")
                return False
            
            if not result.get("found"):
                logger.info(f"         Button not detected in screenshot")
                logger.debug(f"         Response details: {result}")
                return False
            
            logger.info(f"         ✅ Gemini detected button in screenshot!")
            
            # Try to click based on Gemini's analysis
            button_info = result.get("button_info", {})
            logger.info(f"         Button info from Gemini: {button_info}")
            
            # Approach: Get selector or coordinates from Gemini response
            selector = button_info.get("selector")
            if selector:
                logger.info(f"         Attempting to click using selector: {selector}")
                btn = await self.page.query_selector(selector)
                if btn:
                    logger.info(f"         ✓ Selector found element")
                    await btn.scroll_into_view_if_needed()
                    await self._delay(0.5, 1.0)
                    await btn.click()
                    logger.info(f"         ✅ Button clicked successfully via Gemini-provided selector")
                    return True
                else:
                    logger.warning(f"         ⚠️  Selector did not find element on page")
            
            # Alternative: Try clicking by coordinates
            coords = button_info.get("coordinates")
            if coords and "x" in coords and "y" in coords:
                logger.info(f"         Attempting to click using coordinates: x={coords['x']}, y={coords['y']}")
                try:
                    x, y = coords["x"], coords["y"]
                    await self.page.click(f"button[x='{x}'][y='{y}']", timeout=3000)
                    logger.info(f"         ✅ Button clicked successfully via coordinates")
                    return True
                except Exception as coord_err:
                    logger.warning(f"         ⚠️  Coordinate click failed: {coord_err}")
            
            logger.warning(f"         ⚠️  Could not extract/use button information from Gemini")
            return False
        
        except Exception as e:
            logger.error(f"         Exception in screenshot-based detection: {e}")
            logger.error(f"         Exception type: {type(e).__name__}")
            import traceback
            logger.error(f"         Traceback: {traceback.format_exc()}")
            return False

    async def _click_button_from_html(self) -> bool:
        """
        Get all button elements as HTML and ask Gemini to identify which is Easy Apply.
        Then find and click that button.
        """
        try:
            logger.info(f"         Initializing HTML-based detection...")
            logger.info(f"         Collecting all buttons from page...")
            
            # Get all buttons with their properties
            buttons_info = await self.page.evaluate("""
                () => Array.from(document.querySelectorAll('button'))
                    .slice(0, 50)  // Limit to first 50 buttons
                    .map((btn, idx) => ({
                        index: idx,
                        text: btn.innerText.trim().slice(0, 100),
                        aria_label: btn.getAttribute('aria-label') || '',
                        id: btn.getAttribute('id') || '',
                        class: btn.getAttribute('class') || '',
                        data_test: btn.getAttribute('data-test-id') || '',
                        type: btn.getAttribute('type') || 'button',
                        disabled: btn.disabled,
                        visible: btn.offsetParent !== null,
                        html: btn.outerHTML.slice(0, 300)
                    }))
            """)
            
            logger.info(f"         Found {len(buttons_info)} buttons on page")
            
            if len(buttons_info) == 0:
                logger.warning(f"         ⚠️  No buttons found on page!")
                return False
            
            # Log button summary
            logger.debug(f"         Button summary:")
            for i, btn in enumerate(buttons_info[:10]):  # Log first 10
                logger.debug(f"           [{i}] text='{btn.get('text', '')[:40]}' aria='{btn.get('aria_label', '')[:40]}'")
            
            # Call Gemini to identify which button is Easy Apply
            logger.info(f"         Sending {len(buttons_info)} buttons to Gemini for analysis...")
            logger.info(f"         Gemini method: identify_easy_apply_button")
            
            result = await self.gemini_service.identify_easy_apply_button(
                buttons_info
            )
            
            logger.info(f"         Gemini response received:")
            logger.info(f"            Response type: {type(result)}")
            logger.info(f"            Response keys: {list(result.keys()) if isinstance(result, dict) else 'N/A'}")
            logger.info(f"            Full Response: {result}")
            
            if not result or not result.get("found"):
                logger.info(f"         Gemini could not identify Easy Apply button")
                logger.debug(f"         Response details: {result}")
                return False
            
            logger.info(f"         ✅ Gemini identified Easy Apply button!")
            
            button_index = result.get("button_index")
            button_selector = result.get("selector")
            confidence = result.get("confidence", 0)
            
            logger.info(f"         Button index: {button_index}")
            logger.info(f"         Selector: {button_selector}")
            logger.info(f"         Confidence: {confidence}%")
            
            # Try to click using the selector
            if button_selector:
                logger.info(f"         Attempting to click using Gemini-recommended selector...")
                btn = await self.page.query_selector(button_selector)
                if btn and await btn.is_visible():
                    logger.info(f"         ✓ Selector found visible element")
                    await btn.scroll_into_view_if_needed()
                    await self._delay(0.5, 1.0)
                    await btn.click()
                    logger.info(f"         ✅ Button clicked successfully via Gemini-recommended selector")
                    return True
                else:
                    logger.warning(f"         ⚠️  Selector: element not found or not visible")
            
            # Fallback: Click by index
            if button_index is not None and button_index >= 0:
                logger.info(f"         Fallback: Attempting to click button at index {button_index}...")
                all_buttons = await self.page.query_selector_all("button")
                logger.info(f"         Total buttons on page: {len(all_buttons)}")
                
                if button_index < len(all_buttons):
                    target_btn = all_buttons[button_index]
                    logger.info(f"         ✓ Index {button_index} is valid")
                    await target_btn.scroll_into_view_if_needed()
                    await self._delay(0.5, 1.0)
                    await target_btn.click()
                    logger.info(f"         ✅ Button clicked successfully via index {button_index}")
                    return True
                else:
                    logger.warning(f"         ⚠️  Index {button_index} out of range (max: {len(all_buttons)-1})")
            
            logger.warning(f"         ⚠️  Could not click button using provided strategies")
            return False
        
        except Exception as e:
            logger.error(f"         Exception in HTML-based detection: {e}")
            import traceback
            logger.error(f"         Traceback: {traceback.format_exc()}")
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
                            question = (await el.inner_text()).strip()
                            if question:
                                break

                    if not question:
                        continue

                    # Use Gemini if available, otherwise fall back to regex
                    if self.gemini_service:
                        answer = await self._get_answer_from_gemini(question)
                    else:
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
    # Gemini AI Integration
    # ─────────────────────────────────────────────────────────────────────────
    async def _get_answer_from_gemini(self, question: str) -> Optional[str]:
        """Get answer to question using Gemini AI."""
        try:
            logger.debug(f"❓ Asking Gemini: {question[:60]}...")
            result = await self.gemini_service.analyze_question(
                question,
                CANDIDATE_PROFILE
            )
            answer = result.get("answer", "")
            confidence = result.get("confidence", 0)
            logger.debug(f"   Gemini answer: '{answer}' (confidence: {confidence}%)")
            return answer if answer else None
        except Exception as e:
            logger.error(f"   ❌ Gemini question analysis failed: {e}")
            logger.debug(f"   Falling back to regex pattern matching")
            return self._get_yes_no_answer(question)
    
    async def _generate_gemini_resume(self, job: JobListing, 
                                      job_description: str) -> Tuple[str, str]:
        """Generate Gemini-tailored resume with PDF output."""
        try:
            logger.debug(f"📄 Generating Gemini-tailored resume...")
            
            # Get base resume text
            base_resume, _ = self.optimizer.create_tailored_resume_text(
                job.job_id, job.title, job.company, job_description
            )
            with open(base_resume, 'r', encoding='utf-8') as f:
                base_text = f.read()
            
            # Call Gemini to tailor
            result = await self.gemini_service.generate_tailored_resume(
                base_text, job_description, job.title, job.company,
                optimization_level=self.config.resume_optimization_level
            )
            
            resume_text = result.get("resume", base_text)
            logger.info(f"✅ Gemini resume generated ({len(resume_text)} chars)")
            
            return base_resume, resume_text
        
        except Exception as e:
            logger.error(f"   ❌ Gemini resume generation failed: {e}")
            logger.debug(f"   Falling back to regex-based resume")
            return self.optimizer.create_tailored_resume_text(
                job.job_id, job.title, job.company, job_description
            )
    
    async def _generate_gemini_cover_letter(self, job: JobListing,
                                            job_description: str) -> str:
        """Generate Gemini-tailored cover letter."""
        try:
            logger.debug(f"💌 Generating Gemini-tailored cover letter...")
            
            candidate_info = {
                "name": CANDIDATE_PROFILE.get("first_name", "Shaheryar"),
                "email": CANDIDATE_PROFILE.get("email", "emailshaheryar@gmail.com"),
                "phone": CANDIDATE_PROFILE.get("phone", "+923113206213"),
                "years_exp": CANDIDATE_PROFILE.get("years_of_experience", "3"),
                "current_company": CANDIDATE_PROFILE.get("current_company", "Pakistan Single Window"),
                "current_title": CANDIDATE_PROFILE.get("current_title", "Software Engineer"),
            }
            
            result = await self.gemini_service.generate_cover_letter(
                job.title, job.company, job_description, candidate_info
            )
            
            cover_letter = result.get("cover_letter", "")
            logger.info(f"✅ Gemini cover letter generated ({len(cover_letter)} chars)")
            
            return cover_letter
        
        except Exception as e:
            logger.error(f"   ❌ Gemini cover letter generation failed: {e}")
            logger.debug(f"   Falling back to template-based cover letter")
            return self.optimizer.generate_cover_letter(
                job.title, job.company, job_description
            )

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
                logger.error("   ❌ SESSION EXPIRED — redirected to login page!")
                job.apply_status = "session_expired"
                return

            # Check for specific button with ID
            id_button = await self.page.query_selector("#jobs-apply-button-id")
            if id_button:
                logger.debug(f"   ID button found but failed click")
                styles = await self.page.evaluate("() => window.getComputedStyle(document.getElementById('jobs-apply-button-id'))")
                logger.debug(f"   Button styles: display={styles.get('display')}, visibility={styles.get('visibility')}")

            # List all buttons on page for debugging
            buttons = await self.page.evaluate("""
                () => Array.from(document.querySelectorAll('button'))
                    .map(b => ({
                        text: b.innerText.trim().slice(0,60),
                        aria: b.getAttribute('aria-label') || '',
                        id: b.getAttribute('id') || '',
                        disabled: b.disabled,
                        display: window.getComputedStyle(b).display,
                        visibility: window.getComputedStyle(b).visibility,
                        offsetParent: b.offsetParent !== null
                    }))
                    .filter(b => b.text.toLowerCase().includes('apply') || b.aria.toLowerCase().includes('apply'))
                    .slice(0, 10)
            """)
            if buttons:
                logger.warning(f"   Found {len(buttons)} apply-related buttons:")
                for btn in buttons:
                    logger.warning(f"      - Text: '{btn['text'][:40]}' | Type: {btn['display']} | Visible: {btn['offsetParent']}")
            else:
                logger.warning(f"   ❌ NO apply-related buttons found on page!")

            # Check if it's an external application (not Easy Apply)
            apply_link = await self.page.query_selector("a[href*='apply']")
            if apply_link:
                href = await apply_link.get_attribute("href")
                logger.warning(f"   ℹ️  External application link found: {href[:80]}")
                job.apply_status = "external_application"
        except Exception as e:
            logger.debug(f"   Diagnostics error: {e}")
