"""Court Verdicts scraper — HuggingFace parquet datasets (no auth required).

Sources:
  SC: labofsahil/Indian-Supreme-Court-Judgments  (CC-BY-4.0)
      76 parquet files — ALL judgments ingested, no keyword filter.
      Binding precedent governs what any state GO can legally do.

  HC: Immanuel30303/Indian-High-Court-Judgments-all  (CC-BY-4.0)
      100 parquet files — filtered for Telangana-relevant cases.
      Phase 2 will replace this with a dedicated TS HC scraper.

Collections:
  sc_verdicts_chunks  — Supreme Court (all judgments)
  hc_verdicts_chunks  — High Court (Telangana-filtered, interim)
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
_sc_col   = _chroma.get_or_create_collection("sc_verdicts_chunks")
_hc_col   = _chroma.get_or_create_collection("hc_verdicts_chunks")

CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100

HF_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
}

SC_PARQUET_API = "https://huggingface.co/api/datasets/labofsahil/Indian-Supreme-Court-Judgments/parquet"
HC_PARQUET_API = "https://huggingface.co/api/datasets/Immanuel30303/Indian-High-Court-Judgments-all/parquet"

# HC-only filter — SC ingests everything
HC_KEYWORDS = [
    "telangana", "hyderabad", "andhra", "land acquisition", "revenue",
    "government order", "g.o.", "municipal", "panchayat", "urban land",
    "property tax", "building permission", "demolition", "encroachment",
    "public employment", "reservation", "forest", "irrigation", "water",
]


def is_hc_relevant(text: str) -> bool:
    low = text.lower()
    return any(kw in low for kw in HC_KEYWORDS)


def html_to_text(raw_html: str) -> str:
    if not raw_html or len(raw_html.strip()) < 20:
        return ""
    return BeautifulSoup(raw_html, "html.parser").get_text(separator="\n", strip=True)


def chunk_and_embed(text: str, meta: dict, col) -> int:
    words = text.split()
    ids, docs, metas, embs = [], [], [], []
    idx, n = 0, 0
    while idx < len(words):
        chunk = " ".join(words[idx: idx + CHUNK_SIZE])
        if len(chunk.strip()) >= 50:
            cid = hashlib.md5(f"{meta['case_id']}_{n}".encode()).hexdigest()
            if not col.get(ids=[cid])["ids"]:
                ids.append(cid)
                docs.append(chunk)
                metas.append({**meta, "chunk_index": n})
                embs.append(_embedder.encode(chunk).tolist())
            n += 1
        idx += CHUNK_SIZE - CHUNK_OVERLAP
    if ids:
        col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
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
# SC — all judgments, no keyword filter
# ---------------------------------------------------------------------------

def run_sc_judgments(max_files: int = 76) -> int:
    print("\n  [SC] Indian-Supreme-Court-Judgments — ALL judgments (no filter)")
    print(f"  Current SC chunks: {_sc_col.count():,}")

    r = requests.get(SC_PARQUET_API, headers=HF_HEADERS, timeout=15)
    r.raise_for_status()
    urls = r.json().get("default", {}).get("train", [])[:max_files]
    print(f"  Parquet files to process: {len(urls)}")

    total_chunks = 0
    total_cases  = 0

    for i, url in enumerate(tqdm(urls, desc="  SC parquet files")):
        table = fetch_parquet(url)
        if table is None:
            continue
        df    = table.to_pydict()
        n_rows = table.num_rows

        for j in range(n_rows):
            raw_html = str(df.get("raw_html", [""])[j] or "")
            text     = html_to_text(raw_html)
            if not text or len(text.split()) < 30:
                continue

            title      = str(df.get("title",      [""])[j] or "")
            petitioner = str(df.get("petitioner", [""])[j] or "")
            respondent = str(df.get("respondent", [""])[j] or "")
            case_id    = str(df.get("case_id",    [""])[j] or f"sc_{i}_{j}")

            meta = {
                "source":        "HuggingFace/labofsahil",
                "document_type": "supreme_court_verdict",
                "case_id":       case_id[:100],
                "title":         title[:200],
                "petitioner":    petitioner[:150],
                "respondent":    respondent[:150],
                "judge":         str(df.get("judge",         [""])[j] or "")[:150],
                "citation":      str(df.get("citation",      [""])[j] or "")[:100],
                "decision_date": str(df.get("decision_date", [""])[j] or "")[:30],
                "year":          str(df.get("year",          [""])[j] or ""),
                "court":         "Supreme Court of India",
            }
            chunks = chunk_and_embed(text, meta, _sc_col)
            total_chunks += chunks
            if chunks:
                total_cases += 1

        time.sleep(0.2)

    print(f"  SC done: {total_cases:,} cases ingested, {total_chunks:,} new chunks")
    print(f"  SC total in DB: {_sc_col.count():,}")
    return total_chunks


# ---------------------------------------------------------------------------
# HC — Telangana-relevant filter (interim until Phase 2 TS HC scraper)
# ---------------------------------------------------------------------------

def run_hc_judgments(max_files: int = 100) -> int:
    print("\n  [HC] Indian-High-Court-Judgments-all — Telangana-filtered (interim)")
    print(f"  Current HC chunks: {_hc_col.count():,}")

    r = requests.get(HC_PARQUET_API, headers=HF_HEADERS, timeout=15)
    r.raise_for_status()
    urls = r.json().get("default", {}).get("train", [])[:max_files]
    print(f"  Parquet files to process: {len(urls)}")

    total_chunks = 0
    total_cases  = 0

    for i, url in enumerate(tqdm(urls, desc="  HC parquet files")):
        table = fetch_parquet(url)
        if table is None:
            continue
        df    = table.to_pydict()
        n_rows = table.num_rows

        for j in range(n_rows):
            output_text  = str(df.get("output",      [""])[j] or "")
            instruction  = str(df.get("instruction", [""])[j] or "")

            if not is_hc_relevant(output_text) or len(output_text.split()) < 30:
                continue

            case_id = hashlib.md5(f"hc_{i}_{j}_{output_text[:80]}".encode()).hexdigest()
            meta = {
                "source":        "HuggingFace/Immanuel30303",
                "document_type": "high_court_verdict",
                "case_id":       case_id,
                "title":         instruction[:200],
                "court":         "High Court (Telangana-relevant)",
                "state":         "TS",
            }
            chunks = chunk_and_embed(output_text, meta, _hc_col)
            total_chunks += chunks
            if chunks:
                total_cases += 1

        time.sleep(0.2)

    print(f"  HC done: {total_cases:,} cases ingested, {total_chunks:,} new chunks")
    print(f"  HC total in DB: {_hc_col.count():,}")
    return total_chunks


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run_verdicts_hf(max_sc_files: int = 76, max_hc_files: int = 100) -> int:
    print(f"\nVerdicts Scraper (HuggingFace): Starting...")
    sc_chunks = run_sc_judgments(max_files=max_sc_files)
    hc_chunks = run_hc_judgments(max_files=max_hc_files)
    total = sc_chunks + hc_chunks
    print(f"\nVerdicts done. New chunks — SC: {sc_chunks:,}  HC: {hc_chunks:,}  Total: {total:,}")
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--max-sc", type=int, default=76,  help="SC parquet files (76 total)")
    parser.add_argument("--max-hc", type=int, default=100, help="HC parquet files (100 total)")
    parser.add_argument("--sc-only", action="store_true",  help="Run SC ingestion only")
    parser.add_argument("--hc-only", action="store_true",  help="Run HC ingestion only")
    args = parser.parse_args()

    if args.sc_only:
        run_sc_judgments(max_files=args.max_sc)
    elif args.hc_only:
        run_hc_judgments(max_files=args.max_hc)
    else:
        run_verdicts_hf(max_sc_files=args.max_sc, max_hc_files=args.max_hc)
