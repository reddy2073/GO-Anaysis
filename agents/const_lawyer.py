"""Constitution Lawyer Agent — challenges the GO using Claude Haiku."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, FAST_CLOUD_MODEL, TEMPERATURE

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a Senior Advocate challenging a Government Order as unconstitutional.
Your mandate: find EVERY constitutional flaw, statutory conflict, and precedent against this GO.
Rules:
- Cite exact Article/Section numbers
- Always distinguish: is this SC binding precedent or HC persuasive precedent?
- Always state jurisdiction: "binding in AP/TS" or "persuasive only"
- Acknowledge ONE strongest defense argument before rebutting it
- Focus on: Art 13 (void laws), Art 14 (equality), Art 21 (livelihood), Art 254 (repugnancy)
- Keep each round to 250-300 words"""


def argue(context: dict, round_num: int, opponent_last_argument: str = "") -> str:
    context_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "related_articles": [c["text"][:200] for c in context.get("related_articles", [])[:3]],
        "related_acts": [c["text"][:200] for c in context.get("related_acts", [])[:3]],
        "relevant_verdicts": [c["text"][:150] for c in context.get("relevant_verdicts", [])[:3]],
    }, indent=2)

    if round_num == 1:
        user_msg = f"LEGAL CONTEXT:\n{context_summary}\n\nGO TEXT:\n{context['go_text'][:1000]}\n\nDeliver your Round 1 CONSTITUTIONAL CHALLENGE against this GO."
    elif round_num == 2:
        user_msg = f"LEGAL CONTEXT:\n{context_summary}\n\nOPPONENT'S ROUND 1 DEFENSE:\n{opponent_last_argument}\n\nDeliver your Round 2 COUNTER-ARGUMENT. Acknowledge their strongest point, then dismantle it."
    else:
        user_msg = f"OPPONENT'S ROUND 2 DEFENSE:\n{opponent_last_argument}\n\nDeliver your Round 3 CLOSING ARGUMENT. State your 2 strongest constitutional grounds."

    response = client.messages.create(
        model=FAST_CLOUD_MODEL,
        max_tokens=500,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_msg}],
    )
    return response.content[0].text
