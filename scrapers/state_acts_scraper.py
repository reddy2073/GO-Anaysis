"""Telangana State Acts scraper — downloads TS state acts from IndiaCode and law.telangana.gov.in.

Sources:
  1. IndiaCode state acts collection (search for Telangana): indiacode.nic.in
  2. Telangana Law Department: law.telangana.gov.in/actsNew
  3. PRS India (recent TS acts): prsindia.org
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
_col      = _chroma.get_or_create_collection("state_acts_chunks")

STATE_DIR     = Path(DATA_DIR) / "state_acts"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

HEADERS = {
    "User-Agent":      "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":          "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate, br",
    "Connection":      "keep-alive",
}

_session = requests.Session()
_session.headers.update(HEADERS)

INDIACODE_BASE       = "https://www.indiacode.nic.in"
INDIACODE_TS_BROWSE  = f"{INDIACODE_BASE}/handle/123456789/2508/browse"
TELANGANA_LAW_URL    = "https://law.telangana.gov.in/actsNew"

# PRS India hosts recent Telangana acts as PDFs
PRS_TS_ACTS = [
    {
        "title":    "The Telangana Bhu Bharati (Record of Rights in Land) Act, 2024",
        "url":      "https://prsindia.org/files/bills_acts/acts_states/telangana/2025/Act1of2025TS.pdf",
        "filename": "ts_bhu_bharati_act_2024.pdf",
        "year":     "2024",
    },
]


# ---------------------------------------------------------------------------
# IndiaCode helpers
# ---------------------------------------------------------------------------

def browse_indiacode_ts(page: int = 0, rows: int = 100) -> list[dict]:
    """Browse IndiaCode Telangana state acts collection (handle 2508)."""
    params = {"type": "shorttitle", "sort_by": 3, "order": "ASC",
              "rpp": rows, "etal": -1, "offset": page * rows}
    try:
        resp = _session.get(INDIACODE_TS_BROWSE, params=params, timeout=30)
        resp.raise_for_status()
    except Exception as e:
        print(f"  IndiaCode TS browse page {page} failed: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    table = soup.find("table", summary=lambda s: s and "dspace" in s.lower())
    if not table:
        return results
    for row in table.find_all("tr"):
        cells = row.find_all("td")
        if len(cells) < 4:
            continue
        title     = cells[2].get_text(strip=True)
        view_cell = cells[3]
        view_a    = view_cell.find("a", href=lambda h: h and "/handle/" in h)
        if view_a and title:
            href = view_a.get("href", "").split("?")[0]
            results.append({"title": title, "handle": href})
    return results


def get_pdf_url_indiacode(handle_path: str) -> tuple[str, str] | tuple[None, None]:
    url = f"{INDIACODE_BASE}{handle_path}"
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception:
        return None, None

    soup = BeautifulSoup(resp.text, "html.parser")
    for a in soup.select("a[href*='/bitstream/']"):
        href = a.get("href", "")
        if href.lower().endswith(".pdf") or ".pdf?" in href.lower():
            filename = href.split("/")[-1].split("?")[0]
            full_url = f"{INDIACODE_BASE}{href}" if href.startswith("/") else href
            return full_url, filename
    return None, None


# ---------------------------------------------------------------------------
# Telangana Law Department helpers
# ---------------------------------------------------------------------------

def get_ts_law_dept_acts() -> list[dict]:
    """Scrape law.telangana.gov.in for act PDF links."""
    try:
        _session.headers.update({"Referer": "https://law.telangana.gov.in/"})
        resp = _session.get(TELANGANA_LAW_URL, timeout=30, verify=False)
    except Exception as e:
        print(f"  Telangana Law Dept unavailable: {e}")
        return []

    soup = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if ".pdf" in href.lower():
            title    = a.get_text(strip=True) or href.split("/")[-1]
            full_url = href if href.startswith("http") else f"https://law.telangana.gov.in/{href.lstrip('/')}"
            filename = f"ts_{href.split('/')[-1].split('?')[0]}"
            results.append({"title": title, "url": full_url, "filename": filename})
    return results


# ---------------------------------------------------------------------------
# PDF helpers
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
    words  = text.split()
    ids, docs, metas, embs = [], [], [], []
    idx    = 0
    n      = 0
    while idx < len(words):
        chunk = " ".join(words[idx : idx + CHUNK_SIZE])
        if len(chunk.strip()) >= 50:
            cid = hashlib.md5(f"{meta.get('filename', '')}_{n}".encode()).hexdigest()
            if not _col.get(ids=[cid])["ids"]:
                ids.append(cid)
                docs.append(chunk)
                metas.append({**meta, "chunk_index": n})
                embs.append(_embedder.encode(chunk).tolist())
            n += 1
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


def ingest_act(title: str, pdf_url: str, filename: str,
               source: str = "IndiaCode", year: str = "") -> int:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    dest = STATE_DIR / filename

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
        "source":        source,
        "document_type": "state_act",
        "state":         "TS",
        "title":         title[:200],
        "filename":      filename,
        "year":          year,
        "pdf_url":       pdf_url,
    }
    return chunk_and_embed(text, meta)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_state_acts(max_acts: int = 300, skip_existing: bool = True):
    print(f"\nState Acts Scraper (Telangana): Starting (max={max_acts})...")
    STATE_DIR.mkdir(parents=True, exist_ok=True)

    total_chunks = 0
    processed    = 0

    # --- Source 1: PRS India (recent TS acts — known-good PDF URLs) ---
    print("\n  [1/3] PRS India recent Telangana acts...")
    for act in PRS_TS_ACTS:
        dest = STATE_DIR / act["filename"]
        if skip_existing and dest.exists() and dest.stat().st_size > 1000:
            existing = _col.get(where={"filename": act["filename"]}, limit=1)
            if existing["ids"]:
                continue
        chunks = ingest_act(act["title"], act["url"], act["filename"],
                            source="PRS India", year=act.get("year", ""))
        total_chunks += chunks
        processed    += 1
        print(f"    {act['title'][:60]}: {chunks} chunks")

    # --- Source 2: Telangana Law Department ---
    print("\n  [2/3] Telangana Law Department (law.telangana.gov.in)...")
    ts_law_acts = get_ts_law_dept_acts()
    if ts_law_acts:
        print(f"    Found {len(ts_law_acts)} acts on law.telangana.gov.in")
        with tqdm(total=min(len(ts_law_acts), max_acts - processed), unit="act") as pbar:
            for act in ts_law_acts:
                if processed >= max_acts:
                    break
                dest = STATE_DIR / act["filename"]
                if skip_existing and dest.exists() and dest.stat().st_size > 1000:
                    existing = _col.get(where={"filename": act["filename"]}, limit=1)
                    if existing["ids"]:
                        pbar.update(1)
                        continue
                chunks = ingest_act(
                    act["title"], act["url"], act["filename"],
                    source="Telangana Law Dept",
                )
                total_chunks += chunks
                processed    += 1
                pbar.update(1)
                pbar.set_postfix(chunks=total_chunks)
                time.sleep(0.5)
    else:
        print("    Telangana Law Dept unavailable or no PDFs found.")

    # --- Source 3: IndiaCode Telangana state acts collection ---
    print("\n  [3/3] IndiaCode — browsing Telangana state acts collection...")
    handles: list[dict] = []
    page = 0
    while len(handles) < max_acts:
        batch = browse_indiacode_ts(page=page, rows=100)
        if not batch:
            break
        handles.extend(batch)
        print(f"    Page {page + 1}: {len(batch)} acts (total: {len(handles)})")
        page += 1
        time.sleep(1)
        if len(batch) < 100:
            break

    if handles:
        with tqdm(total=min(len(handles), max_acts - processed), unit="act") as pbar:
            for item in handles:
                if processed >= max_acts:
                    break
                pdf_url, filename = get_pdf_url_indiacode(item["handle"])
                if not pdf_url:
                    pbar.update(1)
                    continue
                dest = STATE_DIR / filename
                if skip_existing and dest.exists() and dest.stat().st_size > 1000:
                    existing = _col.get(where={"filename": filename}, limit=1)
                    if existing["ids"]:
                        pbar.update(1)
                        continue
                chunks = ingest_act(item["title"], pdf_url, filename,
                                    source="IndiaCode")
                total_chunks += chunks
                processed    += 1
                pbar.update(1)
                pbar.set_postfix(chunks=total_chunks, act=item["title"][:25])
                time.sleep(0.5)
    else:
        print("    IndiaCode Telangana collection returned no results (possible block).")

    print(f"\nDone. State Acts processed: {processed} | New chunks: {total_chunks}")
    print(f"ChromaDB state_acts total: {_col.count():,}")
    return total_chunks


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Telangana State Acts")
    parser.add_argument("--max",   type=int,  default=300,  help="Max acts to process")
    parser.add_argument("--fresh", action="store_true",     help="Re-ingest all")
    args = parser.parse_args()

    if args.fresh:
        try:
            _chroma.delete_collection("state_acts_chunks")
        except Exception:
            pass
        _col = _chroma.get_or_create_collection("state_acts_chunks")

    run_state_acts(max_acts=args.max, skip_existing=not args.fresh)
