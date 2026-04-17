"""RAG pipeline — searches ChromaDB, builds context JSON for debate agents.
   GO parsing: tries Gemini Flash first, falls back to Claude Haiku if unavailable.
"""
import json
import chromadb
from sentence_transformers import SentenceTransformer
from config import GEMINI_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, FAST_CLOUD_MODEL, CHROMA_PATH, EMBED_MODEL, MAX_CHUNKS, TEMPERATURE

_client = chromadb.PersistentClient(path=CHROMA_PATH)
_embedder = SentenceTransformer(EMBED_MODEL)

# Gemini client (new SDK)
try:
    from google import genai as _google_genai
    _gemini_client = _google_genai.Client(api_key=GEMINI_API_KEY)
    _USE_GEMINI = True
except Exception:
    _USE_GEMINI = False

# Anthropic fallback
from anthropic import Anthropic as _Anthropic
_anthropic = _Anthropic(api_key=ANTHROPIC_API_KEY)

GO_PARSE_PROMPT = """Extract the following from this Telangana Government Order and return ONLY valid JSON with no markdown:
{{
  "go_number": "GO number if present, else null",
  "department": "issuing department",
  "state": "TS",
  "subject": "one-line subject",
  "key_provisions": ["list of 3-5 key provisions"],
  "referenced_laws": ["any Acts or Articles explicitly mentioned"],
  "affected_parties": ["who is directly affected by this GO"],
  "go_type": "Policy|Transfer|Appointment|Financial|Land|Service|Other",
  "date_issued": "date if present else null"
}}

GO Text:
{go_text}"""


def _embed(text: str) -> list[float]:
    return _embedder.encode(text).tolist()


def search_collection(collection_name: str, query: str, n: int = MAX_CHUNKS) -> list[dict]:
    col = _client.get_or_create_collection(collection_name)
    if col.count() == 0:
        return []
    results = col.query(query_embeddings=[_embed(query)], n_results=min(n, col.count()))
    chunks = []
    for i, doc in enumerate(results["documents"][0]):
        meta = results["metadatas"][0][i] if results["metadatas"] else {}
        dist = results["distances"][0][i] if results["distances"] else 1.0
        chunks.append({"text": doc, "metadata": meta, "relevance": round(1 - dist, 3)})
    return chunks


def _parse_json(text: str) -> dict:
    start = text.find("{")
    end = text.rfind("}") + 1
    return json.loads(text[start:end])


def parse_go(go_text: str) -> dict:
    """Parse GO metadata — Gemini Flash first, Claude Haiku fallback."""
    prompt = GO_PARSE_PROMPT.format(go_text=go_text[:3000])
    fallback = {
        "go_number": None, "department": "Unknown", "state": "TS",
        "subject": go_text[:100], "key_provisions": [], "referenced_laws": [],
        "affected_parties": [], "go_type": "Other", "date_issued": None,
    }

    if _USE_GEMINI:
        try:
            resp = _gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return _parse_json(resp.text)
        except Exception as e:
            print(f"      Gemini unavailable ({e.__class__.__name__}), using Claude Haiku fallback...")

    # Claude Haiku fallback
    try:
        resp = _anthropic.messages.create(
            model=FAST_CLOUD_MODEL,
            max_tokens=600,
            temperature=0.1,
            messages=[{"role": "user", "content": prompt}],
        )
        return _parse_json(resp.content[0].text)
    except Exception:
        return fallback


def build_context(go_text: str) -> dict:
    """Full pipeline: parse GO → search all 5 ChromaDB collections → return context."""
    go_meta = parse_go(go_text)
    query = f"{go_meta.get('subject', '')} {' '.join(go_meta.get('key_provisions', []))}"

    return {
        "go_metadata": go_meta,
        "go_text": go_text[:2000],
        "related_articles":  search_collection("constitution_chunks", query, 4),
        "related_acts":      search_collection("central_acts_chunks", query, 4),
        "state_laws":        search_collection("state_acts_chunks", query, 3),
        "similar_gos":       search_collection("government_orders_chunks", query, 3),
        "relevant_verdicts": search_collection("court_verdicts_chunks", query, 4),
    }
