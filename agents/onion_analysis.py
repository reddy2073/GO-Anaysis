"""Onion Analysis — Conflict PIN model: Positions → Interests → Needs for each stakeholder."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL, TEMPERATURE
from agents.utils import parse_llm_json

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a conflict resolution and policy analysis expert applying the Conflict Onion (PIN) model.
The Onion model peels back layers of a dispute:
- POSITIONS (outer): What each party publicly states they want
- INTERESTS (middle): What they actually want to achieve — underlying motivations
- NEEDS (core): What they fundamentally must have — non-negotiable
Revealing true needs uncovers hidden common ground and paths to resolution."""


def run_onion(context: dict, expert_panel: dict, verdict: dict) -> dict:
    go_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "go_text_snippet": context.get("go_text", "")[:600],
        "consolidated_issues": [
            {k: v for k, v in i.items() if k in ("title", "impact")}
            for i in expert_panel.get("consolidated_issues", [])[:4]
        ],
        "verdict": verdict.get("verdict"),
        "conflicts": verdict.get("conflicts", [])[:4],
    }, indent=2)

    prompt = f"""Apply the Conflict Onion (PIN) model to this Telangana Government Order.

GO ANALYSIS:
{go_summary}

Identify all key stakeholder parties. For each, peel back the onion layers.
Return ONLY valid JSON (no markdown):
{{
  "stakeholders": [
    {{
      "party": "e.g. State Government / Affected Employees / Citizens / Opposition",
      "position": "What they publicly state they want regarding this GO",
      "interests": ["What they actually want to achieve", "underlying motivations"],
      "needs": ["Non-negotiable fundamental needs that must be satisfied"],
      "common_ground_with_others": "Where their core needs overlap with other parties"
    }}
  ],
  "core_conflict": "The fundamental tension this GO creates at the needs level",
  "hidden_common_ground": "Where all parties' underlying needs actually align",
  "resolution_space": "What a solution acceptable to all parties would look like",
  "win_win_path": "Specific GO amendment or policy change that satisfies all core needs"
}}"""

    response = client.messages.create(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=3000,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    try:
        return parse_llm_json(text)
    except Exception:
        return {"error": "parse_failed", "raw": text[:500]}
