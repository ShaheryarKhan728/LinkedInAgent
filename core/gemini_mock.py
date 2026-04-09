"""
Gemini Mock Service (for testing)
==================================
Mock implementation while API model compatibility is being resolved.
Demonstrates the architecture - replace with real API calls when models are confirmed.

NOTE: The provided API key appears restricted. Contact Google Cloud and verify
which Gemini models are available for your API key and project.
"""

import asyncio
import json
import logging
from typing import Optional, Dict
import random

logger = logging.getLogger("gemini_mock")


class GeminiMockService:
    """Mock Gemini service for testing system architecture."""
    
    def __init__(self, api_key: str, api_tracker=None, max_calls_per_minute: int = 30):
        """Initialize mock service."""
        self.api_key = api_key
        self.api_tracker = api_tracker
        self.max_calls_per_minute = max_calls_per_minute
        self.call_count = 0
        logger.debug(f"🔧 Gemini MOCK Service initialized (for testing)")
        logger.debug(f"   WARNING: Using MOCK responses - not production ready!")
    
    async def analyze_form(self, form_html: str, job_description: str) -> Dict:
        """Mock form analysis."""
        self.call_count += 1
        logger.debug(f"📝 Mock: Analyzing form...")
        
        await asyncio.sleep(0.3)  # Simulate API latency
        
        # Generate mock response
        fields = [
            {"name": "first_name", "type": "text", "value": "Shaheryar", "confidence": 95},
            {"name": "last_name", "type": "text", "value": "Khan", "confidence": 95},
            {"name": "email", "type": "email", "value": "emailshaheryar@gmail.com", "confidence": 95},
            {"name": "phone", "type": "tel", "value": "+923113206213", "confidence": 95},
            {"name": "years_experience", "type": "select", "value": "3", "confidence": 85},
        ]
        
        if self.api_tracker:
            self.api_tracker.log_call(
                endpoint="generateContent_mock",
                model="gemini-3.1-flash-lite-preview",
                prompt_summary="analyze_form",
                response_length=len(json.dumps(fields)),
                duration_ms=300
            )
        
        logger.info(f"✅ Mock analysis: {len(fields)} fields")
        return {"fields": fields, "form_analysis": {"total_fields": len(fields)}}
    
    async def analyze_question(self, question_text: str, candidate_profile: Dict) -> Dict:
        """Mock question analysis."""
        self.call_count += 1
        logger.debug(f"❓ Mock: Analyzing question...")
        
        await asyncio.sleep(0.2)
        
        # Generate mock response
        answer = "Yes"
        confidence = random.randint(80, 98)
        
        if "authorized" in question_text.lower() or "sponsorship" in question_text.lower():
            answer = "Yes"
            confidence = 90
        elif "relocation" in question_text.lower() or "relocate" in question_text.lower():
            answer = "No"
            confidence = 95
        
        result = {
            "answer": answer,
            "confidence": confidence,
            "reasoning": f"Based on candidate profile"
        }
        
        if self.api_tracker:
            self.api_tracker.log_call(
                endpoint="analyze_question_mock",
                model="gemini-3.1-flash-lite-preview",
                prompt_summary=question_text[:50],
                response_length=len(json.dumps(result)),
                duration_ms=200
            )
        
        logger.info(f"✅ Mock answer: {answer} (confidence: {confidence}%)")
        return result
    
    async def generate_tailored_resume(self, base_resume_text: str, job_description: str,
                                       job_title: str, company: str,
                                       optimization_level: str = "light") -> Dict:
        """Mock resume tailoring."""
        self.call_count += 1
        logger.debug(f"📄 Mock: Generating tailored resume...")
        
        await asyncio.sleep(0.5)
        
        # Simple mock - just add job-specific keywords
        tailored = base_resume_text
        
        # Extract keywords from job description
        keywords = []
        common_words = ["microservices", "REST API", "Azure", "SQL Server", "RabbitMQ", "Docker"]
        for keyword in common_words:
            if keyword.lower() in job_description.lower():
                keywords.append(keyword)
        
        if optimization_level == "light" and keywords:
            tailored = f"KEYWORDS: {', '.join(keywords)}\n\n{base_resume_text}"
        elif optimization_level == "medium":
            tailored = f"[REORDERED FOR: {job_title}]\nKEYWORDS: {', '.join(keywords)}\n\n{base_resume_text}"
        
        result = {"resume": tailored, "length": len(tailored)}
        
        if self.api_tracker:
            self.api_tracker.log_call(
                endpoint="generate_resume_mock",
                model="gemini-3.1-flash-lite-preview",
                prompt_summary=f"{job_title} @ {company}",
                response_length=len(tailored),
                duration_ms=500
            )
        
        logger.info(f"✅ Mock resume generated ({len(tailored)} chars)")
        return result
    
    async def generate_cover_letter(self, job_title: str, company: str,
                                    job_description: str, candidate_info: Dict) -> Dict:
        """Mock cover letter generation."""
        self.call_count += 1
        logger.debug(f"💌 Mock: Generating cover letter...")
        
        await asyncio.sleep(0.4)
        
        cover = f"""Dear Hiring Manager,

I am writing to express my strong interest in the {job_title} position at {company}. 
With over 3 years of professional experience building production-grade .NET applications, 
I am confident in my ability to contribute meaningfully to your team from day one.

In my current role, I have designed and delivered scalable backend systems using modern 
technologies and architectural patterns. My experience aligns closely with your requirements, 
and I am excited about the opportunity to work with your team.

I would welcome the chance to discuss how my background can add value to {company}.

Best regards,
Shaheryar Khan"""
        
        result = {"cover_letter": cover, "length": len(cover)}
        
        if self.api_tracker:
            self.api_tracker.log_call(
                endpoint="generate_cover_mock",
                model="gemini-3.1-flash-lite-preview",
                prompt_summary=f"{job_title} @ {company}",
                response_length=len(cover),
                duration_ms=400
            )
        
        logger.info(f"✅ Mock cover letter generated ({len(cover)} chars)")
        return result
    
    def get_api_summary(self):
        """Get mock API summary."""
        if self.api_tracker:
            return self.api_tracker.get_summary()
        return {"total_calls": self.call_count, "mock": True}
    
    async def analyze_button_location_from_screenshot(self, screenshot_path: str) -> Dict:
        """Mock screenshot analysis for button detection."""
        self.call_count += 1
        logger.info(f"🔍 [LLM-MOCK] analyze_button_location_from_screenshot called")
        logger.info(f"   Screenshot: {screenshot_path}")
        
        await asyncio.sleep(0.3)  # Simulate API latency
        
        # Mock response indicating button found
        result = {
            "found": True,
            "description": "Blue button labeled 'Easy Apply' located at the top-right of the job detail panel",
            "selector": "button#jobs-apply-button-id",
            "coordinates": {
                "x": 85,
                "y": 20,
                "estimated": True
            },
            "confidence": 92,
            "reasoning": "Button text contains 'Easy Apply' and matches known LinkedIn styling"
        }
        
        logger.info(f"   ✅ Mock: Button detected (MOCK RESPONSE)")
        logger.info(f"   Result: found={result['found']}, selector={result['selector']}, confidence={result['confidence']}%")
        
        if self.api_tracker:
            self.api_tracker.log_call(
                endpoint="analyze_button_mock",
                model="gemini-3.1-flash-lite-preview",
                prompt_summary="analyze_button_location",
                response_length=200,
                duration_ms=300
            )
        
        return result
    
    async def identify_easy_apply_button(self, buttons_info: list) -> Dict:
        """Mock button identification from HTML."""
        self.call_count += 1
        logger.info(f"🔍 [LLM-MOCK] identify_easy_apply_button called")
        logger.info(f"   Buttons received: {len(buttons_info)}")
        
        await asyncio.sleep(0.2)
        
        # Log button preview
        for i, btn in enumerate(buttons_info[:3]):
            logger.info(f"      [{i}] text='{btn.get('text', '')[:40]}'")
        
        # Look for "Easy Apply" text in buttons
        for idx, btn in enumerate(buttons_info):
            text = btn.get("text", "").lower()
            aria = btn.get("aria_label", "").lower()
            btn_id = btn.get("id", "").lower()
            
            if "easy apply" in text or "easy apply" in aria or "apply" in btn_id:
                result = {
                    "found": True,
                    "button_index": idx,
                    "selector": f"button#{btn.get('id')}" if btn.get('id') else f"button:nth-child({idx})",
                    "confidence": 95,
                    "reasoning": f"Matched 'Easy Apply' text in button {idx}"
                }
                
                logger.info(f"   ✅ Mock: Button identified at index {idx}")
                logger.info(f"   Result: found={result['found']}, selector={result['selector']}, confidence={result['confidence']}%")
                
                if self.api_tracker:
                    self.api_tracker.log_call(
                        endpoint="identify_button_mock",
                        model="gemini-3.1-flash-lite-preview",
                        prompt_summary="identify_easy_apply_button",
                        response_length=200,
                        duration_ms=200
                    )
                
                return result
        
        # Not found
        result = {
            "found": False,
            "button_index": -1,
            "selector": None,
            "confidence": 0,
            "reasoning": "No button with 'Easy Apply' text found"
        }
        logger.warning(f"   ⚠️  Mock: Easy Apply button not found in provided list")
        return result
