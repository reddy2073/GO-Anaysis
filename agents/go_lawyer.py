"""GO Lawyer Agent — defends the Government Order using Claude Haiku."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, FAST_CLOUD_MODEL, TEMPERATURE

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a Senior Advocate defending a Government Order in court.
Your mandate: build the STRONGEST possible defense for this GO.
Rules:
- Cite exact Article/Section numbers, not just Act names
- Distinguish between binding SC precedent and persuasive HC precedent
- Acknowledge ONE strongest opposing argument before rebutting it (shows credibility)
- Use precise legal language: repugnancy, occupied field, delegated legislation, etc.
- Keep each round to 250-300 words"""


def argue(context: dict, round_num: int, opponent_last_argument: str = "") -> str:
    context_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "related_articles": [c["text"][:200] for c in context.get("related_articles", [])[:3]],
        "related_acts": [c["text"][:200] for c in context.get("related_acts", [])[:3]],
        "similar_gos": [c["text"][:150] for c in context.get("similar_gos", [])[:2]],
        "relevant_verdicts": [c["text"][:150] for c in context.get("relevant_verdicts", [])[:2]],
    }, indent=2)

    if round_num == 1:
        user_msg = f"LEGAL CONTEXT:\n{context_summary}\n\nGO TEXT:\n{context['go_text'][:1000]}\n\nDeliver your Round 1 OPENING DEFENSE for this GO."
    elif round_num == 2:
        user_msg = f"LEGAL CONTEXT:\n{context_summary}\n\nOPPONENT'S ROUND 1 ARGUMENT:\n{opponent_last_argument}\n\nDeliver your Round 2 REBUTTAL. Acknowledge their strongest point, then dismantle it."
    else:
        user_msg = f"OPPONENT'S ROUND 2 ARGUMENT:\n{opponent_last_argument}\n\nDeliver your Round 3 CLOSING ARGUMENT. Identify your 2 strongest points."

    response = client.messages.create(
        model=FAST_CLOUD_MODEL,
        max_tokens=500,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text
