"""
Gemini REST API Service
=======================
Alternative to deprecated SDK - uses REST API directly for better compatibility.
"""

import asyncio
import json
import logging
import time
import aiohttp
from typing import Optional, Dict, List

logger = logging.getLogger("gemini_rest")


class GeminiRestService:
    """Gemini API client using REST calls instead of deprecated SDK."""
    
    # REST API endpoints
    BASE_URL = "https://generativelanguage.googleapis.com/v1beta/models"
    DEFAULT_MODEL = "gemini-1.5-flash-latest"  # Latest available model
    
    def __init__(self, api_key: str, api_tracker=None, max_calls_per_minute: int = 30):
        """
        Initialize Gemini REST service.
        
        Args:
            api_key: Google Gemini API key
            api_tracker: APICallTracker instance for logging
            max_calls_per_minute: Rate limit
        """
        self.api_key = api_key
        self.api_tracker = api_tracker
        self.max_calls_per_minute = max_calls_per_minute
        self.call_times = []
        self.model = self.DEFAULT_MODEL
        
        logger.debug(f"🔧 Gemini REST Service initialized")
        logger.debug(f"   Model: {self.model}")
        logger.debug(f"   Max calls per minute: {max_calls_per_minute}")
    
    async def _enforce_rate_limit(self):
        """Enforce rate limiting."""
        now = time.time()
        self.call_times = [t for t in self.call_times if now - t < 60]
        
        if len(self.call_times) >= self.max_calls_per_minute:
            oldest_call = self.call_times[0]
            wait_time = 60 - (now - oldest_call) + 0.5
            logger.warning(f"⏱️  Rate limit approaching. Waiting {wait_time:.1f}s...")
            await asyncio.sleep(wait_time)
            self.call_times = []
        
        self.call_times.append(now)
    
    async def _make_request(self, endpoint: str, prompt: str) -> Dict:
        """
        Make async REST request to Gemini API.
        
        Args:
            endpoint: API endpoint (e.g., "generateContent")
            prompt: Prompt text
        
        Returns:
            Response dict
        """
        await self._enforce_rate_limit()
        
        url = f"{self.BASE_URL}/{self.model}:{endpoint}?key={self.api_key}"
        
        headers = {
            "Content-Type": "application/json",
        }
        
        payload = {
            "contents": [{
                "parts": [{
                    "text": prompt
                }]
            }],
            "generationConfig": {
                "temperature": 0.7,
                "maxOutputTokens": 2048,
            }
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                start_time = time.time()
                logger.debug(f"🔄 REST API call to {endpoint}...")
                
                async with session.post(url, headers=headers, json=payload, timeout=30) as resp:
                    duration = (time.time() - start_time) * 1000
                    
                    if resp.status != 200:
                        error_text = await resp.text()
                        logger.error(f"❌ API error ({resp.status}): {error_text[:200]}")
                        if self.api_tracker:
                            self.api_tracker.log_error(
                                f"api_error_{resp.status}",
                                error_text[:200],
                                endpoint
                            )
                        return {"error": f"API error {resp.status}", "raw": error_text}
                    
                    result = await resp.json()
                    
                    # Log the API call
                    response_text = json.dumps(result)
                    if self.api_tracker:
                        self.api_tracker.log_call(
                            endpoint=endpoint,
                            model=self.model,
                            prompt_summary=prompt[:100],
                            response_length=len(response_text),
                            duration_ms=duration
                        )
                    
                    logger.info(f"✅ API call successful ({duration:.0f}ms)")
                    return result
        
        except asyncio.TimeoutError:
            logger.error(f"❌ API request timeout")
            if self.api_tracker:
                self.api_tracker.log_error("timeout", "Request exceeded 30s timeout", endpoint)
            return {"error": "Request timeout"}
        
        except Exception as e:
            logger.error(f"❌ API request failed: {e}")
            if self.api_tracker:
                self.api_tracker.log_error("request_error", str(e), endpoint)
            return {"error": str(e)}
    
    async def _extract_response(self, api_response: Dict) -> str:
        """Extract text from Gemini API response."""
        try:
            if "error" in api_response:
                return ""
            
            candidates = api_response.get("candidates", [])
            if not candidates:
                logger.warning("⚠️  No candidates in response")
                return ""
            
            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                logger.warning("⚠️  No parts in response")
                return ""
            
            text = parts[0].get("text", "")
            return text
        
        except Exception as e:
            logger.error(f"❌ Error extracting response: {e}")
            return ""
    
    async def analyze_form(self, form_html: str, job_description: str) -> Dict:
        """Analyze job application form."""
        logger.debug(f"📝 Analyzing form via REST API...")
        
        prompt = f"""Analyze this job application form and return JSON.

FORM:
{form_html[:3000]}

JOB:
{job_description[:2000]}

Return JSON:
{{"fields": [{{"name": "...", "type": "text/select/radio", "value": "...", "confidence": 0-100}}], "warnings": []}}"""
        
        result = await self._make_request("generateContent", prompt)
        text = await self._extract_response(result)
        
        if not text:
            return {"fields": [], "error": result.get("error", "Empty response")}
        
        try:
            # Try to parse JSON
            return json.loads(self._extract_json(text))
        except:
            logger.debug(f"   Could not parse JSON, returning raw: {text[:200]}")
            return {"fields": [], "error": "Could not parse response", "raw_text": text}
    
    async def analyze_question(self, question_text: str, candidate_profile: Dict) -> Dict:
        """Analyze a form question."""
        logger.debug(f"❓ Analyzing question: {question_text[:60]}...")
        
        prompt = f"""Quick question analysis for form filling.

QUESTION: "{question_text}"
CANDIDATE: 3 years .NET experience, Pakistan, open to sponsorship

Return JSON only:
{{"answer": "Yes/No/value", "confidence": 0-100, "reasoning": "brief"}}"""
        
        result = await self._make_request("generateContent", prompt)
        text = await self._extract_response(result)
        
        if not text:
            return {"answer": "", "confidence": 0, "error": result.get("error")}
        
        try:
            return json.loads(self._extract_json(text))
        except:
            return {"answer": "", "confidence": 0, "raw_text": text}
    
    async def generate_tailored_resume(self, base_resume_text: str, job_description: str,
                                       job_title: str, company: str,
                                       optimization_level: str = "light") -> Dict:
        """Generate tailored resume."""
        logger.debug(f"📄 Generating tailored resume via REST API...")
        
        prompt = f"""Tailor this resume for a job. Keep the same PDF format and structure.

BASE RESUME:
{base_resume_text}

JOB: {job_title} @ {company}
DESCRIPTION:
{job_description[:2000]}

OPTIMIZATION: {optimization_level} (only add keywords if light, reorder if medium)

Return the complete tailored resume text."""
        
        result = await self._make_request("generateContent", prompt)
        text = await self._extract_response(result)
        
        if not text:
            return {"resume": base_resume_text, "error": result.get("error")}
        
        return {"resume": text, "length": len(text)}
    
    async def generate_cover_letter(self, job_title: str, company: str,
                                    job_description: str, candidate_info: Dict) -> Dict:
        """Generate cover letter."""
        logger.debug(f"💌 Generating cover letter via REST API...")
        
        prompt = f"""Write a concise (200-250 words) cover letter for this job.

POSITION: {job_title} @ {company}
REQUIREMENTS:
{job_description[:1500]}

CANDIDATE:
- Name: Shaheryar Khan
- Experience: 3 years .NET development
- Highlights: Microservices, SQL Server, RabbitMQ, team player

Make it professional, genuine, and personalized."""
        
        result = await self._make_request("generateContent", prompt)
        text = await self._extract_response(result)
        
        if not text:
            return {"cover_letter": "", "error": result.get("error")}
        
        return {"cover_letter": text, "length": len(text)}
    
    async def analyze_button_location_from_screenshot(self, screenshot_path: str) -> Dict:
        """
        Analyze screenshot to find Easy Apply button.
        REST version requires uploading the image to Files API first.
        """
        logger.debug(f"📸 REST: Analyzing screenshot for button (not yet implemented with REST)")
        
        # Note: REST API screenshot analysis would require using Files API to upload image first
        # This is a placeholder - proper implementation would:
        # 1. Upload image to Files API
        # 2. Make generateContent request with image reference
        # For now, return not found to fall back to HTML-based detection
        return {
            "found": False,
            "error": "Screenshot analysis not yet implemented for REST API",
            "message": "Falling back to HTML-based detection"
        }
    
    async def identify_easy_apply_button(self, buttons_info: List[Dict]) -> Dict:
        """Identify Easy Apply button from HTML button list using REST API."""
        logger.debug(f"🔍 REST: Identifying Easy Apply button from {len(buttons_info)} buttons...")
        
        # Prepare button list for Gemini
        buttons_text = "\n".join([
            f"Button {i}: text='{b.get('text', '')}', aria='{b.get('aria_label', '')}', id='{b.get('id', '')}'"
            for i, b in enumerate(buttons_info[:20])
        ])
        
        prompt = f"""Identify which button is the LinkedIn Easy Apply button.

BUTTONS:
{buttons_text}

Look for "Easy Apply" text and return JSON:
{{"found": true/false, "button_index": <number or -1>, "selector": "...", "confidence": <0-100>}}"""
        
        result = await self._make_request("generateContent", prompt)
        text = await self._extract_response(result)
        
        if not text:
            return {"found": False, "button_index": -1, "confidence": 0, "error": result.get("error")}
        
        try:
            parsed = json.loads(self._extract_json(text))
            return parsed
        except:
            return {"found": False, "button_index": -1, "confidence": 0, "error": "Failed to parse response"}
    
    def _extract_json(self, text: str) -> str:
        """Extract JSON from text."""
        if "```json" in text:
            start = text.find("```json") + 7
            end = text.find("```", start)
            return text[start:end].strip()
        elif "```" in text:
            start = text.find("```") + 3
            end = text.find("```", start)
            return text[start:end].strip()
        return text.strip()
