# LegalDebateAI — Data Ingestion Status

> Last updated: **2026-04-18 10:23:39** (America/Chicago)

## Services

| Service | Status |
|---|---|
| Scraper Pipeline | RUNNING |
| API Server (port 8000) | STOPPED |

## Overall Progress

```
   39.2%  [###########-------------------]
   13,586 / 34,700 chunks
  +1,109 chunks since last check  |  Est. completion: ~7.5h
```

## Collection Breakdown

| Collection | Chunks | +/- | Target | % Done | ETA | Active |
|---|---:|---:|---:|---:|---:|---|
| Constitution of India | 182 | ~ | 200 | 91.0% `[#############--]` | stalled |  |
| Central Acts (IndiaCode) | 8,933 | ~ | 5,000 | 100.0% `[###############]` | complete | Scraping 63% (314/500) |
| Telangana State Acts | 2,573 | +1,109 | 2,500 | 100.0% `[###############]` | complete | Complete |
| Court Verdicts (HuggingFace) | 312 | ~ | 2,000 | 15.6% `[##-------------]` | stalled |  |
| Telangana GOs 2025 | 1,586 | ~ | 25,000 | 6.3% `[---------------]` | stalled |  |

## Notes

- **Biggest gap:** Telangana GOs 2025 needs 23,414 more chunks
- **API server is down** — restart with `uvicorn api:app --port 8000`

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
