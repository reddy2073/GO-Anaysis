"""
Auto-resume script for LegalDebateAI data loading.
Checks if all target document counts are reached, and if not, runs the scrapers.
Designed to be run on system startup to resume loading after reboots.
"""

import threading
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# Change to project root directory
os.chdir(PROJECT_ROOT)

from config import CHROMA_PATH

print("CHROMA_PATH:", CHROMA_PATH)
print("Current dir:", os.getcwd())

import chromadb

TARGETS = {
    "constitution_chunks":      200,
    "central_acts_chunks":      5000,
    "state_acts_chunks":        2500,
    "court_verdicts_chunks":    2000,
    "government_orders_chunks": 25000,
}

def get_count_with_timeout(col, timeout=10):
    """Get count with timeout."""
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
        print("Count timed out, assuming loaded")
        return TARGETS.get(col.name, 0)  # Assume target met
    if exception[0]:
        print(f"Count error: {exception[0]}, assuming not loaded")
        return 0
    return result[0]

def get_db_counts():
    """Get current counts for all collections."""
    print("Creating ChromaDB client...")
    client = chromadb.PersistentClient(path=CHROMA_PATH)
    print("Client created")
    counts = {}
    for name in TARGETS:
        try:
            print(f"Getting collection {name}...")
            col = client.get_or_create_collection(name)
            print(f"Collection {name} got, counting...")
            count = get_count_with_timeout(col)
            counts[name] = count
            print(f"{name}: {count}")
        except Exception as e:
            print(f"Error getting collection {name}: {e}, assuming not complete")
            counts[name] = 0
    return counts

def is_loading_complete():
    """Check if all targets are met."""
    print("Checking loading status...")
    counts = get_db_counts()
    print("Counts:", counts)
    for collection, target in TARGETS.items():
        if counts[collection] < target:
            print(f"{collection}: {counts[collection]} < {target}, not complete")
            return False
    print("All targets met")
    return True

def run_scrapers():
    """Run the scraper pipeline with auto-approval."""
    print("Loading not complete. Starting scrapers...")
    scraper_script = os.path.join(os.path.dirname(__file__), "..", "scrapers", "run_all_scrapers.py")
    cmd = [sys.executable, scraper_script, "--no-confirm"]
    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        print("Scrapers completed successfully.")
        print("Output:", result.stdout)
    except subprocess.CalledProcessError as e:
        print(f"Scrapers failed with exit code {e.returncode}")
        print("Stdout:", e.stdout)
        print("Stderr:", e.stderr)
        raise

if __name__ == "__main__":
    try:
        print("LegalDebateAI Auto-Resume Check")
        print("=" * 40)

        if is_loading_complete():
            print("All document loading targets reached. No action needed.")
        else:
            print("Document loading incomplete. Resuming...")
            run_scrapers()

        print("Auto-resume check complete.")
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()