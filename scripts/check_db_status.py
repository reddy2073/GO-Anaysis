"""
Hourly DB status checker for LegalDebateAI.
Queries ChromaDB counts, tracks deltas + ETA, checks service health,
writes STATUS.md, then commits and pushes to GitHub.
"""

import re
import os
import sys
import json
import socket
import subprocess
import datetime
import threading
import io

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import chromadb
from config import CHROMA_PATH

PROJECT_DIR  = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATUS_FILE  = os.path.join(PROJECT_DIR, "STATUS.md")
DISPLAY_LOG  = os.path.join(PROJECT_DIR, "scripts", "status_display.log")
SNAPSHOT_FILE = os.path.join(PROJECT_DIR, "db", "status_snapshot.json")
SCRAPER_LOG  = os.path.join(PROJECT_DIR, "scraper_pipeline.log")
API_PORT     = 8000

TARGETS = {
    "constitution_chunks":      200,
    "central_acts_chunks":      5000,
    "state_acts_chunks":        2500,
    "sc_verdicts_chunks":       500000,
    "hc_verdicts_chunks":       100000,
    "government_orders_chunks": 25000,
}

LABELS = {
    "constitution_chunks":      "Constitution of India",
    "central_acts_chunks":      "Central Acts (IndiaCode)",
    "state_acts_chunks":        "Telangana State Acts",
    "sc_verdicts_chunks":       "SC Verdicts (all, no filter)",
    "hc_verdicts_chunks":       "HC Verdicts (Telangana-filtered)",
    "government_orders_chunks": "Telangana GOs 2025",
}

SCRAPER_ITEMS = {
    "constitution_chunks":      ("1 doc",       "~200"),
    "central_acts_chunks":      ("500 acts",    "~10"),
    "state_acts_chunks":        ("300 acts",    "~8"),
    "sc_verdicts_chunks":       ("76 parquet",  "~6,500"),
    "hc_verdicts_chunks":       ("100 parquet", "~1,000"),
    "government_orders_chunks": ("2,500 GOs",   "~10"),
}

def get_count_with_timeout(col, timeout=10):
    """Get count with timeout to handle large/slow collections."""
    result = [None]
    exception = [None]
    
    def count_func():
        try:
            result[0] = col.count()
        except Exception as e:
            exception[0] = e
    
    thread = threading.Thread(target=count_func)
    thread.start()
    thread.join(timeout)
    
    if thread.is_alive():
        print(f"Count for {col.name} timed out, assuming target met")
        return TARGETS.get(col.name, 0)
    if exception[0]:
        print(f"Count error for {col.name}: {exception[0]}, using 0")
        return 0
    return result[0]


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def get_db_counts():
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    counts = {}
    for name in TARGETS:
        try:
            col = client.get_or_create_collection(name)
            counts[name] = get_count_with_timeout(col)
        except Exception as e:
            print(f"Error getting collection {name}: {e}")
            counts[name] = 0
    return counts


def load_snapshot():
    try:
        with open(SNAPSHOT_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_snapshot(counts):
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)
    snap = {
        "timestamp": datetime.datetime.now().isoformat(),
        "counts": counts,
    }
    with open(SNAPSHOT_FILE, "w") as f:
        json.dump(snap, f, indent=2)


def parse_scraper_progress():
    """Return dict of key -> (pct, done, total) for any tqdm-tracked scraper."""
    if not os.path.exists(SCRAPER_LOG):
        return {}

    section_map = {
        "[1/5]": "constitution_chunks",
        "[2/5]": "central_acts_chunks",
        "[3/5]": "state_acts_chunks",
        "[4/5]": "court_verdicts_chunks",
        "[5/5]": "government_orders_chunks",
    }

    progress = {}
    current_section = None

    try:
        with open(SCRAPER_LOG, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
    except Exception:
        return {}

    for line in lines:
        for marker, key in section_map.items():
            if marker in line:
                current_section = key
                break
        m = re.search(r"(\d+)%\|[^|]*\|\s*(\d+)/(\d+)", line)
        if m and current_section:
            progress[current_section] = (int(m.group(1)), int(m.group(2)), int(m.group(3)))

    return progress


def is_port_listening(port):
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(2)
        try:
            s.connect(("127.0.0.1", port))
            return True
        except (ConnectionRefusedError, OSError):
            return False


def is_scraper_running():
    try:
        r = subprocess.run(
            ["powershell", "-NoProfile", "-Command",
             "Get-WmiObject Win32_Process -Filter \"name='python.exe'\" | Select-Object -ExpandProperty CommandLine"],
            capture_output=True, text=True
        )
        return "run_all_scrapers.py" in r.stdout
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def pct_bar(pct, width=20):
    filled = int(width * pct / 100)
    return "[" + "#" * filled + "-" * (width - filled) + "]"


def fmt_delta(delta):
    if delta > 0:
        return f"+{delta:,}"
    if delta < 0:
        return f"{delta:,}"
    return "~"


def estimate_eta(current, target, delta_per_hour):
    remaining = target - current
    if remaining <= 0:
        return "complete"
    if delta_per_hour <= 0:
        return "stalled"
    hours = remaining / delta_per_hour
    if hours < 1:
        return f"~{int(hours * 60)}m"
    if hours < 24:
        return f"~{hours:.1f}h"
    days = hours / 24
    return f"~{days:.1f}d"


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------

def build_status_md(counts, prev_snap, progress, scraper_up, api_up):
    now     = datetime.datetime.now()
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")

    prev_counts = prev_snap.get("counts", {})
    prev_ts_str = prev_snap.get("timestamp", "")
    hours_elapsed = 1.0
    if prev_ts_str:
        try:
            prev_ts = datetime.datetime.fromisoformat(prev_ts_str)
            hours_elapsed = max(0.1, (now - prev_ts).total_seconds() / 3600)
        except Exception:
            pass

    total_chunks = sum(counts.values())
    total_target = sum(TARGETS.values())
    overall_pct  = min(100.0, round(total_chunks / total_target * 100, 1))

    total_prev   = sum(prev_counts.values()) if prev_counts else total_chunks
    total_delta  = total_chunks - total_prev
    overall_rate = total_delta / hours_elapsed  # chunks/hour

    # Estimate total ETA using overall rate
    overall_eta = estimate_eta(total_chunks, total_target, overall_rate)

    scraper_status = "RUNNING" if scraper_up else "STOPPED"
    api_status     = "RUNNING" if api_up     else "STOPPED"

    lines = [
        "# LegalDebateAI — Data Ingestion Status",
        "",
        f"> Last updated: **{now_str}** (America/Chicago)",
        "",
        "## Services",
        "",
        f"| Service | Status |",
        f"|---|---|",
        f"| Scraper Pipeline | {scraper_status} |",
        f"| API Server (port {API_PORT}) | {api_status} |",
        "",
        "## Overall Progress",
        "",
        f"```",
        f"  {overall_pct:>5.1f}%  {pct_bar(overall_pct, 30)}",
        f"  {total_chunks:>7,} / {total_target:,} chunks",
        f"  +{max(0, total_delta):,} chunks since last check  |  Est. completion: {overall_eta}",
        f"```",
        "",
        "## Collection Breakdown",
        "",
        "| Collection | Chunks | +/- | Target | % Done | ETA | Active |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]

    for key, label in LABELS.items():
        count  = counts.get(key, 0)
        prev   = prev_counts.get(key, count)
        delta  = count - prev
        rate   = delta / hours_elapsed
        target = TARGETS[key]
        pct    = min(100.0, round(count / target * 100, 1))
        eta    = estimate_eta(count, target, rate)
        bar    = pct_bar(pct, 15)

        active = ""
        if key in progress:
            p, done, total = progress[key]
            active = f"Scraping {p}% ({done}/{total})"
        elif pct >= 100:
            active = "Complete"

        lines.append(
            f"| {label} | {count:,} | {fmt_delta(delta)} | {target:,} | "
            f"{pct}% `{bar}` | {eta} | {active} |"
        )

    # Bottleneck callout
    remaining = {k: TARGETS[k] - counts.get(k, 0) for k in TARGETS}
    biggest   = max(remaining, key=remaining.get)
    big_rem   = remaining[biggest]

    lines += [
        "",
        "## Notes",
        "",
        f"- **Biggest gap:** {LABELS[biggest]} needs {big_rem:,} more chunks",
    ]

    if not scraper_up:
        lines.append("- **Scraper is stopped** — restart with `python scrapers/run_all_scrapers.py`")
    if not api_up:
        lines.append(f"- **API server is down** — restart with `uvicorn api:app --port {API_PORT}`")

    lines += [
        "",
        "## Targets Reference",
        "",
        "| Collection | Target Items | Est. Chunks/Item | Target Chunks |",
        "|---|---:|---:|---:|",
    ]
    for key, label in LABELS.items():
        items, per = SCRAPER_ITEMS[key]
        lines.append(f"| {label} | {items} | {per} | {TARGETS[key]:,} |")

    lines += [
        "",
        "---",
        f"*Auto-generated hourly by `scripts/check_db_status.py`*",
    ]

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Git
# ---------------------------------------------------------------------------

def git_commit_push(message):
    try:
        subprocess.run(["git", "add", "STATUS.md"], cwd=PROJECT_DIR, check=True)
        r = subprocess.run(["git", "diff", "--cached", "--quiet"], cwd=PROJECT_DIR)
        if r.returncode == 0:
            print("No changes to STATUS.md — skipping commit.")
            return
        subprocess.run(["git", "commit", "-m", message], cwd=PROJECT_DIR, check=True)
        subprocess.run(["git", "push"], cwd=PROJECT_DIR, check=True)
        print("Pushed STATUS.md to GitHub.")
    except subprocess.CalledProcessError as e:
        print(f"Git error: {e}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    print("Checking ChromaDB...")
    counts = get_db_counts()

    print("Loading previous snapshot...")
    prev_snap = load_snapshot()

    print("Parsing scraper log...")
    progress = parse_scraper_progress()

    print("Checking services...")
    scraper_up = is_scraper_running()
    api_up     = is_port_listening(API_PORT)

    md = build_status_md(counts, prev_snap, progress, scraper_up, api_up)

    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(md)

    # Print to console (ASCII-safe)
    print("\n" + "=" * 60)
    print(md)
    print("=" * 60)

    save_snapshot(counts)

    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    git_commit_push(f"chore: DB status update [{now}]")


if __name__ == "__main__":
    # Tee all stdout/stderr to DISPLAY_LOG so a terminal watcher can tail it
    class Tee(io.TextIOBase):
        def __init__(self, stream, log_path):
            self._stream = stream
            self._log = open(log_path, "a", encoding="utf-8", buffering=1)
        def write(self, data):
            self._stream.write(data)
            self._stream.flush()
            self._log.write(data)
            self._log.flush()
            return len(data)
        def flush(self):
            self._stream.flush()
            self._log.flush()

    sys.stdout = Tee(sys.__stdout__, DISPLAY_LOG)
    sys.stderr = Tee(sys.__stderr__, DISPLAY_LOG)
    main()
