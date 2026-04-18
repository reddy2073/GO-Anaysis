"""Court Verdicts scraper — fetches Telangana HC + Supreme Court judgments into ChromaDB.

Sources:
  1. Indian Kanoon API (https://api.indiankanoon.org) — requires INDIANKANOON_API_TOKEN in .env
  2. Indian Kanoon public search fallback (no token needed, rate-limited)

Set INDIANKANOON_API_TOKEN in your .env for higher quota and better coverage.
Register free at: https://api.indiankanoon.org/
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib, time, requests, chromadb, pytesseract
from pathlib import Path
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tenacity import retry, stop_after_attempt, wait_exponential
from tqdm import tqdm
from config import CHROMA_PATH, EMBED_MODEL, TESSERACT_PATH, DATA_DIR

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_chroma   = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)
_col      = _chroma.get_or_create_collection("court_verdicts_chunks")

VERDICTS_DIR  = Path(DATA_DIR) / "verdicts"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

IK_API_BASE   = "https://api.indiankanoon.org"
IK_PUBLIC_BASE = "https://indiankanoon.org"

# Searches to run — covering Telangana HC + SC judgments on Telangana matters
SEARCH_QUERIES = [
    "doctypes:telanganaHighCourt",
    "doctypes:andhratelangana",
    "Telangana doctypes:supremecourt",
    "court:Telangana High Court",
]

_API_TOKEN = os.getenv("INDIANKANOON_API_TOKEN", "")

BROWSER_HEADERS = {
    "User-Agent":                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Accept":                    "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language":           "en-US,en;q=0.9",
    "Accept-Encoding":           "gzip, deflate, br",
    "Referer":                   "https://indiankanoon.org/",
    "Connection":                "keep-alive",
    "Upgrade-Insecure-Requests": "1",
    "Sec-Fetch-Dest":            "document",
    "Sec-Fetch-Mode":            "navigate",
    "Sec-Fetch-Site":            "same-origin",
}
API_HEADERS = {
    "Authorization": f"Token {_API_TOKEN}",
    "Accept":        "application/json",
}

_session = requests.Session()
_session.headers.update(BROWSER_HEADERS)


# ---------------------------------------------------------------------------
# Indian Kanoon API (token-based)
# ---------------------------------------------------------------------------

@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def api_search(query: str, pagenum: int = 1) -> dict:
    resp = requests.post(
        f"{IK_API_BASE}/search/",
        headers=API_HEADERS,
        data={"formInput": query, "pagenum": pagenum},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


@retry(stop=stop_after_attempt(3), wait=wait_exponential(min=2, max=10))
def api_get_doc(docid: str) -> dict:
    resp = requests.post(
        f"{IK_API_BASE}/doc/{docid}/",
        headers=API_HEADERS,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def fetch_verdicts_api(query: str, max_docs: int = 500) -> list[dict]:
    """Use IK API to fetch verdicts. Returns list of {docid, title, court, date, text}."""
    results = []
    page    = 1
    while len(results) < max_docs:
        try:
            data = api_search(query, pagenum=page)
        except Exception as e:
            print(f"    API search error (page {page}): {e}")
            break

        docs = data.get("docs", [])
        if not docs:
            break

        for doc in docs:
            docid = str(doc.get("tid", ""))
            if not docid:
                continue
            try:
                full = api_get_doc(docid)
                text = BeautifulSoup(full.get("doc", ""), "html.parser").get_text(
                    separator="\n", strip=True
                )
                results.append({
                    "docid": docid,
                    "title": doc.get("title", ""),
                    "court": doc.get("docsource", ""),
                    "date":  doc.get("publishdate", ""),
                    "text":  text,
                })
                time.sleep(0.3)
            except Exception:
                continue

        if len(docs) < 10:
            break
        page += 1

    return results


# ---------------------------------------------------------------------------
# Indian Kanoon public scraping fallback
# ---------------------------------------------------------------------------

def public_search_doc_ids(query: str, pagenum: int = 1) -> list[dict]:
    """Scrape IK public search for doc IDs — fallback when no API token."""
    url    = f"{IK_PUBLIC_BASE}/search/"
    params = {"formInput": query, "pagenum": pagenum}
    try:
        resp = _session.get(url, params=params, timeout=20)
        resp.raise_for_status()
    except Exception as e:
        print(f"    Public search failed (page {pagenum}): {e}")
        return []

    soup    = BeautifulSoup(resp.text, "html.parser")
    results = []
    for a in soup.select("div.result_title a[href*='/doc/']"):
        href  = a.get("href", "")
        parts = [p for p in href.split("/") if p]
        if parts and parts[0] == "doc" and len(parts) >= 2:
            results.append({
                "docid": parts[1],
                "title": a.get_text(strip=True),
            })
    return results


def public_fetch_doc_text(docid: str) -> tuple[str, str, str]:
    """Fetch full judgment text from IK public doc page. Returns (text, court, date)."""
    url = f"{IK_PUBLIC_BASE}/doc/{docid}/"
    try:
        resp = _session.get(url, timeout=20)
        resp.raise_for_status()
    except Exception:
        return "", "", ""

    soup  = BeautifulSoup(resp.text, "html.parser")
    court = ""
    date  = ""

    # Extract court and date from meta or heading
    for tag in soup.select("div.docsource_main, span.docsource"):
        court = tag.get_text(strip=True)
        break
    for tag in soup.select("div.doc_title span.doc_subtitle, span.date"):
        date = tag.get_text(strip=True)
        break

    # Main judgment text
    main = soup.find("div", {"id": "judgments"}) or soup.find("div", class_="judgments")
    if main:
        text = main.get_text(separator="\n", strip=True)
    else:
        text = soup.get_text(separator="\n", strip=True)[:10000]

    return text, court, date


def fetch_verdicts_public(query: str, max_docs: int = 200) -> list[dict]:
    """Scrape IK public search for verdicts (no API token)."""
    results = []
    page    = 1
    seen    = set()

    while len(results) < max_docs:
        ids = public_search_doc_ids(query, pagenum=page)
        if not ids:
            break
        for item in ids:
            docid = item["docid"]
            if docid in seen:
                continue
            seen.add(docid)
            text, court, date = public_fetch_doc_text(docid)
            if text and len(text.split()) > 50:
                results.append({
                    "docid": docid,
                    "title": item["title"],
                    "court": court,
                    "date":  date,
                    "text":  text,
                })
            time.sleep(1.0)  # polite rate limit for public scraping
        page += 1
        if len(ids) < 5:
            break

    return results


# ---------------------------------------------------------------------------
# Embed and store
# ---------------------------------------------------------------------------

def chunk_and_embed(verdict: dict) -> int:
    text  = verdict["text"]
    words = text.split()
    ids, docs, metas, embs = [], [], [], []
    idx   = 0
    n     = 0
    while idx < len(words):
        chunk = " ".join(words[idx : idx + CHUNK_SIZE])
        if len(chunk.strip()) >= 50:
            cid = hashlib.md5(f"verdict_{verdict['docid']}_{n}".encode()).hexdigest()
            if not _col.get(ids=[cid])["ids"]:
                ids.append(cid)
                docs.append(chunk)
                metas.append({
                    "source":        "IndianKanoon",
                    "document_type": "court_verdict",
                    "docid":         verdict["docid"],
                    "title":         verdict["title"][:200],
                    "court":         verdict["court"][:100],
                    "date":          verdict["date"][:50],
                    "state":         "TS",
                    "chunk_index":   n,
                })
                embs.append(_embedder.encode(chunk).tolist())
            n += 1
        idx += CHUNK_SIZE - CHUNK_OVERLAP

    if ids:
        _col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    return len(ids)


def save_verdict_text(verdict: dict):
    """Save raw text to disk for reproducibility."""
    VERDICTS_DIR.mkdir(parents=True, exist_ok=True)
    fname = VERDICTS_DIR / f"ik_{verdict['docid']}.txt"
    if not fname.exists():
        fname.write_text(verdict["text"], encoding="utf-8")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_verdicts(max_per_query: int = 200, skip_existing: bool = True):
    print(f"\nVerdicts Scraper: Starting...")
    VERDICTS_DIR.mkdir(parents=True, exist_ok=True)

    use_api = bool(_API_TOKEN)
    if use_api:
        print("  Mode: Indian Kanoon API (token found)")
    else:
        print("  ERROR: INDIANKANOON_API_TOKEN not set in .env")
        print("  IndianKanoon now blocks all public scraping (403 Forbidden).")
        print("  Register free at: https://api.indiankanoon.org/")
        print("  Then add to .env:  INDIANKANOON_API_TOKEN=your_token_here")
        return 0

    if skip_existing:
        count = _col.count()
        if count > 0:
            print(f"  Already have {count:,} verdict chunks.")

    total_chunks = 0
    total_docs   = 0

    for query in SEARCH_QUERIES:
        print(f"\n  Query: {query}")
        if use_api:
            verdicts = fetch_verdicts_api(query, max_docs=max_per_query)
        else:
            verdicts = fetch_verdicts_public(query, max_docs=max_per_query)

        print(f"    Fetched {len(verdicts)} verdicts")
        for v in tqdm(verdicts, unit="verdict", desc=f"    Embedding"):
            # Skip if already in DB
            existing = _col.get(
                where={"docid": v["docid"]}, limit=1
            )
            if skip_existing and existing["ids"]:
                continue
            save_verdict_text(v)
            chunks = chunk_and_embed(v)
            total_chunks += chunks
            total_docs   += 1
        time.sleep(2)

    print(f"\nDone. Verdicts ingested: {total_docs} | New chunks: {total_chunks}")
    print(f"ChromaDB court_verdicts total: {_col.count():,}")
    return total_chunks


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Court Verdicts (Telangana HC + SC)")
    parser.add_argument("--max",   type=int,  default=200,  help="Max verdicts per query")
    parser.add_argument("--fresh", action="store_true",     help="Re-ingest all")
    args = parser.parse_args()

    if args.fresh:
        try:
            _chroma.delete_collection("court_verdicts_chunks")
        except Exception:
            pass
        _col = _chroma.get_or_create_collection("court_verdicts_chunks")

    run_verdicts(max_per_query=args.max, skip_existing=not args.fresh)
