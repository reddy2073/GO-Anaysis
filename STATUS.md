# LegalDebateAI — Data Ingestion Status

> Last updated: **2026-04-18 18:00:11** (America/Chicago)

## Services

| Service | Status |
|---|---|
| Scraper Pipeline | RUNNING |
| API Server (port 8000) | RUNNING |

## Overall Progress

```
   86.3%  [#########################-----]
   29,934 / 34,700 chunks
  +0 chunks since last check  |  Est. completion: stalled
```

## Collection Breakdown

| Collection | Chunks | +/- | Target | % Done | ETA | Active |
|---|---:|---:|---:|---:|---:|---|
| Constitution of India | 182 | ~ | 200 | 91.0% `[#############--]` | stalled |  |
| Central Acts (IndiaCode) | 8,934 | ~ | 5,000 | 100.0% `[###############]` | complete | Scraping 63% (314/500) |
| Telangana State Acts | 2,705 | ~ | 2,500 | 100.0% `[###############]` | complete | Complete |
| Court Verdicts (HuggingFace) | 16,527 | ~ | 2,000 | 100.0% `[###############]` | complete | Complete |
| Telangana GOs 2025 | 1,586 | ~ | 25,000 | 6.3% `[---------------]` | stalled |  |

## Notes

- **Biggest gap:** Telangana GOs 2025 needs 23,414 more chunks

## Targets Reference

| Collection | Target Items | Est. Chunks/Item | Target Chunks |
|---|---:|---:|---:|
| Constitution of India | 1 doc | ~200 | 200 |
| Central Acts (IndiaCode) | 500 acts | ~10 | 5,000 |
| Telangana State Acts | 300 acts | ~8 | 2,500 |
| Court Verdicts (HuggingFace) | 400 files | ~5 | 2,000 |
| Telangana GOs 2025 | 2,500 GOs | ~10 | 25,000 |

---
*Auto-generated hourly by `scripts/check_db_status.py`*
