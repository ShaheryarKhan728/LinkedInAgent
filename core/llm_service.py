"""
Gemini LLM Service (with fallback support)
===========================================
Wraps Google GenerativeAI Gemini API with aggressive logging, rate limiting, and error handling.
Includes fallback to REST API and mock service if needed.
"""

import asyncio
import json
import logging
import time
from typing import Optional, Dict, List
from datetime import datetime

logger = logging.getLogger("llm_service")

# Try to import Gemini SDK, but don't fail if unavailable
try:
    import google.generativeai as genai
    GEMINI_SDK_AVAILABLE = True
except ImportError:
    GEMINI_SDK_AVAILABLE = False
    logger.warning("⚠️  google.generativeai not available, will use fallback services")

class GeminiService:
    """Gemini API wrapper with rate limiting and aggressive logging."""
    
    def __init__(self, api_key: str, api_tracker=None, max_calls_per_minute: int = 30):
        """
        Initialize Gemini service.
        
        Args:
            api_key: Google Gemini API key
            api_tracker: APICallTracker instance for logging
            max_calls_per_minute: Rate limit (free tier default: 30/min)
        """
        self.api_key = api_key
        self.api_tracker = api_tracker
        self.max_calls_per_minute = max_calls_per_minute
        self.call_times = []  # Track call times for rate limiting
        # Using latest available model with confirmed API key access
        self.model = "gemini-3.1-flash-lite-preview"  # Updated model with working API access
        
        # Configure Gemini
        genai.configure(api_key=api_key)
        logger.debug(f"🔧 Gemini service initialized with model: {self.model}")
        logger.debug(f"   Max calls per minute: {max_calls_per_minute}")
        logger.debug(f"   ⚠️  Using deprecated google-generativeai package")
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting - wait if necessary."""
        now = time.time()
        # Remove calls older than 1 minute
        self.call_times = [t for t in self.call_times if now - t < 60]
        
        if len(self.call_times) >= self.max_calls_per_minute:
            oldest_call = self.call_times[0]
            wait_time = 60 - (now - oldest_call) + 0.5
            logger.warning(f"⏱️  Rate limit approaching. Waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            self.call_times = []  # Reset
        
        self.call_times.append(now)
    
    async def analyze_form(self, form_html: str, job_description: str) -> Dict:
        """
        Analyze job application form and suggest field mappings.
        
        Args:
            form_html: HTML content of the form
            job_description: Full job description text
        
        Returns:
            Dict with field mappings and suggestions
        """
        logger.debug(f"📝 Starting form analysis...")
        logger.debug(f"   Form HTML length: {len(form_html)} chars")
        logger.debug(f"   Job description length: {len(job_description)} chars")
        
        await self._enforce_rate_limit()
        
        prompt = f"""You are an expert form filler for LinkedIn job applications.

Analyze the following job application form and job description. 
Provide structured JSON output with field mappings and suggested values.

FORM HTML:
{form_html[:5000]}

JOB DESCRIPTION:
{job_description[:2000]}

CANDIDATE PROFILE:
- Name: Shaheryar Khan
- Email: emailshaheryar@gmail.com
- Phone: +923113206213
- Experience: 2+ years .NET development
- Location: Pakistan
- Open to: Remote work
- Authorized: No (but looking for sponsorship)

TASK:
1. Identify all form fields
2. For each field, provide:
   - field_name (HTML input name or label)
   - field_type (text, select, radio, checkbox, file)
   - suggested_value (what to fill)
   - confidence (0-100, how sure you are)
3. Mark any questions that might indicate values or constraints
4. Return ONLY valid JSON, no markdown or extra text

Return format:
{{
  "fields": [
    {{"name": "...", "type": "...", "value": "...", "confidence": ...}},
    ...
  ],
  "form_analysis": {{"total_fields": ..., "required_fields": ...}},
  "warnings": ["any issues found"]
}}"""
        
        try:
            start_time = time.time()
            logger.debug(f"🔄 Calling Gemini API for form analysis...")
            
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            
            duration = (time.time() - start_time) * 1000
            response_text = response.text
            
            logger.debug(f"📦 Gemini response received ({len(response_text)} chars) in {duration:.0f}ms")
            
            # Log API call
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent",
                    model=self.model,
                    prompt_summary="analyze_form",
                    response_length=len(response_text),
                    duration_ms=duration
                )
            
            # Parse JSON
            try:
                # Try to extract JSON from response
                result = self._extract_json(response_text)
                logger.info(f"✅ Form analysis complete: {len(result.get('fields', []))} fields detected")
                logger.debug(f"   Field names: {[f['name'] for f in result.get('fields', [])]}")
                return result
            except json.JSONDecodeError as e:
                logger.error(f"❌ Failed to parse Gemini JSON response: {e}")
                logger.debug(f"   Raw response: {response_text[:500]}")
                if self.api_tracker:
                    self.api_tracker.log_error("json_parse_error", str(e), "analyze_form")
                return {"fields": [], "error": "Failed to parse response", "raw": response_text}
        
        except Exception as e:
            logger.error(f"❌ Gemini API error in analyze_form: {e}")
            if self.api_tracker:
                self.api_tracker.log_error("api_error", str(e), "analyze_form")
            return {"fields": [], "error": str(e)}
    
    async def analyze_question(self, question_text: str, candidate_profile: Dict) -> Dict:
        """
        Analyze a single question and suggest answer.
        
        Args:
            question_text: The question text
            candidate_profile: Candidate's profile info
        
        Returns:
            Dict with suggested answer and confidence
        """
        logger.debug(f"❓ Analyzing question: {question_text[:60]}...")
        
        await self._enforce_rate_limit()
        
        prompt = f"""You are an expert in answering LinkedIn job application questions 
for a .NET software engineer with 2+ years experience.

QUESTION: "{question_text}"

CANDIDATE PROFILE:
- Name: Shaheryar Khan
- Email: emailshaheryar@gmail.com
- Phone: +923113206213
- Years of Experience: 3 years
- Technologies: C#, .NET Core, SQL Server, RabbitMQ, Azure
- Location: Pakistan (willing to work remote)
- Education: Bachelor of Computer Science
- Open to Sponsorship: Yes
- Open to Relocation: No

TASK:
1. Understand what the question is really asking
2. Provide the BEST answer based on candidate profile
3. If Yes/No question, answer: "Yes" or "No"
4. If text question, provide brief answer (1-3 words)
5. If multiple choice, pick the best option
6. Provide confidence score (0-100)

Return ONLY valid JSON:
{{"answer": "...", "confidence": ..., "reasoning": "..."}}"""
        
        try:
            start_time = time.time()
            logger.debug(f"🔄 Calling Gemini API for question analysis...")
            
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            
            duration = (time.time() - start_time) * 1000
            response_text = response.text
            
            logger.debug(f"📦 Gemini response received ({len(response_text)} chars) in {duration:.0f}ms")
            
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent",
                    model=self.model,
                    prompt_summary="analyze_question",
                    response_length=len(response_text),
                    duration_ms=duration
                )
            
            result = self._extract_json(response_text)
            logger.info(f"✅ Question analysis: answer='{result.get('answer')}' confidence={result.get('confidence')}%")
            return result
        
        except Exception as e:
            logger.error(f"❌ Gemini API error in analyze_question: {e}")
            if self.api_tracker:
                self.api_tracker.log_error("api_error", str(e), "analyze_question")
            return {"answer": "", "confidence": 0, "error": str(e)}
    
    async def generate_tailored_resume(self, base_resume_text: str, job_description: str,
                                       job_title: str, company: str,
                                       optimization_level: str = "light") -> Dict:
        """
        Generate a tailored resume for a specific job.
        
        Args:
            base_resume_text: Original resume text
            job_description: Job description to tailor to
            job_title: Job title
            company: Company name
            optimization_level: "light" (keywords only) or "medium" (reorder + keywords)
        
        Returns:
            Dict with tailored resume text
        """
        logger.debug(f"📄 Generating tailored resume...")
        logger.debug(f"   Job: {job_title} @ {company}")
        logger.debug(f"   Optimization level: {optimization_level}")
        logger.debug(f"   Base resume length: {len(base_resume_text)} chars")
        
        await self._enforce_rate_limit()
        
        if optimization_level == "light":
            optimization_prompt = """Light optimization means:
- Keep the resume structure EXACTLY as is
- Add relevant keywords from the job description to existing bullet points
- Do NOT rewrite or reorder sections
- Enhance existing experience, don't create new ones
- Make it look like minor additions, not a rewrite"""
        else:  # medium
            optimization_prompt = """Medium optimization means:
- Reorder experience sections by relevance to this job
- Rewrite 2-3 key bullet points to emphasize relevant skills
- Add job-specific keywords naturally
- Balance between tailoring and keeping authenticity
- Keep maximum 1.5 pages"""
        
        prompt = f"""You are an ATS (Applicant Tracking System) and resume optimization expert.

TASK: Tailor this resume for a specific job while keeping the EXACT PDF format and structure.

BASE RESUME (in PDF format):
{base_resume_text}

JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION:
{job_description[:2500]}

OPTIMIZATION LEVEL: {optimization_level}

INSTRUCTIONS:
{optimization_prompt}

⚠️ CRITICAL CONSTRAINTS:
1. PRESERVE the exact resume formatting and structure
2. Do NOT change section headings or fundamental layout
3. Instead of rewriting, ENHANCE existing bullets
4. Add keywords naturally into existing content
5. Try to keep it around 1.5 pages max
6. Maintain the professional tone

EXAMPLE of light enhancement:
Original: "Built REST APIs using .NET Core"
Tailored: "Built highly scalable REST APIs using .NET Core with microservices architecture"

Return ONLY the complete tailored resume text, with no additional explanation."""
        
        try:
            start_time = time.time()
            logger.debug(f"🔄 Calling Gemini API for resume tailoring...")
            
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            
            duration = (time.time() - start_time) * 1000
            tailored_resume = response.text
            
            logger.debug(f"📦 Gemini response received ({len(tailored_resume)} chars) in {duration:.0f}ms")
            
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent",
                    model=self.model,
                    prompt_summary="generate_tailored_resume",
                    response_length=len(tailored_resume),
                    duration_ms=duration
                )
            
            logger.info(f"✅ Tailored resume generated ({len(tailored_resume)} chars)")
            return {"resume": tailored_resume, "length": len(tailored_resume)}
        
        except Exception as e:
            logger.error(f"❌ Gemini API error in generate_tailored_resume: {e}")
            if self.api_tracker:
                self.api_tracker.log_error("api_error", str(e), "generate_tailored_resume")
            return {"resume": base_resume_text, "error": str(e)}
    
    async def generate_cover_letter(self, job_title: str, company: str,
                                    job_description: str, candidate_info: Dict) -> Dict:
        """
        Generate a tailored cover letter.
        
        Args:
            job_title: Job position title
            company: Company name
            job_description: Full job description
            candidate_info: Candidate information dict
        
        Returns:
            Dict with generated cover letter
        """
        logger.debug(f"💌 Generating cover letter...")
        logger.debug(f"   Job: {job_title} @ {company}")
        logger.debug(f"   Job description length: {len(job_description)} chars")
        
        await self._enforce_rate_limit()
        
        prompt = f"""You are an expert cover letter writer for tech professionals.

Write a professional, compelling cover letter for the following position:

JOB TITLE: {job_title}
COMPANY: {company}

JOB DESCRIPTION:
{job_description[:2500]}

CANDIDATE PROFILE:
- Name: {candidate_info.get('name', 'Shaheryar Khan')}
- Email: {candidate_info.get('email', 'emailshaheryar@gmail.com')}
- Phone: {candidate_info.get('phone', '+923113206213')}
- Technologies: C#, .NET Core, SQL Server, RabbitMQ, Azure, Microservices, REST APIs
- Current Company: {candidate_info.get('current_company', 'Pakistan Single Window')}
- Current Title: {candidate_info.get('current_title', 'Software Engineer')}
- Location: United States (Remote preferred)
- Key Achievement: Architected microservices for 100K+ users

REQUIREMENTS:
1. Length: 200-250 words (concise and scannable)
2. Tone: Professional, enthusiastic, but genuine
3. Structure:
   - Opening: Express interest in the specific role and company
   - Body: 2-3 paragraphs highlighting how your experience matches the job
   - Closing: Call to action
4. Make it human and personalized (not generic template)
5. Highlight relevant technical skills and achievements
6. Show understanding of the role requirements

Return ONLY the cover letter text, no additional formatting or explanation."""
        
        try:
            start_time = time.time()
            logger.debug(f"🔄 Calling Gemini API for cover letter generation...")
            
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            
            duration = (time.time() - start_time) * 1000
            cover_letter = response.text
            
            logger.debug(f"📦 Gemini response received ({len(cover_letter)} chars) in {duration:.0f}ms")
            
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent",
                    model=self.model,
                    prompt_summary="generate_cover_letter",
                    response_length=len(cover_letter),
                    duration_ms=duration
                )
            
            logger.info(f"✅ Cover letter generated ({len(cover_letter)} chars, ~{len(cover_letter) // 5} words)")
            return {"cover_letter": cover_letter, "length": len(cover_letter)}
        
        except Exception as e:
            logger.error(f"❌ Gemini API error in generate_cover_letter: {e}")
            if self.api_tracker:
                self.api_tracker.log_error("api_error", str(e), "generate_cover_letter")
            return {"cover_letter": "", "error": str(e)}
    
    async def analyze_button_location_from_screenshot(self, screenshot_path: str) -> Dict:
        """
        Analyze a screenshot to identify the Easy Apply button location.
        
        Args:
            screenshot_path: Path to the screenshot file
        
        Returns:
            Dict with button location info and selector/coordinates
        """
        logger.info(f"🔍 [LLM-GEMINI] analyze_button_location_from_screenshot called")
        logger.info(f"   Screenshot path: {screenshot_path}")
        
        try:
            # Check if file exists
            import os
            if not os.path.exists(screenshot_path):
                logger.error(f"❌ Screenshot file not found: {screenshot_path}")
                return {"found": False, "error": "File not found"}
            
            file_size = os.path.getsize(screenshot_path)
            logger.info(f"   File size: {file_size} bytes")
            
            await self._enforce_rate_limit()
            
            # Read screenshot as binary
            with open(screenshot_path, "rb") as f:
                screenshot_data = f.read()
            
            logger.info(f"   Read {len(screenshot_data)} bytes from file")
            
            prompt = """You are an expert at identifying UI elements in screenshots.

TASK: Analyze this LinkedIn job page screenshot and identify the "Easy Apply" button.

INSTRUCTIONS:
1. Look for a button with text containing "Easy Apply"
2. Describe its location on the page (top, right, blue color, etc.)
3. Provide a CSS selector that might work to locate it
4. If you can estimate coordinates, provide them as percentages (0-100) or pixels
5. Assess confidence in finding the button (0-100%)

Return ONLY valid JSON:
{
  "found": true/false,
  "description": "Location and appearance of the button...",
  "selector": "CSS selector to find the button (e.g., 'button.apply-btn')",
  "coordinates": {
    "x": pixel_x_or_percentage,
    "y": pixel_y_or_percentage,
    "estimated": true/false
  },
  "confidence": 85,
  "reasoning": "Why you think this is the Easy Apply button..."
}"""
            
            start_time = time.time()
            logger.info(f"   🔄 Calling Gemini API with screenshot Vision support...")
            logger.info(f"   Model: {self.model}")
            
            model = genai.GenerativeModel(self.model)
            
            # Use Vision API with the screenshot
            logger.info(f"   Sending screenshot to Gemini with prompt...")
            response = model.generate_content([
                prompt,
                {
                    "mime_type": "image/png",
                    "data": screenshot_data
                }
            ])
            
            duration = (time.time() - start_time) * 1000
            response_text = response.text
            
            logger.info(f"   ✅ API Response received in {duration:.0f}ms")
            logger.info(f"   Response length: {len(response_text)} chars")
            logger.debug(f"   Response text: {response_text[:500]}")
            
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent (vision)",
                    model=self.model,
                    prompt_summary="analyze_button_location",
                    response_length=len(response_text),
                    duration_ms=duration
                )
            
            result = self._extract_json(response_text)
            logger.info(f"   Parsed JSON result:")
            logger.info(f"      found: {result.get('found')}")
            logger.info(f"      confidence: {result.get('confidence', 0)}%")
            logger.info(f"      selector: {result.get('selector', 'N/A')}")
            
            if result.get("found"):
                logger.info(f"   ✅ Button detected!")
            else:
                logger.warning(f"   ⚠️  Button not detected in screenshot")
            
            return result
        
        except Exception as e:
            logger.error(f"   ❌ Exception in analyze_button_location_from_screenshot: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            if self.api_tracker:
                self.api_tracker.log_error("screenshot_analysis_error", str(e), "analyze_button_location")
            return {"found": False, "error": str(e)}
    
    async def identify_easy_apply_button(self, buttons_info: List[Dict]) -> Dict:
        """
        Analyze button HTML elements and identify which is the Easy Apply button.
        
        Args:
            buttons_info: List of button dictionaries with text, aria-label, id, etc.
        
        Returns:
            Dict with button index, selector, and confidence
        """
        logger.info(f"🔍 [LLM-GEMINI] identify_easy_apply_button called")
        logger.info(f"   Analyzing {len(buttons_info)} buttons...")
        
        await self._enforce_rate_limit()
        
        # Prepare button list for Gemini
        buttons_text = "\n".join([
            f"Button {i}: text='{b.get('text', '')}', aria='{b.get('aria_label', '')}', id='{b.get('id', '')}', class='{b.get('class', '')[:100]}'"
            for i, b in enumerate(buttons_info[:20])  # Limit to first 20
        ])
        
        logger.info(f"   Button list preview:")
        for i, b in enumerate(buttons_info[:5]):
            logger.info(f"      [{i}] text='{b.get('text', '')[:50]}'")
        
        prompt = f"""You are an expert at identifying UI buttons.

TASK: Identify which button is the LinkedIn "Easy Apply" button.

BUTTONS ON PAGE:
{buttons_text}

ANALYSIS RULES:
1. Look for text containing "apply" (case-insensitive)
2. Specifically look for "easy apply" in text or aria-label
3. Consider button styling, ID, and data attributes
4. Easy Apply buttons typically have:
   - Text: "Easy Apply", "easy apply button"
   - Aria labels mentioning "apply"
   - IDs containing "apply"

RETURN: JSON with:
- button_index: which button number (0-based, or -1 if not found)
- selector: CSS selector to locate it (e.g., "button#jobs-apply-button-id")
- confidence: 0-100 confidence score
- reasoning: why this is the Easy Apply button

If not found, return {{"found": false, "button_index": -1, "confidence": 0}}

Return ONLY valid JSON:
{{
  "found": true/false,
  "button_index": <number or -1>,
  "selector": "CSS selector...",
  "confidence": <0-100>,
  "reasoning": "..."
}}"""
        
        try:
            start_time = time.time()
            logger.info(f"   🔄 Calling Gemini API for button identification...")
            logger.info(f"   Model: {self.model}")
            logger.info(f"   Sending {len(buttons_info)} buttons to Gemini...")
            
            model = genai.GenerativeModel(self.model)
            response = model.generate_content(prompt)
            
            duration = (time.time() - start_time) * 1000
            response_text = response.text
            
            logger.info(f"   ✅ API Response received in {duration:.0f}ms")
            logger.info(f"   Response length: {len(response_text)} chars")
            logger.debug(f"   Response text: {response_text[:500]}")
            
            if self.api_tracker:
                self.api_tracker.log_call(
                    endpoint="generateContent",
                    model=self.model,
                    prompt_summary="identify_easy_apply_button",
                    response_length=len(response_text),
                    duration_ms=duration
                )
            
            result = self._extract_json(response_text)
            logger.info(f"   Parsed JSON result:")
            logger.info(f"      found: {result.get('found')}")
            logger.info(f"      button_index: {result.get('button_index', -1)}")
            logger.info(f"      selector: {result.get('selector', 'N/A')}")
            logger.info(f"      confidence: {result.get('confidence', 0)}%")
            
            if result.get("found"):
                logger.info(f"   ✅ Button identified at index {result.get('button_index')}")
            else:
                logger.warning(f"   ⚠️  Could not identify Easy Apply button")
            
            return result
        
        except Exception as e:
            logger.error(f"   ❌ Exception in identify_easy_apply_button: {e}")
            import traceback
            logger.error(f"   Traceback: {traceback.format_exc()}")
            if self.api_tracker:
                self.api_tracker.log_error("button_identification_error", str(e), "identify_easy_apply_button")
            return {"found": False, "button_index": -1, "confidence": 0, "error": str(e)}
    
    def _extract_json(self, text: str) -> Dict:
        """Extract JSON from Gemini response (handles markdown code blocks)."""
        # Try to extract JSON from markdown code blocks
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            text = text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            text = text[start:end].strip()
        
        # Clean up any leading/trailing whitespace
        text = text.strip()
        
        logger.debug(f"🔍 Extracting JSON from response ({len(text)} chars)")
        return json.loads(text)
    
    def get_api_summary(self):
        """Get API usage summary."""
        if self.api_tracker:
            return self.api_tracker.get_summary()
        return {"total_calls": 0, "errors": 0}


async def create_gemini_service(api_key: str, api_tracker=None, force_mock: bool = False):
    """
    Factory function to create appropriate Gemini service.
    
    Tries real service first, falls back to REST or mock if needed.
    
    Args:
        api_key: Google Gemini API key
        api_tracker: API call tracker
        force_mock: Force mock service (for testing)
    
    Returns:
        Service instance (GeminiService, REST, or Mock)
    """
    if force_mock:
        logger.info("⚠️  Using MOCK Gemini service (for testing)")
        from core.gemini_mock import GeminiMockService
        return GeminiMockService(api_key, api_tracker)
    
    # Try SDK first if available
    if GEMINI_SDK_AVAILABLE:
        try:
            logger.info("🔧 Attempting to use Gemini SDK...")
            service = GeminiService(api_key, api_tracker)
            logger.info("✅ Using Gemini SDK service")
            return service
        except Exception as e:
            logger.warning(f"⚠️  Gemini SDK failed: {e}")
    
    # Try REST API
    try:
        logger.info("🔄 Attempting to use Gemini REST API...")
        from core.gemini_rest import GeminiRestService
        service = GeminiRestService(api_key, api_tracker)
        logger.info("✅ Using Gemini REST service")
        return service
    except Exception as e:
        logger.warning(f"⚠️  Gemini REST API failed: {e}")
    
    # Fall back to mock
    logger.warning("⚠️  Falling back to MOCK Gemini service")
    from core.gemini_mock import GeminiMockService
    return GeminiMockService(api_key, api_tracker)
