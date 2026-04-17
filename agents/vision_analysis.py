"""Vision API integration for PDF and image analysis of Government Orders."""
import base64
import json
from pathlib import Path
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY
from pypdf import PdfReader
import io

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def extract_pdf_metadata_with_vision(pdf_path: str) -> dict:
    """
    Extract structured metadata from PDF using Claude Vision.
    Handles scanned documents, tables, formatted text, stamps, signatures.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Dict with extracted metadata: go_number, date, department, subject, etc.
    """
    pdf_path = Path(pdf_path)
    if not pdf_path.exists():
        return {"error": f"PDF not found: {pdf_path}"}
    
    # Read first page as image
    reader = PdfReader(str(pdf_path))
    first_page = reader.pages[0]
    
    # Convert PDF page to image for vision analysis
    from pdf2image import convert_from_path
    images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=150)
    if not images:
        return {"error": "Failed to convert PDF page to image"}
    
    # Convert image to base64
    img_buffer = io.BytesIO()
    images[0].save(img_buffer, format="PNG")
    img_base64 = base64.standard_b64encode(img_buffer.getvalue()).decode("utf-8")
    
    prompt = """Analyze this Government Order document and extract structured metadata.
    
Return ONLY valid JSON with:
{
  "go_number": "e.g., GO No. MS 123/2025",
  "go_date": "e.g., 2025-04-16",
  "effective_date": "e.g., 2025-05-01 or null if same as go_date",
  "department": "e.g., Finance, Revenue, etc.",
  "subject": "Full subject of the order",
  "document_type": "NOTIFICATION|RESOLUTION|GOVERNMENT_ORDER|CIRCULAR|AMENDMENT",
  "issuing_authority": "e.g., Secretary, Principal Secretary",
  "classification": "CONFIDENTIAL|RESTRICTED|GENERAL|PUBLIC",
  "has_amendments": true/false,
  "has_technical_tables": true/false,
  "has_schedules": true/false,
  "document_language": "ENGLISH|TELUGU|BILINGUAL",
  "key_paragraphs_count": approximate number,
  "extraction_confidence": 0.0-1.0 (how confident in extraction)
}

Focus on: official header, reference numbers, stamps, dates, signatures visible."""
    
    message = client.messages.create(
        model="claude-opus-4-1-20250805",  # Vision capable model
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )
    
    try:
        response_text = message.content[0].text
        # Try to parse JSON from response
        import json as json_mod
        # Find JSON in response
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            json_str = response_text[start_idx:end_idx]
            return json_mod.loads(json_str)
        return {"raw_extraction": response_text}
    except Exception as e:
        return {"error": f"Failed to parse response: {str(e)}", "raw": response_text[:500]}


def extract_tables_from_pdf(pdf_path: str) -> list:
    """
    Extract tables from PDF using Vision API.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        List of extracted tables with data and structure
    """
    from pdf2image import convert_from_path
    import json as json_mod
    
    pdf_path = Path(pdf_path)
    images = convert_from_path(str(pdf_path), dpi=200)
    
    tables = []
    for page_num, image in enumerate(images, 1):
        img_buffer = io.BytesIO()
        image.save(img_buffer, format="PNG")
        img_base64 = base64.standard_b64encode(img_buffer.getvalue()).decode("utf-8")
        
        prompt = """Extract ALL tables from this document page and return as JSON.
        
For each table found, return:
{
  "table_id": "T1, T2, etc",
  "title": "Table title if visible",
  "headers": ["col1", "col2", "col3"],
  "rows": [
    ["val1", "val2", "val3"],
    ["val1", "val2", "val3"]
  ],
  "notes": "Any footnotes or annotations",
  "format": "STRUCTURED|UNSTRUCTURED|MIXED"
}

Return as JSON array. If no tables, return empty array []."""
        
        message = client.messages.create(
            model="claude-opus-4-1-20250805",
            max_tokens=4000,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": img_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt
                        }
                    ],
                }
            ],
        )
        
        try:
            response_text = message.content[0].text
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']') + 1
            if start_idx >= 0 and end_idx > start_idx:
                page_tables = json_mod.loads(response_text[start_idx:end_idx])
                for table in page_tables:
                    table["page"] = page_num
                    tables.append(table)
        except Exception:
            pass
    
    return tables


def analyze_pdf_signatures_and_stamps(pdf_path: str) -> dict:
    """
    Detect and analyze official seals, signatures, and stamps in PDF.
    
    Args:
        pdf_path: Path to PDF file
    
    Returns:
        Dict with signature/stamp analysis
    """
    from pdf2image import convert_from_path
    
    pdf_path = Path(pdf_path)
    images = convert_from_path(str(pdf_path), first_page=1, last_page=1, dpi=250)
    
    if not images:
        return {"error": "Cannot convert PDF to image"}
    
    img_buffer = io.BytesIO()
    images[0].save(img_buffer, format="PNG")
    img_base64 = base64.standard_b64encode(img_buffer.getvalue()).decode("utf-8")
    
    prompt = """Analyze this document for official authentication elements.

Return JSON:
{
  "signatures_detected": number,
  "signature_positions": ["bottom-right", "left-side", etc],
  "seals_detected": number,
  "seal_types": ["official_seal", "department_stamp", "date_stamp"],
  "official_markings": ["classified", "approved", "reviewed"],
  "authenticity_indicators": ["official letterhead", "government emblem", "reference number"],
  "is_scanned": true/false,
  "is_digitally_signed": true/false,
  "analysis": "Brief assessment of document authenticity"
}"""
    
    message = client.messages.create(
        model="claude-opus-4-1-20250805",
        max_tokens=1000,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": img_base64,
                        },
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ],
            }
        ],
    )
    
    try:
        response_text = message.content[0].text
        start_idx = response_text.find('{')
        end_idx = response_text.rfind('}') + 1
        if start_idx >= 0 and end_idx > start_idx:
            return json.loads(response_text[start_idx:end_idx])
    except Exception:
        pass
    
    return {"raw_analysis": response_text[:300], "error": "parse_failed"}
