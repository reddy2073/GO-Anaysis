# LegalDebateAI — Data Ingestion Status

> Last updated: **2026-04-18 08:38:49** (America/Chicago)

## Services

| Service | Status |
|---|---|
| Scraper Pipeline | RUNNING |
| API Server (port 8000) | STOPPED |

## Overall Progress

```
   25.3%  [#######-----------------------]
    8,764 / 34,700 chunks
  +992 chunks since last check  |  Est. completion: ~9.3h
```

## Collection Breakdown

| Collection | Chunks | +/- | Target | % Done | ETA | Active |
|---|---:|---:|---:|---:|---:|---|
| Constitution of India | 182 | ~ | 200 | 91.0% `[#############--]` | stalled |  |
| Central Acts (IndiaCode) | 5,565 | +992 | 5,000 | 100.0% `[###############]` | complete | Scraping 63% (314/500) |
| Telangana State Acts | 1,119 | ~ | 2,500 | 44.8% `[######---------]` | stalled |  |
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
