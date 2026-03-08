"""
PDF Validator
=============
Validates generated PDF files for integrity, readability, and size.
"""

import logging
import os
from pathlib import Path

try:
    from PyPDF2 import PdfReader
    PDF_VALIDATION_AVAILABLE = True
except ImportError:
    PDF_VALIDATION_AVAILABLE = False

logger = logging.getLogger("pdf_validator")


class PDFValidator:
    """Validate PDF files for quality and integrity."""
    
    def __init__(self, max_size_mb: float = 5.0, max_pages: int = 2):
        """
        Initialize validator.
        
        Args:
            max_size_mb: Maximum file size in MB
            max_pages: Maximum allowed pages
        """
        self.max_size_bytes = max_size_mb * 1024 * 1024
        self.max_pages = max_pages
        logger.debug(f"🔍 PDF Validator initialized")
        logger.debug(f"   Max size: {max_size_mb}MB")
        logger.debug(f"   Max pages: {max_pages}")
        if not PDF_VALIDATION_AVAILABLE:
            logger.warning(f"⚠️  PyPDF2 not available - basic validation only")
    
    def validate_pdf(self, pdf_path: str, max_size_mb: float = None, 
                     max_pages: int = None) -> tuple:
        """
        Validate a PDF file.
        
        Args:
            pdf_path: Path to PDF file
            max_size_mb: Override max size
            max_pages: Override max pages
        
        Returns:
            Tuple of (is_valid, errors_list)
        """
        logger.debug(f"🔍 Validating PDF: {pdf_path}")
        
        errors = []
        max_sz = max_size_mb * 1024 * 1024 if max_size_mb else self.max_size_bytes
        max_pg = max_pages if max_pages else self.max_pages
        
        # Check file exists
        if not os.path.exists(pdf_path):
            error = f"PDF file does not exist: {pdf_path}"
            logger.error(f"❌ {error}")
            errors.append(error)
            return False, errors
        
        logger.debug(f"✓ File exists")
        
        # Check file size
        file_size = os.path.getsize(pdf_path)
        logger.debug(f"   File size: {file_size} bytes ({file_size / 1024:.1f}KB)")
        
        if file_size == 0:
            error = "PDF file is empty (0 bytes)"
            logger.error(f"❌ {error}")
            errors.append(error)
            return False, errors
        
        if file_size > max_sz:
            error = f"PDF too large: {file_size / 1024 / 1024:.1f}MB > {max_sz / 1024 / 1024:.1f}MB limit"
            logger.warning(f"⚠️  {error}")
            errors.append(error)
        
        logger.debug(f"✓ File size validation passed")
        
        # Check if readable as PDF
        if PDF_VALIDATION_AVAILABLE:
            try:
                reader = PdfReader(pdf_path)
                num_pages = len(reader.pages)
                logger.debug(f"   Number of pages: {num_pages}")
                
                if num_pages == 0:
                    error = "PDF has no pages"
                    logger.error(f"❌ {error}")
                    errors.append(error)
                    return False, errors
                
                if num_pages > max_pg:
                    error = f"PDF has too many pages: {num_pages} > {max_pg}"
                    logger.warning(f"⚠️  {error}")
                    errors.append(error)
                
                # Try to extract text
                has_text = False
                for i, page in enumerate(reader.pages[:1]):  # Check first page
                    text = page.extract_text()
                    if text and len(text.strip()) > 10:
                        has_text = True
                        logger.debug(f"✓ Page {i} has readable text ({len(text)} chars)")
                        break
                
                if not has_text:
                    logger.warning(f"⚠️  No readable text found in PDF")
                
                logger.debug(f"✓ PDF structure validation passed")
                logger.info(f"✅ PDF is valid: {num_pages} pages, {file_size / 1024:.1f}KB")
                
                return len(errors) == 0, errors
            
            except Exception as e:
                error = f"Cannot read PDF: {str(e)}"
                logger.error(f"❌ {error}")
                errors.append(error)
                return False, errors
        
        else:
            logger.debug(f"⚠️  Skipping detailed validation (PyPDF2 not available)")
            logger.info(f"✅ PDF basic validation passed: {file_size / 1024:.1f}KB")
            return len(errors) == 0, errors
    
    def validate_pdf_with_backup(self, pdf_path: str, text_backup_path: str = None) -> dict:
        """
        Validate PDF and return backup info.
        
        Args:
            pdf_path: PDF file path
            text_backup_path: Text backup file path (optional)
        
        Returns:
            Dict with validation results
        """
        logger.debug(f"🔍 Validating PDF with backup...")
        
        is_valid, errors = self.validate_pdf(pdf_path)
        
        has_backup = False
        backup_size = 0
        if text_backup_path and os.path.exists(text_backup_path):
            has_backup = True
            backup_size = os.path.getsize(text_backup_path)
        
        result = {
            "pdf_path": pdf_path,
            "is_valid": is_valid,
            "errors": errors,
            "file_size": os.path.getsize(pdf_path) if os.path.exists(pdf_path) else 0,
            "has_backup": has_backup,
            "backup_path": text_backup_path if has_backup else None,
            "backup_size": backup_size
        }
        
        if is_valid:
            logger.info(f"✅ PDF validation passed")
        else:
            logger.warning(f"⚠️  PDF validation failed: {errors}")
        
        return result
