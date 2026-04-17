"""Telangana GO Scraper — fetches 2025 GOs from Internet Archive and ingests into ChromaDB.


Source:  https://archive.org  collection: in.gov.telangana.goir
Pattern: in.gov.telangana.goir.{YYYY-MM-DD}.{dept-slug}-{go-type}-{number}
PDF URL: https://archive.org/download/{identifier}/{dept-slug}-{go-type}-{number}.pdf
~2,349 GOs available for 2025.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re
import time
import hashlib
import requests
import chromadb
import pytesseract
import pdfplumber
from pathlib import Path
from pdf2image import convert_from_path
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from config import (
    CHROMA_PATH, EMBED_MODEL, TESSERACT_PATH, OCR_LANGUAGES, DATA_DIR,
)

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_chroma   = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)
_col      = _chroma.get_or_create_collection("government_orders_chunks")

ARCHIVE_SEARCH = "https://archive.org/advancedsearch.php"
ARCHIVE_DL     = "https://archive.org/download"
HEADERS        = {"User-Agent": "LegalDebateAI/1.0 (research; contact: reddy2073@gmail.com)"}
CHUNK_SIZE     = 800
CHUNK_OVERLAP  = 100
GO_DIR         = Path(DATA_DIR) / "government_orders" / "TS" / "2025"


# ---------------------------------------------------------------------------
# Archive.org helpers
# ---------------------------------------------------------------------------

def search_archive(year: int = 2025, department: str = None,
                   rows: int = 100, page: int = 1) -> dict:
    """Query Internet Archive for TS GOs."""
    query = f"identifier:in.gov.telangana.goir.{year}*"
    if department:
        query += f" AND subject:{department}"
    params = {
        "q": query,
        "fl[]": ["identifier", "title", "date", "subject"],
        "rows": rows,
        "page": page,
        "output": "json",
        "sort[]": "date desc",
    }
    resp = requests.get(ARCHIVE_SEARCH, params=params, headers=HEADERS, timeout=30)
    resp.raise_for_status()
    return resp.json()


def parse_identifier(identifier: str) -> dict:
    """Extract metadata from an Archive identifier string."""
    # e.g. in.gov.telangana.goir.2025-05-08.revenue-routine-174
    parts = identifier.split(".")
    if len(parts) < 6:
        return {}
    date_str   = parts[4]                    # 2025-05-08
    slug       = parts[5]                    # revenue-routine-174

    # slug format: {dept-words}-{go_type}-{number}
    go_types   = ("routine", "manuscript", "special")
    go_type    = next((t for t in go_types if f"-{t}-" in slug), "routine")
    split_on   = f"-{go_type}-"
    dept_slug, _, number = slug.partition(split_on)
    department = dept_slug.replace("-", " ").title()

    return {
        "identifier":  identifier,
        "date":        date_str,
        "department":  department,
        "go_type":     go_type,
        "go_number":   number,
        "state":       "TS",
        "pdf_filename": slug + ".pdf",
        "pdf_url":     f"{ARCHIVE_DL}/{identifier}/{slug}.pdf",
    }


# ---------------------------------------------------------------------------
# PDF processing
# ---------------------------------------------------------------------------

def extract_text(pdf_path: str) -> str:
    """Extract text from PDF — pdfplumber first, then OCR fallback."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        pass

    if len(text.strip()) < 100:
        try:
            images = convert_from_path(pdf_path, dpi=200)
            for img in images:
                text += pytesseract.image_to_string(img, lang=OCR_LANGUAGES) + "\n"
        except Exception as e:
            print(f"        OCR failed: {e}")

    return text.strip()


def chunk_and_embed(text: str, meta: dict) -> int:
    """Chunk text, embed and upsert into ChromaDB. Returns chunks added."""
    words  = text.split()
    chunks, ids, embeddings, metas = [], [], [], []

    for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        if len(chunk.strip()) < 50:
            continue
        chunk_meta = {**meta, "chunk_index": len(chunks)}
        chunk_id   = hashlib.md5(
            f"{meta.get('identifier', '')}_{len(chunks)}".encode()
        ).hexdigest()
        chunks.append(chunk)
        ids.append(chunk_id)
        metas.append(chunk_meta)
        embeddings.append(_embedder.encode(chunk).tolist())

    if chunks:
        _col.upsert(ids=ids, documents=chunks, metadatas=metas, embeddings=embeddings)

    return len(chunks)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=15))
def download_pdf(url: str, dest: Path) -> bool:
    """Download PDF to dest path. Returns True on success."""
    resp = requests.get(url, headers=HEADERS, timeout=60, stream=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


# ---------------------------------------------------------------------------
# Main ingestion pipeline
# ---------------------------------------------------------------------------

def ingest_item(item: dict, skip_existing: bool = True) -> int:
    """Process a single Archive item — download, extract, embed. Returns chunks added."""
    identifier = item.get("identifier", "")
    meta       = parse_identifier(identifier)
    if not meta:
        return 0

    # Add title/subject from Archive metadata
    meta["title"]   = item.get("title", "")
    meta["subject"] = item.get("subject", "")

    GO_DIR.mkdir(parents=True, exist_ok=True)
    pdf_path = GO_DIR / meta["pdf_filename"]

    # Skip if already ingested
    if skip_existing and pdf_path.exists() and pdf_path.stat().st_size > 1000:
        existing = _col.get(where={"identifier": identifier}, limit=1)
        if existing["ids"]:
            return 0  # already in ChromaDB

    # Download
    if not pdf_path.exists() or pdf_path.stat().st_size < 1000:
        try:
            download_pdf(meta["pdf_url"], pdf_path)
            time.sleep(0.3)  # be polite to Archive.org
        except Exception as e:
            print(f"        Download failed [{identifier}]: {e}")
            return 0

    # Extract + embed
    text = extract_text(str(pdf_path))
    if not text:
        return 0

    return chunk_and_embed(text, meta)


def run_phase1(year: int = 2025, department_filter: str = None,
               max_gos: int = 500, rows_per_page: int = 100,
               skip_existing: bool = True):
    """
    Phase 1 scraper — ingest TS GOs from 2025 via Internet Archive.

    Args:
        year:              Year to scrape (default 2025)
        department_filter: Optional dept keyword to filter (e.g. 'finance')
        max_gos:           Max GOs to process (default 500)
        rows_per_page:     Items per API page (max 100)
        skip_existing:     Skip GOs already in ChromaDB
    """
    print(f"\nPhase 1: Scraping TS GOs — year={year}"
          + (f", dept={department_filter}" if department_filter else ""))

    # Get total count first
    first = search_archive(year, department_filter, rows=1, page=1)
    total_available = first.get("response", {}).get("numFound", 0)
    total_to_process = min(total_available, max_gos)
    print(f"Available: {total_available} | Processing: {total_to_process}")

    processed = 0
    total_chunks = 0
    page = 1

    with tqdm(total=total_to_process, unit="GO") as pbar:
        while processed < total_to_process:
            batch_size = min(rows_per_page, total_to_process - processed)
            try:
                result = search_archive(year, department_filter, rows=batch_size, page=page)
                items  = result.get("response", {}).get("docs", [])
            except Exception as e:
                print(f"\n  API error (page {page}): {e}")
                break

            if not items:
                break

            for item in items:
                chunks = ingest_item(item, skip_existing)
                total_chunks += chunks
                processed += 1
                pbar.update(1)
                pbar.set_postfix(chunks=total_chunks, go=item.get("identifier", "")[-30:])

            page += 1

    print(f"\nDone. GOs processed: {processed} | Chunks ingested: {total_chunks}")
    print(f"ChromaDB total GO chunks: {_col.count()}")
    return total_chunks


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Phase 1 — Ingest 2025 TS GOs from Internet Archive")
    parser.add_argument("--year",    type=int,   default=2025,  help="Year to scrape")
    parser.add_argument("--dept",    type=str,   default=None,  help="Department keyword filter")
    parser.add_argument("--max",     type=int,   default=500,   help="Max GOs to process")
    parser.add_argument("--fresh",   action="store_true",       help="Re-ingest even if already done")
    args = parser.parse_args()

    run_phase1(
        year=args.year,
        department_filter=args.dept,
        max_gos=args.max,
        skip_existing=not args.fresh,
    )
