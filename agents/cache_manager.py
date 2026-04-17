"""Cache manager for expert panel analysis — avoids re-analyzing duplicate GOs."""
import json
import hashlib
from pathlib import Path
from datetime import datetime


CACHE_DIR = Path("./db/cache")
EXPERT_CACHE_FILE = CACHE_DIR / "expert_panel_cache.json"


def _ensure_cache_dir():
    """Create cache directory if it doesn't exist."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def _generate_cache_key(context: dict) -> str:
    """
    Generate a unique cache key from GO metadata.
    Uses GO number + department + date to identify unique GOs.
    """
    meta = context.get("go_metadata", {})
    key_parts = [
        str(meta.get("go_number", "unknown")).strip(),
        str(meta.get("department", "unknown")).strip(),
        str(meta.get("go_date", "unknown")).strip(),
    ]
    key_string = "|".join(key_parts).lower()
    # Return first part of GO number as readable key, with hash for uniqueness
    go_number = str(meta.get("go_number", "unknown")).strip()
    hash_suffix = hashlib.md5(key_string.encode()).hexdigest()[:8]
    return f"{go_number}_{hash_suffix}"


def _load_cache() -> dict:
    """Load cache from disk."""
    _ensure_cache_dir()
    if EXPERT_CACHE_FILE.exists():
        try:
            with open(EXPERT_CACHE_FILE, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {}
    return {}


def _save_cache(cache: dict):
    """Save cache to disk."""
    _ensure_cache_dir()
    with open(EXPERT_CACHE_FILE, 'w') as f:
        json.dump(cache, f, indent=2)


def get_cached_analysis(context: dict) -> dict | None:
    """
    Check if expert panel analysis exists in cache.
    Returns cached analysis if found, None otherwise.
    """
    cache_key = _generate_cache_key(context)
    cache = _load_cache()
    
    if cache_key in cache:
        cached_entry = cache[cache_key]
        return cached_entry.get("analysis")
    
    return None


def cache_analysis(context: dict, analysis: dict):
    """
    Store expert panel analysis in cache.
    """
    cache_key = _generate_cache_key(context)
    meta = context.get("go_metadata", {})
    
    cache = _load_cache()
    cache[cache_key] = {
        "go_number": meta.get("go_number"),
        "department": meta.get("department"),
        "go_date": meta.get("go_date"),
        "cached_at": datetime.now().isoformat(),
        "analysis": analysis,
    }
    _save_cache(cache)


def clear_cache():
    """Clear entire cache."""
    _ensure_cache_dir()
    if EXPERT_CACHE_FILE.exists():
        EXPERT_CACHE_FILE.unlink()


def get_cache_stats() -> dict:
    """Get cache statistics."""
    cache = _load_cache()
    return {
        "total_cached_analyses": len(cache),
        "cache_file": str(EXPERT_CACHE_FILE),
        "cache_entries": [
            {
                "go_number": entry.get("go_number"),
                "department": entry.get("department"),
                "cached_at": entry.get("cached_at"),
            }
            for entry in cache.values()
        ]
    }
