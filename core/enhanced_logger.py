"""
Enhanced Logging with API Call Tracking
========================================
Aggressive logging from start, API call counter, and detailed request/response logging.
"""

import logging
import os
from datetime import datetime
from pathlib import Path

class APICallTracker:
    """Track all Gemini API calls with counts and details."""
    
    def __init__(self):
        self.call_count = 0
        self.calls_log = []
        self.errors = []
    
    def log_call(self, endpoint: str, model: str, prompt_summary: str, 
                 response_length: int, duration_ms: float, status: str = "success"):
        """Log a single API call."""
        self.call_count += 1
        call_entry = {
            "timestamp": datetime.now().isoformat(),
            "call_number": self.call_count,
            "endpoint": endpoint,
            "model": model,
            "prompt_summary": prompt_summary[:100],  # First 100 chars
            "response_length": response_length,
            "duration_ms": duration_ms,
            "status": status
        }
        self.calls_log.append(call_entry)
        return self.call_count
    
    def log_error(self, error_type: str, error_msg: str, context: str = ""):
        """Log an API error."""
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "error_msg": error_msg[:200],
            "context": context[:200]
        }
        self.errors.append(error_entry)
    
    def get_summary(self):
        """Get summary of API calls."""
        return {
            "total_calls": self.call_count,
            "errors": len(self.errors),
            "calls_by_status": self._count_by_status(),
        }
    
    def _count_by_status(self):
        """Count calls by status."""
        status_map = {}
        for call in self.calls_log:
            status = call.get("status", "unknown")
            status_map[status] = status_map.get(status, 0) + 1
        return status_map
    
    def print_summary(self):
        """Print API call summary."""
        summary = self.get_summary()
        print(f"\n{'=' * 60}")
        print(f"API CALL SUMMARY")
        print(f"{'=' * 60}")
        print(f"Total API Calls: {summary['total_calls']}")
        print(f"Errors: {summary['errors']}")
        print(f"Status Breakdown: {summary['calls_by_status']}")
        print(f"{'=' * 60}\n")


def setup_enhanced_logger(name: str, log_dir: str = "logs") -> tuple:
    """
    Setup enhanced logger with aggressive logging + API tracking.
    Returns: (logger, api_tracker)
    """
    os.makedirs(log_dir, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_file = os.path.join(log_dir, f"agent_{timestamp}.log")
    api_tracker_file = os.path.join(log_dir, f"api_calls_{timestamp}.log")

    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Capture everything
    
    # Clear any existing handlers
    logger.handlers = []

    # Console handler - INFO level
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    cl_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s", 
        "%H:%M:%S"
    )
    ch.setFormatter(cl_format)

    # File handler - DEBUG level (aggressive logging)
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh_format = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s:%(funcName)s:%(lineno)d - %(message)s",
        "%Y-%m-%d %H:%M:%S"
    )
    fh.setFormatter(fh_format)

    # Separate API call logger
    api_fh = logging.FileHandler(api_tracker_file, encoding="utf-8")
    api_fh.setLevel(logging.INFO)
    api_fh.setFormatter(fh_format)

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.addHandler(api_fh)
    
    # Aggressive logging - log startup
    logger.debug(f"🚀 Enhanced logger initialized for '{name}'")
    logger.debug(f"   Main log: {log_file}")
    logger.debug(f"   API calls log: {api_tracker_file}")

    api_tracker = APICallTracker()
    return logger, api_tracker


def log_api_call(logger, api_tracker, endpoint: str, model: str, 
                 prompt_summary: str, response_length: int, duration_ms: float):
    """Log an API call with all details."""
    call_num = api_tracker.log_call(endpoint, model, prompt_summary, response_length, duration_ms)
    logger.debug(
        f"📡 API Call #{call_num}: {endpoint} | Model: {model} | "
        f"Response: {response_length}B | Duration: {duration_ms:.0f}ms"
    )
    logger.info(
        f"✓ Gemini API Call #{call_num} completed successfully"
    )


def log_api_error(logger, api_tracker, error_type: str, error_msg: str, context: str = ""):
    """Log an API error."""
    api_tracker.log_error(error_type, error_msg, context)
    logger.error(
        f"❌ API Error ({error_type}): {error_msg[:100]} | Context: {context[:100]}"
    )
