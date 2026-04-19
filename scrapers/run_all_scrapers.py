"""Master data ingestion pipeline — runs all scrapers in order.

Order:
  1. Constitution of India
  2. Central Acts (IndiaCode)
  3. Telangana State Acts
  4. Court Verdicts (HuggingFace datasets — SC + HC judgments, no API key required)
  5. Telangana GOs 2025 (remaining from Internet Archive)
"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import time
import chromadb
from config import CHROMA_PATH
from scrapers.constitution_scraper import run_constitution
from scrapers.central_acts_scraper  import run_central_acts
from scrapers.state_acts_scraper    import run_state_acts
from scrapers.verdicts_hf_scraper   import run_verdicts_hf
from scrapers.ts_go_scraper         import run_phase1


def print_db_status():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    collections = [
        "constitution_chunks",
        "central_acts_chunks",
        "state_acts_chunks",
        "court_verdicts_chunks",
        "government_orders_chunks",
    ]
    print("\n" + "=" * 55)
    print("  ChromaDB Collection Status")
    print("=" * 55)
    for name in collections:
        try:
            col   = client.get_or_create_collection(name)
            count = col.count()
        except Exception:
            count = 0
        label = name.replace("_chunks", "").replace("_", " ").title()
        status = "OK" if count > 0 else "EMPTY"
        print(f"  {label:<30} {count:>6,} chunks  [{status}]")
    print("=" * 55)


def run_all(
    max_central_acts: int = 500,
    max_state_acts:   int = 300,
    max_verdicts:     int = 200,
    max_gos:          int = 2500,
    fresh:            bool = False,
):
    start = time.time()
    results = {}

    print("\n" + "=" * 55)
    print("  LegalDebateAI — Full Data Ingestion Pipeline")
    print("=" * 55)
    print_db_status()

    # 1. Constitution
    print("\n[1/5] Constitution of India")
    results["constitution"] = run_constitution(fresh=fresh)

    # 2. Central Acts
    print("\n[2/5] Central Acts (IndiaCode)")
    results["central_acts"] = run_central_acts(
        max_acts=max_central_acts, skip_existing=not fresh
    )

    # 3. Telangana State Acts
    print("\n[3/5] Telangana State Acts")
    results["state_acts"] = run_state_acts(
        max_acts=max_state_acts, skip_existing=not fresh
    )

    # 4. Court Verdicts (HuggingFace datasets — no API key required)
    print("\n[4/5] Court Verdicts (HuggingFace: SC + HC judgments)")
    results["verdicts"] = run_verdicts_hf(
        max_sc_files=max_verdicts, max_hc_files=max_verdicts
    )

    # 5. Remaining Telangana GOs 2025
    print("\n[5/5] Telangana GOs 2025 (Internet Archive — all remaining)")
    results["gos"] = run_phase1(
        year=2025, max_gos=max_gos, skip_existing=not fresh
    )

    elapsed = time.time() - start
    print(f"\n{'=' * 55}")
    print(f"  Pipeline complete in {elapsed / 60:.1f} minutes")
    print(f"  New chunks added:")
    for k, v in results.items():
        print(f"    {k:<20} {v:>6,}")
    print_db_status()

    return results


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Run all LegalDebateAI data scrapers")
    parser.add_argument("--max-central-acts", type=int, default=500)
    parser.add_argument("--max-state-acts",   type=int, default=300)
    parser.add_argument("--max-verdicts",     type=int, default=200)
    parser.add_argument("--max-gos",          type=int, default=2500,
                        help="Max GOs to fetch (archive has ~2349 for 2025)")
    parser.add_argument("--fresh", action="store_true",
                        help="Delete all existing data and re-ingest from scratch")
    parser.add_argument("--no-confirm", action="store_true",
                        help="Skip confirmation prompts for destructive operations")
    args = parser.parse_args()

    if args.fresh:
        if not args.no_confirm:
            confirm = input("WARNING: --fresh will delete ALL existing ChromaDB data. Type 'yes' to confirm: ")
            if confirm.strip().lower() != "yes":
                print("Aborted.")
                sys.exit(0)
        else:
            print("WARNING: --fresh enabled with --no-confirm, proceeding without confirmation...")

    run_all(
        max_central_acts=args.max_central_acts,
        max_state_acts=args.max_state_acts,
        max_verdicts=args.max_verdicts,
        max_gos=args.max_gos,
        fresh=args.fresh,
    )
