"""Main debate engine — orchestrates full GO analysis pipeline.

Pipeline:
  1. Gemini Flash  — parse GO metadata + build RAG context
  2. Expert Panel  — 4 domain experts identify issues + impact
  3. Debate        — 3-round GO Lawyer vs Constitution Lawyer (Claude Haiku)
  4. Judge         — neutral verdict + conflict scores (Claude Sonnet)
  5. POTATO        — devil's advocate stress-test
  6. Onion         — PIN stakeholder analysis
  7. Strategy      — final legal strategy report
"""
import json
import argparse
from datetime import datetime
from pathlib import Path
from gemma.rag_pipeline import build_context
from agents import go_lawyer, const_lawyer, judge_arbiter
from agents.expert_panel import run_expert_panel
from agents.potato_analysis import run_potato
from agents.onion_analysis import run_onion
from agents.strategy_analysis import run_strategy
from config import MIN_CONFLICT_SCORE_FOR_AMENDMENTS


def run_debate(go_text: str, verbose: bool = True, use_cache: bool = True) -> dict:
    # Step 1 — RAG context
    if verbose:
        print("\n[1/7] Parsing GO + searching ChromaDB (Gemini Flash)...")
    context = build_context(go_text)
    go_meta = context.get("go_metadata", {})
    if verbose:
        print(f"      GO: {go_meta.get('go_number', 'N/A')} | Dept: {go_meta.get('department', 'Unknown')} | Type: {go_meta.get('go_type', 'N/A')}")
        print(f"      Found: {len(context['related_articles'])} articles, {len(context['related_acts'])} acts, "
              f"{len(context['state_laws'])} state laws, {len(context['relevant_verdicts'])} verdicts")

    # Step 2 — Expert Panel (PARALLEL execution)
    if verbose:
        cache_msg = " (with cache enabled)" if use_cache else " (cache disabled)"
        print(f"\n[2/7] Expert Panel Analysis (4 experts in PARALLEL — Claude Sonnet){cache_msg}...")
    expert_panel = run_expert_panel(context, use_cache=use_cache, verbose=verbose)
    if verbose:
        cache_source = " [CACHED]" if expert_panel.get("_from_cache") else " [FRESH]"
        exec_time = expert_panel.get("_execution_time_seconds", "N/A")
        print(f"      Issues found: {expert_panel['total_issues']} total, {expert_panel['critical_count']} CRITICAL{cache_source}")
        if not expert_panel.get("_from_cache"):
            print(f"      Parallel execution time: {exec_time}s")

    # Steps 3-4 — Debate + Judge
    transcript = {"rounds": [], "go_text": go_text, "timestamp": datetime.now().isoformat()}
    go_arg = const_arg = ""

    for round_num in range(1, 4):
        if verbose:
            print(f"\n[{round_num + 2}/7] Round {round_num} — Debating (Claude Haiku)...")
        go_arg   = go_lawyer.argue(context, round_num, opponent_last_argument=const_arg)
        const_arg = const_lawyer.argue(context, round_num, opponent_last_argument=go_arg)
        transcript["rounds"].append({
            "round": round_num,
            "go_lawyer": go_arg,
            "const_lawyer": const_arg,
        })
        if verbose:
            print(f"      Round {round_num} complete.")

    if verbose:
        print("\n[6/7] Judge scoring (Claude Sonnet)...")
    verdict = judge_arbiter.score_debate(context, transcript)
    transcript["verdict"] = verdict

    # Steps 5-7 — POTATO, Onion, Strategy
    if verbose:
        print("\n[7/7] POTATO + Onion + Strategy Analysis (Claude Sonnet)...")
    potato   = run_potato(context, expert_panel, verdict)
    onion    = run_onion(context, expert_panel, verdict)
    strategy = run_strategy(context, expert_panel, verdict, potato, onion)

    result = {
        "go_metadata":        go_meta,
        "timestamp":          datetime.now().isoformat(),
        "expert_panel":       expert_panel,
        "debate_transcript":  transcript,
        "verdict":            verdict,
        "potato_analysis":    potato,
        "onion_analysis":     onion,
        "strategy":           strategy,
    }

    if verbose:
        _print_final_report(result)

    return result


def _print_final_report(result: dict):
    verdict  = result["verdict"]
    strategy = result["strategy"]
    panel    = result["expert_panel"]

    w = 70
    print("\n" + "=" * w)
    meta = result["go_metadata"]
    print(f"GO: {meta.get('go_number', 'N/A')}  |  {meta.get('department', '')}  |  {meta.get('subject', '')[:45]}")
    print("=" * w)
    print(f"  VERDICT             : {verdict.get('verdict', 'N/A')}")
    print(f"  COMPOSITE SCORE     : {verdict.get('composite_score', 'N/A')}/10")
    print(f"  HC SUCCESS PROB     : {verdict.get('hc_success_probability', 'N/A')}")
    print(f"  TOTAL ISSUES        : {panel.get('total_issues', 0)}  ({panel.get('critical_count', 0)} CRITICAL)")
    print(f"  OVERALL RISK        : {strategy.get('overall_risk', 'N/A')}")
    print(f"  GO STATUS           : {strategy.get('go_status', 'N/A')}")
    print("-" * w)
    print("EXECUTIVE SUMMARY:")
    print(f"  {strategy.get('executive_summary', '')}")
    print("-" * w)
    print("IMMEDIATE ACTIONS:")
    for a in strategy.get("immediate_actions", [])[:3]:
        print(f"  [{a.get('timeline', '?').upper():20s}]  {a.get('action', '')}")
    print("-" * w)
    lit = strategy.get("litigation_strategy", {})
    print(f"LITIGATION: {lit.get('best_forum', 'N/A')} | {lit.get('writ_type', 'N/A')} | {lit.get('success_probability', 'N/A')}")
    print(f"INTERIM RELIEF: {lit.get('interim_relief', 'N/A')[:80]}")
    print("=" * w)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LegalDebateAI — Analyze a Telangana Government Order")
    parser.add_argument("--go",     type=str, help="GO text")
    parser.add_argument("--file",   type=str, help="Path to GO PDF or text file")
    parser.add_argument("--output", type=str, help="Save full report to JSON file")
    parser.add_argument("--no-cache", action="store_true", help="Disable expert panel caching (always run fresh analysis)")
    parser.add_argument("--cache-stats", action="store_true", help="Show cache statistics and exit")
    parser.add_argument("--clear-cache", action="store_true", help="Clear entire cache and exit")
    args = parser.parse_args()

    # Handle cache management commands
    if args.cache_stats or args.clear_cache:
        from agents.cache_manager import get_cache_stats, clear_cache
        if args.clear_cache:
            clear_cache()
            print("✓ Cache cleared successfully")
        if args.cache_stats:
            stats = get_cache_stats()
            print(f"\n{'='*60}")
            print(f"Cache Statistics")
            print(f"{'='*60}")
            print(f"Total cached analyses: {stats['total_cached_analyses']}")
            print(f"Cache file: {stats['cache_file']}\n")
            if stats['cache_entries']:
                print("Cached GOs:")
                for entry in stats['cache_entries']:
                    print(f"  • {entry['go_number']} ({entry['department']}) — {entry['cached_at']}")
            else:
                print("(No analyses cached yet)")
            print(f"{'='*60}")
        exit(0)

    if args.file:
        p = Path(args.file)
        if p.suffix.lower() == ".pdf":
            from pypdf import PdfReader
            reader = PdfReader(str(p))
            go_text = "\n".join(page.extract_text() or "" for page in reader.pages)
        else:
            with open(args.file, "r", encoding="utf-8") as f:
                go_text = f.read()
    elif args.go:
        go_text = args.go
    else:
        print("Usage: python debate_engine.py --go 'GO text here'")
        print("       python debate_engine.py --file path/to/go.txt")
        print("       python debate_engine.py --cache-stats")
        print("       python debate_engine.py --clear-cache")
        exit(1)

    result = run_debate(go_text, use_cache=not args.no_cache)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        print(f"\nFull report saved to: {args.output}")
