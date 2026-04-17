"""POTATO Analysis — Devil's advocate stress-test of all GO findings."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL
from agents.utils import parse_llm_json

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a Devil's Advocate and Logical Red Team analyst for legal analysis.
Your mandate: challenge every finding, expose weak reasoning, find what was missed,
and present the strongest possible counter-arguments.
Stop yes-pointing. Start counter-pointing. Be brutal, precise, and constructive.
You serve the analysis — not the petitioner or the government."""


def run_potato(context: dict, expert_panel: dict, verdict: dict) -> dict:
    findings_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "go_text_snippet": context.get("go_text", "")[:500],
        "consolidated_issues": [
            {k: v for k, v in i.items() if k in ("title", "description", "legal_provisions", "court_challenge_probability")}
            for i in expert_panel.get("consolidated_issues", [])[:6]
        ],
        "verdict": verdict.get("verdict"),
        "composite_score": verdict.get("composite_score"),
        "conflicts": verdict.get("conflicts", [])[:5],
        "recommendation": verdict.get("recommendation"),
        "strongest_defense_points": verdict.get("strongest_defense_points", []),
    }, indent=2)

    prompt = f"""These are findings from an AI legal analysis of a Telangana Government Order.
Your job: challenge everything.

FINDINGS:
{findings_summary}

Return ONLY valid JSON (no markdown):
{{
  "challenged_findings": [
    {{
      "original_finding": "what was claimed",
      "challenge": "why this may be wrong, overstated, or legally weak",
      "strength_of_challenge": "STRONG|MODERATE|WEAK",
      "what_was_missed": "what the analysis failed to consider"
    }}
  ],
  "overlooked_issues": ["critical issues the panel completely missed"],
  "overblown_issues": ["issues less serious than claimed — with reason"],
  "strongest_government_defense": "The single strongest legal argument IN FAVOR of this GO",
  "analysis_blind_spots": ["systemic gaps in the analytical approach"],
  "assumption_failures": ["assumptions made in the analysis that may not hold"],
  "revised_risk_assessment": "CRITICAL|HIGH|MEDIUM|LOW",
  "revised_risk_rationale": "one sentence explaining the revised assessment"
}}"""

    response = client.messages.create(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=3000,
        temperature=0.4,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    try:
        return parse_llm_json(text)
    except Exception:
        return {"error": "parse_failed", "raw": text[:500]}
