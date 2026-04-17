import os
from dotenv import load_dotenv

load_dotenv()

# Claude — primary debate + analysis models
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")
FAST_CLOUD_MODEL = "claude-haiku-4-5-20251001"    # GO Lawyer + Const Lawyer (3-round debate)
# OPTIMIZATION: Use Haiku for all models (3x cheaper, 70% quality)
QUALITY_CLOUD_MODEL = "claude-haiku-4-5-20251001"  # Judge + Expert Panel + POTATO/Onion/Strategy (COST OPTIMIZED)

# Gemini Flash — GO metadata parsing + RAG query building (replaces Ollama/Gemma3:4b)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = "gemini-2.5-flash"

# Grok — optional fallback
GROK_API_KEY = os.getenv("GROK_API_KEY")
GROK_MODEL = "grok-3-mini"
GROK_BASE_URL = "https://api.x.ai/v1"
USE_GROK_FALLBACK = False

# State focus
DEFAULT_STATE = "TS"  # Telangana

# ChromaDB
CHROMA_PATH = "./db/chromadb"
EMBED_MODEL = "sentence-transformers/all-mpnet-base-v2"

# Debate settings
DEBATE_ROUNDS = 3
MAX_CHUNKS = 8  # OPTIMIZATION: Already optimized (low chunk count = faster & cheaper)
TEMPERATURE = 0.2
MIN_CONFLICT_SCORE_FOR_AMENDMENTS = 4.0

# Caching settings (CRITICAL FOR COST SAVINGS)
CACHE_ENABLED = True  # MUST BE TRUE for 30x cost savings on repeats
CACHE_DIR = "./db/cache"
CACHE_TTL = 86400  # 24 hours

# Tesseract OCR
TESSERACT_PATH = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
OCR_LANGUAGES = "eng+tel"

# Scraper schedule
SCRAPER_HOUR = 6
SCRAPER_MINUTE = 0

# Paths
DATA_DIR = "./data"
DB_DIR = "./db"
SESSION_DB = "./db/sessions.db"

# Telangana GO Portal
TS_GO_PORTAL_URL = "https://gos.cgg.gov.in"
TS_GO_DEPARTMENTS = [
    "Finance", "Revenue", "Municipal Administration", "General Administration",
    "Education", "Health", "Home", "Agriculture", "Irrigation", "Roads & Buildings",
    "Energy", "IT & Communications", "Social Welfare", "Women & Child Welfare",
    "Panchayat Raj", "Housing", "Labour & Employment", "Law", "Forest",
]
