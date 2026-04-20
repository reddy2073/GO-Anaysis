"""
LegalDebateAI Autopilot — keeps scrapers running until all DB targets are met.

Run manually:   python scripts/autopilot.py
Scheduled:      every 2 hours via Windows Task Scheduler (LegalDebateAI_Autopilot)

On each invocation:
  1. Check each collection count vs target
  2. For incomplete collections, detect if the scraper is already running
  3. Launch scrapers for any gaps (background subprocess, detached)
  4. Log every action to scripts/autopilot.log
"""

import sys
import os
import subprocess
import chromadb
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

LOG_FILE = PROJECT_ROOT / "scripts" / "autopilot.log"
PYTHON   = str(PROJECT_ROOT / "venv" / "Scripts" / "python.exe")

TARGETS = {
    "constitution_chunks":      200,
    "central_acts_chunks":      5000,
    "state_acts_chunks":        2500,
    "sc_verdicts_chunks":       500000,
    "hc_verdicts_chunks":       100000,
    "government_orders_chunks": 25000,
}

# Maps collection name → (script path relative to project root, extra args)
SCRAPER_MAP = {
    "sc_verdicts_chunks":       ("scrapers/verdicts_hf_scraper.py", ["--sc-only"]),
    "hc_verdicts_chunks":       ("scrapers/verdicts_hf_scraper.py", ["--hc-only"]),
    "government_orders_chunks": ("scrapers/ts_go_scraper.py",       ["--year", "2025", "--max", "2500"]),
    "central_acts_chunks":      ("scrapers/central_acts_scraper.py", []),
    "state_acts_chunks":        ("scrapers/state_acts_scraper.py",   []),
    "constitution_chunks":      ("scrapers/constitution_scraper.py", []),
}

# Keyword in cmdline that identifies each scraper process
SCRAPER_KEYWORD = {
    "sc_verdicts_chunks":       "verdicts_hf_scraper",
    "hc_verdicts_chunks":       "verdicts_hf_scraper",
    "government_orders_chunks": "ts_go_scraper",
    "central_acts_chunks":      "central_acts_scraper",
    "state_acts_chunks":        "state_acts_scraper",
    "constitution_chunks":      "constitution_scraper",
}


def log(msg: str):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    line = f"{ts}  {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def get_counts() -> dict:
    from config import CHROMA_PATH
    client = chromadb.PersistentClient(path=str(CHROMA_PATH))
    counts = {}
    for name in TARGETS:
        try:
            col = client.get_or_create_collection(name)
            counts[name] = col.count()
        except Exception as e:
            counts[name] = 0
            log(f"  [WARN] count error for {name}: {e}")
    return counts


def running_cmdlines() -> list[str]:
    """Return list of command lines for all running python processes."""
    try:
        import psutil
        lines = []
        for proc in psutil.process_iter(["name", "cmdline"]):
            try:
                if proc.info["name"] and "python" in proc.info["name"].lower():
                    lines.append(" ".join(proc.info["cmdline"] or []))
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return lines
    except ImportError:
        # psutil not available — fall back to tasklist
        try:
            out = subprocess.check_output(
                ["powershell", "-Command",
                 "Get-WmiObject Win32_Process -Filter \"name='python.exe'\" | Select-Object CommandLine | Format-List"],
                text=True, stderr=subprocess.DEVNULL
            )
            return [out]
        except Exception:
            return []


def is_scraper_running(keyword: str, cmdlines: list[str]) -> bool:
    return any(keyword in c for c in cmdlines)


def launch_scraper(collection: str) -> bool:
    script, args = SCRAPER_MAP[collection]
    script_path = str(PROJECT_ROOT / script.replace("/", os.sep))
    cmd = [PYTHON, script_path] + args

    log(f"  [LAUNCH] {collection}: {' '.join(cmd)}")
    try:
        # Detached so it keeps running after this script exits
        subprocess.Popen(
            cmd,
            cwd=str(PROJECT_ROOT),
            creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP,
            stdout=open(LOG_FILE.parent / f"{collection}.log", "a"),
            stderr=subprocess.STDOUT,
        )
        return True
    except Exception as e:
        log(f"  [ERROR] failed to launch {collection}: {e}")
        return False


def main():
    log("=" * 60)
    log("LegalDebateAI Autopilot — checking collections")

    counts    = get_counts()
    cmdlines  = running_cmdlines()
    started   = []
    skipped   = []
    complete  = []

    for col, target in TARGETS.items():
        count = counts.get(col, 0)
        pct   = min(100, round(count / target * 100, 1)) if target else 100

        if count >= target:
            complete.append(f"{col}: {count:,} ✓")
            continue

        keyword = SCRAPER_KEYWORD.get(col, col)
        if is_scraper_running(keyword, cmdlines):
            skipped.append(f"{col}: {count:,}/{target:,} ({pct}%) — already running")
            continue

        log(f"  [NEED]  {col}: {count:,}/{target:,} ({pct}%) — launching scraper")
        if launch_scraper(col):
            started.append(col)

    log("-" * 40)
    log(f"Complete  : {len(complete)} collections")
    log(f"Launched  : {started if started else 'none'}")
    log(f"Already running: {skipped if skipped else 'none'}")
    log("=" * 60)


if __name__ == "__main__":
    main()
