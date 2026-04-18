"""Constitution of India scraper — downloads and ingests the Constitution PDF into ChromaDB."""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import re, hashlib, requests, chromadb, pdfplumber, pytesseract
from pathlib import Path
from pdf2image import convert_from_path
from sentence_transformers import SentenceTransformer
from config import CHROMA_PATH, EMBED_MODEL, TESSERACT_PATH, OCR_LANGUAGES, DATA_DIR

pytesseract.pytesseract.tesseract_cmd = TESSERACT_PATH

_chroma   = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)
_col      = _chroma.get_or_create_collection("constitution_chunks")

CONST_DIR     = Path(DATA_DIR) / "constitution"
CHUNK_SIZE    = 800
CHUNK_OVERLAP = 100
HEADERS       = {"User-Agent": "LegalDebateAI/1.0 (research; contact: reddy2073@gmail.com)"}

# Official government CDN — Constitution as amended up to Nov 2024 (106th Amendment)
SOURCES = [
    {
        "name":     "Constitution of India (as amended, Nov 2024)",
        "url":      "https://cdnbbsr.s3waas.gov.in/s380537a945c7aaa788ccfcdf1b99b5d8f/uploads/2024/11/202411291130199951.pdf",
        "filename": "constitution_of_india_nov2024.pdf",
    },
    {
        "name":     "Constitution of India (legislative.gov.in)",
        "url":      "https://www.legislative.gov.in/static/uploads/2025/12/aa187bd277347972681116b208a267e2.pdf",
        "filename": "constitution_of_india_legislative.pdf",
    },
]


def _download(url: str, dest: Path) -> bool:
    resp = requests.get(url, headers=HEADERS, timeout=120, stream=True)
    resp.raise_for_status()
    dest.write_bytes(resp.content)
    return True


def _extract_text(pdf_path: Path) -> str:
    text = ""
    try:
        with pdfplumber.open(str(pdf_path)) as pdf:
            for page in pdf.pages:
                text += (page.extract_text() or "") + "\n"
    except Exception:
        pass
    if len(text.strip()) < 500:
        try:
            images = convert_from_path(str(pdf_path), dpi=200)
            for img in images:
                text += pytesseract.image_to_string(img, lang=OCR_LANGUAGES) + "\n"
        except Exception as e:
            print(f"    OCR failed: {e}")
    return text.strip()


def _chunk(text: str, base_meta: dict) -> list[tuple[str, dict]]:
    """Article-level chunking with sliding-window fallback."""
    article_re = re.compile(
        r'(Article\s+\d+[A-Za-z]?\.?\s*[—\-]?\s*.{0,100})',
        re.IGNORECASE,
    )
    parts = article_re.split(text)

    results = []
    if len(parts) > 3:
        i = 1
        while i < len(parts):
            header = parts[i].strip()
            body   = parts[i + 1].strip() if (i + 1) < len(parts) else ""
            combined = f"{header}\n{body}"
            if len(combined.split()) >= 20:
                m = re.search(r'\d+', header)
                results.append((combined[:3200], {
                    **base_meta,
                    "article":    m.group() if m else "",
                    "section":    header[:120],
                    "chunk_type": "article",
                }))
            i += 2

    if not results:
        words = text.split()
        for i in range(0, len(words), CHUNK_SIZE - CHUNK_OVERLAP):
            chunk = " ".join(words[i : i + CHUNK_SIZE])
            if len(chunk.strip()) >= 50:
                results.append((chunk, {**base_meta, "article": "", "section": "", "chunk_type": "passage"}))

    return results


def _ingest_source(src: dict) -> int:
    CONST_DIR.mkdir(parents=True, exist_ok=True)
    dest = CONST_DIR / src["filename"]

    if dest.exists() and dest.stat().st_size > 100_000:
        print(f"    Already downloaded: {dest.name}")
    else:
        print(f"    Downloading: {src['name']} ...")
        try:
            _download(src["url"], dest)
            print(f"    → {dest.stat().st_size // 1024} KB")
        except Exception as e:
            print(f"    Download failed: {e}")
            return 0

    print("    Extracting text...")
    text = _extract_text(dest)
    if not text:
        print("    ERROR: No text extracted.")
        return 0
    print(f"    {len(text.split()):,} words extracted.")

    base_meta = {
        "source":        src["name"],
        "document_type": "constitution",
        "state":         "IN",
        "filename":      src["filename"],
    }
    chunks = _chunk(text, base_meta)

    ids, docs, metas, embs = [], [], [], []
    for i, (chunk_text, meta) in enumerate(chunks):
        cid = hashlib.md5(f"{src['filename']}_{i}".encode()).hexdigest()
        # Skip if already in DB
        existing = _col.get(ids=[cid])
        if existing["ids"]:
            continue
        ids.append(cid)
        docs.append(chunk_text)
        metas.append({**meta, "chunk_index": i})
        embs.append(_embedder.encode(chunk_text).tolist())

    if ids:
        _col.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=embs)
    print(f"    Ingested {len(ids)} new chunks.")
    return len(ids)


def run_constitution(fresh: bool = False):
    print("\nConstitution Scraper: Starting...")

    if not fresh:
        count = _col.count()
        if count > 0:
            print(f"  Already ingested ({count:,} chunks). Use --fresh to re-ingest.")
            return count

    total = 0
    for src in SOURCES:
        print(f"\n  Source: {src['name']}")
        n = _ingest_source(src)
        total += n
        if n > 0:
            break  # One good copy is enough

    print(f"\nDone. Constitution chunks in ChromaDB: {_col.count():,}")
    return total


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Ingest Constitution of India")
    parser.add_argument("--fresh", action="store_true", help="Delete existing and re-ingest")
    args = parser.parse_args()

    if args.fresh:
        try:
            _chroma.delete_collection("constitution_chunks")
        except Exception:
            pass
        _col = _chroma.get_or_create_collection("constitution_chunks")

    run_constitution(fresh=args.fresh)
