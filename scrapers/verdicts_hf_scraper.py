"""Court Verdicts scraper — HuggingFace parquet datasets (no auth required).

Sources:
  1. labofsahil/Indian-Supreme-Court-Judgments  (CC-BY-4.0)
     76 parquet files, rich metadata, raw HTML judgment text
  2. Immanuel30303/Indian-High-Court-Judgments-all  (CC-BY-4.0)
     100 parquet files, text in 'output' column

Filters for Telangana-relevant cases using keyword matching.
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import hashlib, io, time, requests, chromadb
import pyarrow.parquet as pq
from bs4 import BeautifulSoup
from sentence_transformers import SentenceTransformer
from tqdm import tqdm
from config import CHROMA_PATH, EMBED_MODEL

_chroma   = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)
_col      = _chroma.get_or_create_collection("court_verdicts_chunks")

CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

HF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

SC_PARQUET_API  = "https://huggingface.co/api/datasets/labofsahil/Indian-Supreme-Court-Judgments/parquet"
HC_PARQUET_API  = "https://huggingface.co/api/datasets/Immanuel30303/Indian-High-Court-Judgments-all/parquet"

# Keywords to keep a case (any match = include)
RELEVANCE_KEYWORDS = [
    "telangana", "hyderabad", "andhra", "land acquisition", "revenue",
    "government order", "g.o.", "municipal", "panchayat", "urban land",
    "property tax", "building permission", "demolition", "encroachment",
    "public employment", "reservation", "forest", "irrigation", "water",
]


def is_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in RELEVANCE_KEYWORDS)


def html_to_text(raw_html: str) -> str:
    if not raw_html or len(raw_html.strip()) < 20:
        return ""
    soup = BeautifulSoup(raw_html, "html.parser")
    return soup.get_text(separator="\n", strip=True)


def chunk_and_embed(text: str, meta: dict) -> int:
    words = text.split()
    ids, docs, metas, embs = [], [], [], []
    idx, n = 0, 0
    while idx < len(words):
        chunk = " ".join(words[idx: idx + CHUNK_SIZE])
        if len(chunk.strip()) >= 50:
            cid = hashlib.md5(f"{meta['case_id']}_{n}".encode()).hexdigest()
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


def fetch_parquet(url: str):
    try:
        r = requests.get(url, headers=HF_HEADERS, timeout=60)
        r.raise_for_status()
        return pq.read_table(io.BytesIO(r.content))
    except Exception as e:
        print(f"    Download failed: {e}")
        return None


# ---------------------------------------------------------------------------
# SC dataset
# ---------------------------------------------------------------------------

def run_sc_judgments(max_files: int = 76) -> int:
    print("\n  [SC] Indian-Supreme-Court-Judgments (HuggingFace)")
    r = requests.get(SC_PARQUET_API, headers=HF_HEADERS, timeout=15)
    r.raise_for_status()
    urls = r.json().get("default", {}).get("train", [])
    urls = urls[:max_files]
    print(f"  Files to scan: {len(urls)}")

    total_chunks = 0
    total_cases  = 0

    for i, url in enumerate(tqdm(urls, desc="  SC parquet files")):
        table = fetch_parquet(url)
        if table is None:
            continue
        df = table.to_pydict()
        n_rows = table.num_rows

        for j in range(n_rows):
            title      = str(df.get("title", [""])[j] or "")
            petitioner = str(df.get("petitioner", [""])[j] or "")
            respondent = str(df.get("respondent", [""])[j] or "")
            combined   = f"{title} {petitioner} {respondent}"

            if not is_relevant(combined):
                continue

            raw_html = str(df.get("raw_html", [""])[j] or "")
            text     = html_to_text(raw_html)
            if not text or len(text.split()) < 30:
                continue

            case_id = str(df.get("case_id", [""])[j] or f"sc_{i}_{j}")
            meta = {
                "source":        "HuggingFace/labofsahil",
                "document_type": "supreme_court_verdict",
                "state":         "IN",
                "case_id":       case_id[:100],
                "title":         title[:200],
                "petitioner":    petitioner[:150],
                "respondent":    respondent[:150],
                "judge":         str(df.get("judge", [""])[j] or "")[:150],
                "citation":      str(df.get("citation", [""])[j] or "")[:100],
                "decision_date": str(df.get("decision_date", [""])[j] or "")[:30],
                "court":         "Supreme Court of India",
                "year":          str(df.get("year", [""])[j] or ""),
            }
            chunks = chunk_and_embed(text, meta)
            total_chunks += chunks
            if chunks:
                total_cases += 1

        time.sleep(0.2)

    print(f"  SC done: {total_cases} relevant cases, {total_chunks} chunks")
    return total_chunks


# ---------------------------------------------------------------------------
# HC dataset
# ---------------------------------------------------------------------------

def run_hc_judgments(max_files: int = 100) -> int:
    print("\n  [HC] Indian-High-Court-Judgments-all (HuggingFace)")
    r = requests.get(HC_PARQUET_API, headers=HF_HEADERS, timeout=15)
    r.raise_for_status()
    urls = r.json().get("default", {}).get("train", [])
    urls = urls[:max_files]
    print(f"  Files to scan: {len(urls)}")

    total_chunks = 0
    total_cases  = 0

    for i, url in enumerate(tqdm(urls, desc="  HC parquet files")):
        table = fetch_parquet(url)
        if table is None:
            continue
        df = table.to_pydict()
        n_rows = table.num_rows

        for j in range(n_rows):
            instruction = str(df.get("instruction", [""])[j] or "")
            output_text = str(df.get("output", [""])[j] or "")

            if not is_relevant(output_text):
                continue
            if len(output_text.split()) < 30:
                continue

            case_id = hashlib.md5(f"hc_{i}_{j}_{output_text[:80]}".encode()).hexdigest()
            meta = {
                "source":        "HuggingFace/Immanuel30303",
                "document_type": "high_court_verdict",
                "state":         "TS",
                "case_id":       case_id,
                "title":         instruction[:200],
                "court":         "High Court (Telangana-relevant)",
            }
            chunks = chunk_and_embed(output_text, meta)
            total_chunks += chunks
            if chunks:
                total_cases += 1

        time.sleep(0.2)

    print(f"  HC done: {total_cases} relevant cases, {total_chunks} chunks")
    return total_chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_verdicts_hf(max_sc_files: int = 76, max_hc_files: int = 100) -> int:
    print(f"\nVerdicts Scraper (HuggingFace): Starting...")
    print(f"  Current DB count: {_col.count():,}")

    sc_chunks = run_sc_judgments(max_files=max_sc_files)
    hc_chunks = run_hc_judgments(max_files=max_hc_files)

    total = sc_chunks + hc_chunks
    print(f"\nDone. Total new chunks: {total}")
    print(f"ChromaDB court_verdicts total: {_col.count():,}")
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Court Verdicts from HuggingFace datasets")
    parser.add_argument("--max-sc",   type=int, default=76,  help="Max SC parquet files (76 total)")
    parser.add_argument("--max-hc",   type=int, default=100, help="Max HC parquet files (100 total)")
    parser.add_argument("--fresh",    action="store_true",   help="Re-ingest all (clears existing)")
    args = parser.parse_args()

    if args.fresh:
        try:
            _chroma.delete_collection("court_verdicts_chunks")
        except Exception:
            pass
        _col = _chroma.get_or_create_collection("court_verdicts_chunks")

    run_verdicts_hf(max_sc_files=args.max_sc, max_hc_files=args.max_hc)
