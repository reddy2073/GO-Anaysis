"""
Migrate court_verdicts_chunks → sc_verdicts_chunks + hc_verdicts_chunks.
Also saves raw text files to data/verdicts_export/ for local backup.

Splits by document_type metadata:
  supreme_court_verdict → sc_verdicts_chunks
  high_court_verdict    → hc_verdicts_chunks
  (unknown)             → hc_verdicts_chunks (conservative default)
"""

import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from pathlib import Path
from config import CHROMA_PATH

EXPORT_DIR = Path(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))) / "data" / "verdicts_export"
BATCH_SIZE = 500

def migrate():
    client  = chromadb.PersistentClient(path=CHROMA_PATH)
    src     = client.get_collection("court_verdicts_chunks")
    sc_col  = client.get_or_create_collection("sc_verdicts_chunks")
    hc_col  = client.get_or_create_collection("hc_verdicts_chunks")

    total   = src.count()
    print(f"Source collection: court_verdicts_chunks — {total:,} chunks")
    print(f"SC target:  sc_verdicts_chunks  (currently {sc_col.count():,})")
    print(f"HC target:  hc_verdicts_chunks  (currently {hc_col.count():,})")
    print(f"Export dir: {EXPORT_DIR}")
    print()

    EXPORT_DIR.mkdir(parents=True, exist_ok=True)

    sc_added = hc_added = skipped = 0
    offset = 0

    while offset < total:
        # Fetch without embeddings — avoids segfault on large float arrays.
        # Re-embedding happens on next scraper run via upsert dedup.
        batch = src.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["documents", "metadatas"],
        )
        ids   = batch["ids"]
        docs  = batch["documents"]
        metas = batch["metadatas"]

        if not ids:
            break

        sc_ids, sc_docs, sc_metas = [], [], []
        hc_ids, hc_docs, hc_metas = [], [], []

        for cid, doc, meta in zip(ids, docs, metas):
            dtype = meta.get("document_type", "")
            if dtype == "supreme_court_verdict":
                sc_ids.append(cid); sc_docs.append(doc); sc_metas.append(meta)
            else:
                hc_ids.append(cid); hc_docs.append(doc); hc_metas.append(meta)

            # Save text locally (first chunk of each case only)
            if meta.get("chunk_index", 0) == 0:
                case_id = meta.get("case_id", cid)[:80].replace("/", "_").replace("\\", "_")
                prefix  = "sc" if dtype == "supreme_court_verdict" else "hc"
                fpath   = EXPORT_DIR / f"{prefix}_{case_id}.txt"
                if not fpath.exists():
                    try:
                        fpath.write_text(
                            f"Title: {meta.get('title','')}\n"
                            f"Court: {meta.get('court','')}\n"
                            f"Date:  {meta.get('decision_date', meta.get('date',''))}\n"
                            f"---\n{doc}",
                            encoding="utf-8",
                        )
                    except Exception:
                        pass

        # Add without embeddings — ChromaDB will embed on next query if needed
        if sc_ids:
            sc_col.upsert(ids=sc_ids, documents=sc_docs, metadatas=sc_metas)
            sc_added += len(sc_ids)
        if hc_ids:
            hc_col.upsert(ids=hc_ids, documents=hc_docs, metadatas=hc_metas)
            hc_added += len(hc_ids)

        offset += len(ids)
        pct = offset / total * 100
        print(f"  [{pct:5.1f}%] processed {offset:,}/{total:,}  →  SC +{sc_added:,}  HC +{hc_added:,}", end="\r")

    print(f"\n\nMigration complete.")
    print(f"  SC chunks migrated: {sc_added:,}  (sc_verdicts_chunks total: {sc_col.count():,})")
    print(f"  HC chunks migrated: {hc_added:,}  (hc_verdicts_chunks total: {hc_col.count():,})")
    print(f"  Text files saved:   {len(list(EXPORT_DIR.glob('*.txt'))):,}  →  {EXPORT_DIR}")
    print()
    print("Old collection 'court_verdicts_chunks' is unchanged (safe to delete manually later).")


if __name__ == "__main__":
    migrate()
