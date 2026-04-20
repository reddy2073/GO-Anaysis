# LegalDebateAI — Data Ingestion Status

> Last updated: **2026-04-20 17:48:57** (America/Chicago)

## Services

| Service | Status |
|---|---|
| Scraper Pipeline | RUNNING |
| API Server (port 8000) | STOPPED |

## Overall Progress

```
    4.4%  [#-----------------------------]
   27,705 / 632,700 chunks
  +547 chunks since last check  |  Est. completion: ~15.8d
```

## Collection Breakdown

| Collection | Chunks | +/- | Target | % Done | ETA | Active |
|---|---:|---:|---:|---:|---:|---|
| Constitution of India | 182 | ~ | 200 | 91.0% `[#############--]` | stalled |  |
| Central Acts (IndiaCode) | 8,936 | ~ | 5,000 | 100.0% `[###############]` | complete | Scraping 63% (314/500) |
| Telangana State Acts | 2,809 | ~ | 2,500 | 100.0% `[###############]` | complete | Complete |
| SC Verdicts (all, no filter) | 5,084 | +238 | 500,000 | 1.0% `[---------------]` | ~29.7d |  |
| HC Verdicts (Telangana-filtered) | 8,556 | +309 | 100,000 | 8.6% `[#--------------]` | ~4.2d |  |
| Telangana GOs 2025 | 2,138 | ~ | 25,000 | 8.6% `[#--------------]` | stalled |  |

## Notes

- **Biggest gap:** SC Verdicts (all, no filter) needs 494,916 more chunks
- **API server is down** — restart with `uvicorn api:app --port 8000`

## Targets Reference

| Collection | Target Items | Est. Chunks/Item | Target Chunks |
|---|---:|---:|---:|
| Constitution of India | 1 doc | ~200 | 200 |
| Central Acts (IndiaCode) | 500 acts | ~10 | 5,000 |
| Telangana State Acts | 300 acts | ~8 | 2,500 |
| SC Verdicts (all, no filter) | 76 parquet | ~6,500 | 500,000 |
| HC Verdicts (Telangana-filtered) | 100 parquet | ~1,000 | 100,000 |
| Telangana GOs 2025 | 2,500 GOs | ~10 | 25,000 |

---
*Auto-generated hourly by `scripts/check_db_status.py`*
