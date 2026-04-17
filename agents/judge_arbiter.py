"""Judge Agent — neutral arbiter that scores the debate and issues conflict analysis."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL, TEMPERATURE
from agents.utils import parse_llm_json

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a neutral Supreme Court judge evaluating a legal debate about a Government Order.
Your task: analyze all arguments and produce a structured conflict analysis.
Be precise, cite Articles and Sections, and give numeric scores based on legal strength of evidence.
Return ONLY valid JSON — no markdown, no explanation outside the JSON object."""


def score_debate(context: dict, debate_transcript: dict) -> dict:
    transcript_text = "\n\n".join([
        f"ROUND {r['round']} — GO LAWYER:\n{r['go_lawyer']}\n\nROUND {r['round']} — CONSTITUTION LAWYER:\n{r['const_lawyer']}"
        for r in debate_transcript["rounds"]
    ])

    prompt = f"""Review this 3-round legal debate about a Telangana Government Order.

GO METADATA:
{json.dumps(context.get('go_metadata'), indent=2)}

DEBATE TRANSCRIPT:
{transcript_text}

Return ONLY valid JSON with this exact structure:
{{
  "conflicts": [
    {{
      "provision": "e.g. Article 254 Repugnancy",
      "score": 8.5,
      "severity": "CRITICAL|HIGH|MEDIUM|LOW|CLEAR",
      "reasoning": "one sentence explaining the score",
      "binding_precedent": true
    }}
  ],
  "composite_score": 7.2,
  "score_range": [6.8, 7.7],
  "verdict": "LIKELY UNCONSTITUTIONAL|LIKELY VALID|REQUIRES AMENDMENT|UNCLEAR",
  "hc_success_probability": "65-80%",
  "strongest_defense_points": ["point 1", "point 2"],
  "strongest_challenge_points": ["point 1", "point 2"],
  "recommendation": "one paragraph with specific action"
}}

Score guide: 8-10=CRITICAL, 6-7=HIGH, 4-5=MEDIUM, 2-3=LOW, 0-1=CLEAR"""

    response = client.messages.create(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=2000,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    try:
        return parse_llm_json(response.content[0].text)
    except Exception:
        return {"error": "Judge failed to parse", "raw": response.content[0].text}
