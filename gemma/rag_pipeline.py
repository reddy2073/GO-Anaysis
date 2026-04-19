"""RAG pipeline — searches ChromaDB, builds context JSON for debate agents.
   GO parsing: tries Gemini Flash first, falls back to Claude Haiku if unavailable.
"""
import json
import re
import chromadb
from sentence_transformers import SentenceTransformer
from config import GEMINI_API_KEY, GEMINI_MODEL, ANTHROPIC_API_KEY, FAST_CLOUD_MODEL, CHROMA_PATH, EMBED_MODEL, MAX_CHUNKS, TEMPERATURE

_client = None
_embedder = None
_gemini_client = None
_USE_GEMINI = False
_anthropic = None

try:
    from google import genai as _google_genai
    if GEMINI_API_KEY:
        _gemini_client = _google_genai.Client(api_key=GEMINI_API_KEY)
        _USE_GEMINI = True
except Exception:
    _USE_GEMINI = False


def _get_client():
    global _client
    if _client is None:
        try:
            _client = chromadb.PersistentClient(path=CHROMA_PATH)
        except Exception as e:
            print(f"      Warning: ChromaDB unavailable ({e.__class__.__name__})")
            _client = None
    return _client


def _get_embedder():
    global _embedder
    if _embedder is None:
        try:
            _embedder = SentenceTransformer(EMBED_MODEL)
        except Exception as e:
            print(f"      Warning: Embedder unavailable ({e.__class__.__name__})")
            _embedder = None
    return _embedder


def _get_anthropic():
    global _anthropic
    if _anthropic is None:
        if not ANTHROPIC_API_KEY:
            return None
        try:
            from anthropic import Anthropic as _Anthropic
            _anthropic = _Anthropic(api_key=ANTHROPIC_API_KEY)
        except Exception as e:
            print(f"      Warning: Anthropic unavailable ({e.__class__.__name__})")
            _anthropic = None
    return _anthropic

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


def _embed(text: str) -> list[float] | None:
    embedder = _get_embedder()
    if embedder is None:
        return None
    try:
        embeddings = embedder.encode(text)
        return embeddings.tolist() if hasattr(embeddings, "tolist") else list(embeddings)
    except Exception as e:
        print(f"      Warning: embedding failed ({e.__class__.__name__})")
        return None


def search_collection(collection_name: str, query: str, n: int = MAX_CHUNKS) -> list[dict]:
    client = _get_client()
    if client is None:
        return []

    try:
        col = client.get_or_create_collection(collection_name)
    except Exception as e:
        print(f"      Warning: cannot access collection {collection_name} ({e.__class__.__name__})")
        return []

    if col.count() == 0:
        return []

    query_embedding = _embed(query)
    if query_embedding is None:
        return []

    try:
        results = col.query(query_embeddings=[query_embedding], n_results=min(n, col.count()))
    except Exception as e:
        print(f"      Warning: ChromaDB query failed ({e.__class__.__name__})")
        return []

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


def _local_parse_go(go_text: str) -> dict:
    lines = [line.strip() for line in go_text.splitlines() if line.strip()]
    go_number = None
    department = None
    date_issued = None
    subject = None
    key_provisions = []
    referenced_laws = []
    affected_parties = []
    go_type = "Other"

    for line in lines:
        if not go_number:
            m = re.search(r"G\.O\.Ms?\.No\.?\s*[:\.]?\s*([^,\s]+)", line, re.I)
            if m:
                go_number = m.group(1).strip()
        if not date_issued:
            m = re.search(r"Dated\s*[:\-]?\s*([0-9]{1,2}[-/][0-9]{1,2}[-/][0-9]{2,4})", line, re.I)
            if m:
                date_issued = m.group(1).strip()
        if not department and "Department" in line:
            department = line
        if not subject:
            m = re.search(r"SUBJECT\s*[:\-]?\s*(.+)", line, re.I)
            if m:
                subject = m.group(1).strip()

    if not department and len(lines) > 1:
        department = lines[1]
    if not subject and lines:
        for line in lines:
            if line.lower().startswith("subject"):
                subject = re.sub(r"(?i)^subject\s*[:\-]?\s*", "", line).strip()
                break
    if not subject:
        subject = lines[-1] if lines else go_text[:100]

    if subject:
        subject_lower = subject.lower()
        if any(k in subject_lower for k in ["finance", "pay", "salary", "pay scale", "arrear"]):
            go_type = "Financial"
        elif any(k in subject_lower for k in ["appointment", "transfer", "posting", "promotion"]):
            go_type = "Service"
        elif any(k in subject_lower for k in ["land", "acquisition", "property"]):
            go_type = "Land"
        elif any(k in subject_lower for k in ["education", "school", "college", "university"]):
            go_type = "Policy"

    if subject:
        key_provisions.append(subject)
    for line in lines[:4]:
        if line and line not in key_provisions:
            key_provisions.append(line)
        if len(key_provisions) >= 5:
            break

    referenced_laws.extend(re.findall(r"\bArticle\s*\d+[A-Za-z]?\b", go_text, re.I))
    referenced_laws.extend(re.findall(r"\b[A-Z][a-z]+ Act\b", go_text))
    referenced_laws = list(dict.fromkeys(referenced_laws))

    if re.search(r"employee|employees|service", go_text, re.I):
        affected_parties.append("Government employees")
    if re.search(r"citizen|public|resident", go_text, re.I):
        affected_parties.append("Citizens")
    if not affected_parties:
        affected_parties.append("State Government employees")

    return {
        "go_number": go_number,
        "department": department or "Unknown",
        "state": "TS",
        "subject": subject,
        "key_provisions": key_provisions,
        "referenced_laws": referenced_laws,
        "affected_parties": affected_parties,
        "go_type": go_type,
        "date_issued": date_issued,
    }


def parse_go(go_text: str) -> dict:
    """Parse GO metadata — Gemini Flash first, Claude Haiku fallback."""
    prompt = GO_PARSE_PROMPT.format(go_text=go_text[:3000])
    fallback = _local_parse_go(go_text)

    if _USE_GEMINI and _gemini_client is not None:
        try:
            resp = _gemini_client.models.generate_content(
                model=GEMINI_MODEL,
                contents=prompt,
            )
            return _parse_json(resp.text)
        except Exception as e:
            print(f"      Gemini unavailable ({e.__class__.__name__}), using Claude Haiku fallback...")

    anthropic_client = _get_anthropic()
    if anthropic_client is not None:
        try:
            resp = anthropic_client.messages.create(
                model=FAST_CLOUD_MODEL,
                max_tokens=600,
                temperature=0.1,
                messages=[{"role": "user", "content": prompt}],
            )
            return _parse_json(resp.content[0].text)
        except Exception as e:
            print(f"      Anthropic unavailable ({e.__class__.__name__}), using local text parser...")

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
