"""Central Acts scraper — downloads Central Acts from IndiaCode (indiacode.nic.in) into ChromaDB.

Source: https://www.indiacode.nic.in (DSpace repository of all enforced Central Acts)
Collection handle: 123456789/1362
PDF pattern: /bitstream/123456789/{item_id}/{seq}/{filename}.pdf
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib, time, requests, chromadb, pdfplumber, pytesseract
from pathlib import Path
from bs4 import BeautifulSoup
from pdf2image import convert_from_path
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from config import CHROMA_PATH, EMBED_MODEL, TESSERACT_PATH, OCR_LANGUAGES, DATA_DIR

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_chroma   = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)
_col      = _chroma.get_or_create_collection("central_acts_chunks")

ACTS_DIR      = Path(DATA_DIR) / "central_acts"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

BASE_URL      = "https://www.indiacode.nic.in"
BROWSE_URL    = f"{BASE_URL}/handle/123456789/1362/browse"
HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":  "document",
    "Sec-Fetch-Mode":  "navigate",
    "Sec-Fetch-Site":  "none",
}

_session = requests.Session()
_session.headers.update(HEADERS)


# ---------------------------------------------------------------------------
# Scraping helpers
# ---------------------------------------------------------------------------

def get_act_handles(page: int = 0, rows: int = 100) -> list[dict]:
    """Scrape one browse page — returns list of {title, handle}."""
    params = {"type": "shorttitle", "sort_by": 3, "order": "ASC",
              "rpp": rows, "etal": -1, "offset": page * rows}
    try:
        resp = _session.get(BROWSE_URL, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  Browse page {page} failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    # Table rows: columns are [Enactment Date, Act Number, Short Title, View]
    table = soup.find("table", summary=lambda s: s and "dspace" in s.lower())
    if not table:
        table = soup.find("table", class_=lambda c: c and "table" in c)
    if not table:
        return results
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        title_cell = cells[2]
        view_cell  = cells[3]
        title = title_cell.get_text(strip=True)
        view_a = view_cell.find("a", href=lambda h: h and "/handle/" in h)
        if view_a and title:
            href = view_a.get("href", "")
            results.append({"title": title, "handle": href.split("?")[0]})
    return results


def get_pdf_url(handle_path: str) -> tuple[str, str] | tuple[None, None]:
    """Visit an act's handle page and return (pdf_url, filename)."""
    url = f"{BASE_URL}{handle_path}"
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    # DSpace bitstream links
    for a in soup.select("a[href*='/bitstream/']"):
        href = a.get("href", "")
        if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
            filename = href.split("/")[-1].split("?")[0]
            full_url = f"{BASE_URL}{href}" if href.startswith("/") else href
            return full_url, filename

    return None, None


# ---------------------------------------------------------------------------
# PDF helpers (shared with other scrapers)
# ---------------------------------------------------------------------------

def extract_text(pdf_path: Path) -> str:
    text = ""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    if len(text.strip()) < 100:
        try:
            images = convert_from_path(str(pdf_path), dpi=200)
            for img in images:
                text += pytesseract.image_to_string(img, lang=OCR_LANGUAGES) + "\n"
        except Exception as e:
            print(f"    OCR failed: {e}")
    return text.strip()


def chunk_and_embed(text: str, meta: dict) -> int:
    words = text.split()
    ids, docs, metas, embs = [], [], [], []
    idx = 0
    chunk_num = 0
    while idx < len(words):
        chunk = " ".join(words[idx : idx + CHUNK_SIZE])
        if len(chunk.strip()) >= 50:
            cid = hashlib.md5(
                f"{meta.get('filename', '')}_{chunk_num}".encode()
            ).hexdigest()
            existing = _col.get(ids=[cid])
            if not existing["ids"]:
                ids.append(cid)
                docs.append(chunk)
                metas.append({**meta, "chunk_index": chunk_num})
                embs.append(_embedder.encode(chunk).tolist())
            chunk_num += 1
        idx += CHUNK_SIZE - CHUNK_OVERLAP

    if ids:
        _col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    return len(ids)


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def download_pdf(url: str, dest: Path) -> bool:
    resp = _session.get(url, timeout=60, stream=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


def ingest_act(title: str, pdf_url: str, filename: str) -> int:
    ACTS_DIR.mkdir(parents=True, exist_ok=True)
    dest = ACTS_DIR / filename

    if not dest.exists() or dest.stat().st_size < 1000:
        try:
            download_pdf(pdf_url, dest)
            time.sleep(0.5)
        except Exception as e:
            print(f"    Download failed [{filename}]: {e}")
            return 0

    text = extract_text(dest)
    if not text:
        return 0

    meta = {
        "source":        "IndiaCode",
        "document_type": "central_act",
        "state":         "IN",
        "title":         title[:200],
        "filename":      filename,
        "pdf_url":       pdf_url,
    }
    return chunk_and_embed(text, meta)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_central_acts(max_acts: int = 500, rows_per_page: int = 100,
                     skip_existing: bool = True):
    print(f"\nCentral Acts Scraper: Starting (max={max_acts})...")

    if skip_existing:
        count = _col.count()
        if count > 0:
            print(f"  Already have {count:,} chunks. Checking for new acts...")

    ACTS_DIR.mkdir(parents=True, exist_ok=True)

    all_handles: list[dict] = []
    page = 0
    print("  Fetching act list from IndiaCode...")

    while len(all_handles) < max_acts:
        batch = get_act_handles(page=page, rows=rows_per_page)
        if not batch:
            break
        all_handles.extend(batch)
        print(f"    Page {page + 1}: {len(batch)} acts (total: {len(all_handles)})")
        page += 1
        time.sleep(1)
        if len(batch) < rows_per_page:
            break  # Last page

    if not all_handles:
        print("\n  WARNING: Could not fetch acts list from IndiaCode (possible block).")
        print("  Try running with Playwright or check network connectivity.")
        return 0

    acts_to_process = all_handles[:max_acts]
    print(f"\n  Processing {len(acts_to_process)} acts...")

    total_chunks = 0
    with tqdm(total=len(acts_to_process), unit="act") as pbar:
        for item in acts_to_process:
            title  = item["title"]
            handle = item["handle"]

            pdf_url, filename = get_pdf_url(handle)
            if not pdf_url:
                pbar.update(1)
                continue

            # Skip if PDF already downloaded and in DB
            dest = ACTS_DIR / filename
            if skip_existing and dest.exists() and dest.stat().st_size > 1000:
                existing = _col.get(where={"filename": filename}, limit=1)
                if existing["ids"]:
                    pbar.update(1)
                    continue

            chunks = ingest_act(title, pdf_url, filename)
            total_chunks += chunks
            pbar.update(1)
            pbar.set_postfix(chunks=total_chunks, act=title[:30])
            time.sleep(0.5)

    print(f"\nDone. Acts processed. New chunks: {total_chunks}")
    print(f"ChromaDB central_acts total: {_col.count():,}")
    return total_chunks


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Central Acts from IndiaCode")
    parser.add_argument("--max",   type=int,  default=500,  help="Max acts to process")
    parser.add_argument("--fresh", action="store_true",     help="Re-ingest all")
    args = parser.parse_args()

    if args.fresh:
        try:
            _chroma.delete_collection("central_acts_chunks")
        except Exception:
            pass
        _col = _chroma.get_or_create_collection("central_acts_chunks")

    run_central_acts(max_acts=args.max, skip_existing=not args.fresh)
