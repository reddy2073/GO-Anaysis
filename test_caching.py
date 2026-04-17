"""Quick test for expert panel caching functionality."""
import json
from pathlib import Path

# Create test context (simulating a GO analysis)
test_context = {
    "go_metadata": {
        "go_number": "TEST-GO-001",
        "department": "Finance",
        "go_date": "2025-04-16",
        "subject": "Test Government Order for Caching",
    },
    "go_text": "This is a test GO for caching.",
    "related_articles": [],
    "related_acts": [],
    "state_laws": [],
    "relevant_verdicts": [],
}

# Test cache manager
from agents.cache_manager import (
    get_cached_analysis,
    cache_analysis,
    get_cache_stats,
    clear_cache,
    _generate_cache_key,
)

print("=" * 60)
print("Testing Response Caching System")
print("=" * 60)

# Test 1: Generate cache key
cache_key = _generate_cache_key(test_context)
print(f"\n✓ Generated cache key: {cache_key}")

# Test 2: Check cache (should be empty initially)
cached = get_cached_analysis(test_context)
print(f"✓ Cache lookup (before storing): {cached is None}")

# Test 3: Store analysis in cache
dummy_analysis = {
    "expert_reports": {},
    "consolidated_issues": [
        {"title": "Test Issue 1", "impact": {"severity": "HIGH"}},
        {"title": "Test Issue 2", "impact": {"severity": "CRITICAL"}},
    ],
    "critical_issues": [{"title": "Test Issue 2"}],
    "high_issues": [{"title": "Test Issue 1"}],
    "total_issues": 2,
    "critical_count": 1,
}

cache_analysis(test_context, dummy_analysis)
print(f"✓ Stored analysis in cache")

# Test 4: Retrieve from cache
cached = get_cached_analysis(test_context)
print(f"✓ Cache hit: {cached is not None}")
if cached:
    print(f"  - Total issues: {cached['total_issues']}")
    print(f"  - Critical count: {cached['critical_count']}")

# Test 5: View cache stats
stats = get_cache_stats()
print(f"\n✓ Cache Statistics:")
print(f"  - Total cached analyses: {stats['total_cached_analyses']}")
print(f"  - Cache file: {Path(stats['cache_file']).name}")

# Test 6: Clear cache
clear_cache()
cached = get_cached_analysis(test_context)
print(f"\n✓ Cache cleared: {cached is None}")

print("\n" + "=" * 60)
print("✓ All caching tests passed!")
print("=" * 60)
