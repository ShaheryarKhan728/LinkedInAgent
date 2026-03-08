"""
PDF Generator
=============
Converts text resume/cover letter to professional PDF using reportlab.
Preserves format and styling.
"""

import logging
import os
from io import BytesIO
from pathlib import Path
from datetime import datetime

from reportlab.lib.pagesizes import letter, A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, PageBreak, Table, TableStyle
from reportlab.lib import colors
from reportlab.pdfgen import canvas

logger = logging.getLogger("pdf_generator")


class PDFGenerator:
    """Generate professional PDFs from text content."""
    
    def __init__(self, output_dir: str = "resumes/tailored"):
        self.output_dir = output_dir
        os.makedirs(output_dir, exist_ok=True)
        logger.debug(f"📄 PDF Generator initialized. Output dir: {output_dir}")
    
    def generate_resume_pdf(self, resume_text: str, job_id: str, company: str, 
                           output_filename: str = None) -> tuple:
        """
        Generate resume PDF from text.
        
        Args:
            resume_text: Plain text resume
            job_id: Job ID for naming
            company: Company name for naming
            output_filename: Optional filename override
        
        Returns:
            Tuple of (pdf_path, success)
        """
        logger.debug(f"📄 Generating resume PDF...")
        logger.debug(f"   Resume text length: {len(resume_text)} chars")
        logger.debug(f"   Job ID: {job_id}, Company: {company}")
        
        try:
            # Validate input
            if not resume_text or len(resume_text) < 100:
                logger.error(f"❌ Invalid resume text: too short ({len(resume_text)} chars)")
                return None, False
            
            # Generate filename
            if output_filename is None:
                safe_company = "".join(c if c.isalnum() else "_" for c in company)[:20]
                output_filename = f"ShaheryarKhan_{safe_company}_{job_id}.pdf"
            
            pdf_path = os.path.join(self.output_dir, output_filename)
            
            logger.debug(f"🔄 Creating PDF file: {pdf_path}")
            
            # Create PDF using reportlab
            self._create_pdf_from_text(resume_text, pdf_path, page_limit=1.5)
            
            # Verify file
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF file was not created")
                return None, False
            
            file_size = os.path.getsize(pdf_path)
            logger.debug(f"📦 PDF created: {file_size} bytes")
            
            if file_size == 0:
                logger.error(f"❌ PDF file is empty")
                return None, False
            
            logger.info(f"✅ Resume PDF generated: {output_filename}")
            return pdf_path, True
        
        except Exception as e:
            logger.error(f"❌ Error generating resume PDF: {e}")
            logger.debug(f"   Exception details: {str(e)}")
            return None, False
    
    def generate_cover_letter_pdf(self, cover_letter_text: str, job_id: str, company: str,
                                 output_filename: str = None) -> tuple:
        """
        Generate cover letter PDF from text.
        
        Args:
            cover_letter_text: Plain text cover letter
            job_id: Job ID for naming
            company: Company name for naming
            output_filename: Optional filename override
        
        Returns:
            Tuple of (pdf_path, success)
        """
        logger.debug(f"💌 Generating cover letter PDF...")
        logger.debug(f"   Cover letter text length: {len(cover_letter_text)} chars")
        logger.debug(f"   Job ID: {job_id}, Company: {company}")
        
        try:
            # Validate input
            if not cover_letter_text or len(cover_letter_text) < 50:
                logger.error(f"❌ Invalid cover letter text: too short ({len(cover_letter_text)} chars)")
                return None, False
            
            # Generate filename
            if output_filename is None:
                safe_company = "".join(c if c.isalnum() else "_" for c in company)[:20]
                output_filename = f"CoverLetter_{safe_company}_{job_id}.pdf"
            
            pdf_path = os.path.join(self.output_dir, output_filename)
            
            logger.debug(f"🔄 Creating PDF file: {pdf_path}")
            
            # Create PDF
            self._create_pdf_from_text(cover_letter_text, pdf_path, page_limit=1)
            
            # Verify file
            if not os.path.exists(pdf_path):
                logger.error(f"❌ PDF file was not created")
                return None, False
            
            file_size = os.path.getsize(pdf_path)
            logger.debug(f"📦 PDF created: {file_size} bytes")
            
            if file_size == 0:
                logger.error(f"❌ PDF file is empty")
                return None, False
            
            logger.info(f"✅ Cover letter PDF generated: {output_filename}")
            return pdf_path, True
        
        except Exception as e:
            logger.error(f"❌ Error generating cover letter PDF: {e}")
            logger.debug(f"   Exception details: {str(e)}")
            return None, False
    
    def _create_pdf_from_text(self, text: str, output_path: str, page_limit: float = 1):
        """
        Create PDF from plain text with good formatting.
        
        Args:
            text: Plain text content
            output_path: Output PDF file path
            page_limit: Maximum pages (1, 1.5, or 2)
        """
        logger.debug(f"🖨️  Creating PDF with page limit: {page_limit}")
        
        # Create PDF document
        doc = SimpleDocTemplate(
            output_path,
            pagesize=letter,
            rightMargin=0.5 * inch,
            leftMargin=0.5 * inch,
            topMargin=0.5 * inch,
            bottomMargin=0.5 * inch
        )
        
        # Parse text into sections
        sections = self._parse_resume_text(text)
        story = []
        
        # Build story
        for section_type, section_title, section_content in sections:
            
            # Section title
            if section_type == "title":
                # Main title
                title_style = ParagraphStyle(
                    'CustomTitle',
                    parent=getSampleStyleSheet()['Heading1'],
                    fontSize=12,
                    textColor=colors.HexColor('#1a1a1a'),
                    spaceAfter=6,
                    alignment=1  # Center
                )
                story.append(Paragraph(section_title, title_style))
                story.append(Spacer(1, 0.1 * inch))
            
            elif section_type == "heading":
                # Section heading
                heading_style = ParagraphStyle(
                    'CustomHeading',
                    parent=getSampleStyleSheet()['Heading2'],
                    fontSize=10,
                    textColor=colors.HexColor('#000000'),
                    spaceAfter=4,
                    spaceBefore=6,
                    fontName='Helvetica-Bold'
                )
                story.append(Paragraph(section_title, heading_style))
            
            elif section_type == "content":
                # Content paragraph
                content_style = ParagraphStyle(
                    'CustomContent',
                    parent=getSampleStyleSheet()['Normal'],
                    fontSize=9,
                    textColor=colors.HexColor('#333333'),
                    spaceAfter=6,
                    leading=10
                )
                story.append(Paragraph(section_content, content_style))
        
        logger.debug(f"📝 Building PDF story with {len(story)} elements")
        
        # Build PDF
        try:
            doc.build(story, onFirstPage=self._get_page_template, onLaterPages=self._get_page_template)
            logger.debug(f"✅ PDF story built successfully")
        except Exception as e:
            logger.error(f"❌ Error building PDF: {e}")
            raise
    
    def _parse_resume_text(self, text: str) -> list:
        """Parse resume text into sections."""
        sections = []
        lines = text.split('\n')
        
        current_heading = None
        current_content = []
        
        for line in lines:
            stripped = line.strip()
            
            if not stripped:
                continue
            
            # Check if this looks like a heading
            if self._is_heading(stripped):
                # Save previous section
                if current_heading:
                    content = ' '.join(current_content).strip()
                    if content:
                        sections.append(("content", current_heading, content))
                
                # Start new heading
                current_heading = stripped
                current_content = []
            
            # Check if this looks like title (name line)
            elif len(sections) == 0 and any(x in stripped.lower() for x in ['shaheryar', 'khan']):
                sections.append(("title", stripped, ""))
            else:
                current_content.append(stripped)
        
        # Save last section
        if current_heading and current_content:
            content = ' '.join(current_content).strip()
            if content:
                sections.append(("heading", current_heading, ""))
                # Split content into bullets if needed
                for line in current_content:
                    if line.strip():
                        sections.append(("content", "", line))
        
        logger.debug(f"📊 Parsed {len(sections)} sections from resume")
        return sections
    
    def _is_heading(self, line: str) -> bool:
        """Determine if a line is a section heading."""
        headings = [
            'PROFESSIONAL', 'EXPERIENCE', 'EDUCATION', 'SKILLS', 
            'PROJECTS', 'CERTIFICATIONS', 'SUMMARY', 'CONTACT',
            'TECHNICAL', 'LANGUAGES', 'FRAMEWORKS', 'ARCHITECTURE',
            'ACHIEVEMENTS'
        ]
        line_upper = line.upper()
        return any(heading in line_upper for heading in headings) and len(line) < 60
    
    def _get_page_template(self, canvas_obj, doc):
        """Add page template with header/footer."""
        logger.debug(f"📄 Adding page template")
        # Could add header/footer here if needed
        pass
