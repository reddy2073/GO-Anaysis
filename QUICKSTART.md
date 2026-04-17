# Quick Start Guide - LegalDebateAI

Get LegalDebateAI running in 5 minutes.

## Prerequisites
- Python 3.10 or higher
- Anthropic API key (free tier available)

## Installation (5 minutes)

### Step 1: Navigate to project directory
```bash
cd c:\Users\vemul\LegalDebateAI
```

### Step 2: Install dependencies
```bash
pip install -r requirements.txt
```

### Step 3: Set up API key
Create a `.env` file in the project root:
```env
ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```

Or set environment variable:
```bash
# Windows
set ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE

# Linux/Mac
export ANTHROPIC_API_KEY=sk-ant-YOUR-KEY-HERE
```

### Step 4: Verify installation
```bash
python validate_system.py
```

Expected output:
```
✓ Expert Panel (parallel + few-shot)
✓ Cache Manager (0 cached)
✓ Streaming API (real-time responses)
✓ Vision API (PDF analysis)
✓ Advanced Embeddings (6 models available)
✓ Ollama Integration
✓ Fine-tuning Pipeline (5 landmark cases)

ALL MODULES OPERATIONAL - READY FOR DEPLOYMENT
```

### Step 5: Run tests
```bash
python test_scenarios.py
```

Expected output:
```
Results: 12/12 tests passed
Report saved to test_results.json
```

---

## Basic Usage

### Analyze a Government Order

```python
from debate_engine import run_debate

# Sample GO text
go_text = """
Government of Telangana
Office of the Chief Secretary
G.O.Ms.No. 215, Dated: 15-03-2024

SUBJECT: Implementation of Revised Guidelines for Government Employees Conduct

1. No Government employee shall engage in any private business without prior approval.
2. All employees must report by 9:00 AM sharp.
3. Political activism is prohibited during work hours.
"""

# Run analysis
result = run_debate(go_text, verbose=True, use_cache=True)

# View results
print(f"Total Issues: {result['expert_panel']['total_issues']}")
print(f"Critical Issues: {result['expert_panel']['critical_count']}")
print(f"Verdict: {result['verdict']['verdict']}")
print(f"Recommended Actions: {result['strategy']['recommended_actions']}")
```

### Output Structure
```python
{
  "go_metadata": {
    "go_number": "G.O.Ms.No. 215",
    "department": "Office of the Chief Secretary",
    ...
  },
  "expert_panel": {
    "constitutional_expert": {...},
    "admin_law_expert": {...},
    "public_interest_expert": {...},
    "fiscal_expert": {...},
    "total_issues": 7,
    "critical_count": 2
  },
  "debate_transcript": {...},      # 3-round debate
  "verdict": {...},                # Judge's verdict
  "potato_analysis": {...},        # Vulnerabilities
  "onion_analysis": {...},         # Stakeholder impact
  "strategy": {...}                # Recommendations
}
```

---

## Common Operations

### Run with Caching (30x faster!)
```python
result = run_debate(go_text, use_cache=True)
```

### Disable Verbose Output
```python
result = run_debate(go_text, verbose=False)
```

### Batch Process Multiple GOs
```python
from concurrent.futures import ThreadPoolExecutor

gos = [go_text_1, go_text_2, go_text_3]

with ThreadPoolExecutor(max_workers=4) as executor:
    results = list(executor.map(run_debate, gos))
```

### Export Results to JSON
```python
import json

with open('analysis_result.json', 'w') as f:
    json.dump(result, f, indent=2)
```

---

## Troubleshooting

### API Key not found
```bash
# Check if key is set
echo %ANTHROPIC_API_KEY%  # Windows
echo $ANTHROPIC_API_KEY   # Linux/Mac

# Set it (Windows)
setx ANTHROPIC_API_KEY sk-ant-YOUR-KEY
```

### Tests failing
```bash
# Check system
python validate_system.py

# Reinstall dependencies
pip install -r requirements.txt --upgrade

# Reinitialize database
python setup_db.py
```

### Slow performance
1. Enable caching: `use_cache=True`
2. Use Haiku model instead of Sonnet (faster, less accurate)
3. Reduce `MAX_CHUNKS` in config.py
4. Install Ollama for local inference

### Out of memory
- Reduce `MAX_CHUNKS` in config.py
- Process one GO at a time
- Reduce batch size

---

## Next Steps

### Explore the System
- Read [README.md](README.md) for full documentation
- Check [TEST_DOCUMENTATION.md](TEST_DOCUMENTATION.md) for test details
- Review [CONTRIBUTING.md](CONTRIBUTING.md) for development guidelines

### Deploy to Production
1. Set up remote git repository
2. Configure GitHub Actions (already in `.github/workflows/`)
3. Deploy API using FastAPI server
4. Set up monitoring and logging

### Customize the System
1. Add new agents in `agents/` directory
2. Modify prompts in agent files
3. Add new test scenarios
4. Extend RAG database with more documents

---

## Key Features

### 7-Step Analysis Pipeline
1. RAG Context - Document retrieval
2. Expert Panel - 4 parallel experts
3-4. Debate & Judge - 3-round debate with scoring
5. POTATO - Vulnerability detection
6. Onion - Stakeholder analysis
7. Strategy - Recommendations

### Performance
- **Cache Speedup**: 30x faster on repeats
- **Parallel Execution**: 4 experts simultaneously
- **Token Optimization**: Few-shot prompting
- **Multi-Model Fallback**: 5-model cascade

### Reliability
- 12/12 tests passing
- Error handling with fallbacks
- Graceful degradation
- Comprehensive logging

---

## Configuration

Edit `config.py` to customize:

```python
# API Keys
ANTHROPIC_API_KEY = "sk-ant-..."      # Required
OPENAI_API_KEY = "sk-..."              # Optional
GOOGLE_API_KEY = "AIza..."             # Optional

# Model Selection
QUALITY_CLOUD_MODEL = "claude-sonnet-4-6"
FAST_CLOUD_MODEL = "claude-haiku-3-5"

# Parameters
TEMPERATURE = 0.2                       # 0=deterministic, 1=creative
MIN_CONFLICT_SCORE_FOR_AMENDMENTS = 4.0

# Cache
CACHE_ENABLED = True
CACHE_DIR = "./db/cache"

# Embedding
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"

# Database
CHROMA_PATH = "./db/chromadb"
```

---

## Support & Resources

| Resource | Location |
|----------|----------|
| Main Guide | [README.md](README.md) |
| Tests | [TEST_DOCUMENTATION.md](TEST_DOCUMENTATION.md) |
| Development | [CONTRIBUTING.md](CONTRIBUTING.md) |
| Version History | [CHANGELOG.md](CHANGELOG.md) |
| Configuration | [config.py](config.py) |

---

## Getting Help

1. **Check documentation**: README.md, TEST_DOCUMENTATION.md
2. **Run validation**: `python validate_system.py`
3. **Run tests**: `python test_scenarios.py`
4. **Check logs**: Look for error messages in output
5. **Review configuration**: Verify config.py settings

---

## Performance Tips

### For Speed
- Enable caching: `use_cache=True`
- Use Haiku model for debates
- Reduce `MAX_CHUNKS` in config

### For Quality
- Use Sonnet model
- Increase `TEMPERATURE` to 0.5-0.7
- Increase `MAX_CHUNKS` for more context

### For Cost
- Enable caching (30x faster = 30x cheaper)
- Use fallback to Haiku
- Batch process to reduce API calls

---

## What's Next?

1. ✅ **Install & Run** (this guide)
2. 📖 **Read Documentation** (README.md)
3. 🧪 **Review Tests** (TEST_DOCUMENTATION.md)
4. 🔧 **Configure** (config.py)
5. 🚀 **Deploy** (GitHub/Cloud)

---

**Ready to analyze Government Orders?** 🚀

```bash
python test_scenarios.py  # Verify everything works
# Then run your own analysis!
```

Happy analyzing! 📋✨
