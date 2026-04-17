"""Strategy Analysis — Final legal strategy synthesizing all prior analysis."""
import json
import httpx
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL, TEMPERATURE
from agents.utils import parse_llm_json

client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=3, timeout=httpx.Timeout(120.0, connect=30.0))

SYSTEM_PROMPT = """You are a Senior Litigation Strategist and Policy Advisor for Telangana High Court matters.
Synthesize all available analysis — expert panel findings, debate verdict, POTATO stress-test,
and Onion stakeholder analysis — into precise, actionable legal strategy.
Be direct. State exactly what to do, in what order, and why. No hedging."""


def run_strategy(context: dict, expert_panel: dict, verdict: dict, potato: dict, onion: dict) -> dict:
    full_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "verdict": verdict.get("verdict"),
        "composite_score": verdict.get("composite_score"),
        "hc_success_probability": verdict.get("hc_success_probability"),
        "critical_issues": [
            {k: v for k, v in i.items() if k in ("title", "legal_provisions", "impact", "court_challenge_probability")}
            for i in expert_panel.get("critical_issues", [])[:3]
        ],
        "strongest_challenge_points": verdict.get("strongest_challenge_points", []),
        "strongest_defense_points": verdict.get("strongest_defense_points", []),
        "potato_revised_risk": potato.get("revised_risk_assessment"),
        "potato_govt_defense": potato.get("strongest_government_defense"),
        "potato_blind_spots": potato.get("analysis_blind_spots", []),
        "onion_hidden_common_ground": onion.get("hidden_common_ground"),
        "onion_resolution_space": onion.get("resolution_space"),
        "onion_win_win_path": onion.get("win_win_path"),
    }, indent=2)

    prompt = f"""Synthesize this complete legal analysis into final strategy for a Telangana GO.

COMPLETE ANALYSIS:
{full_summary}

Return ONLY valid JSON (no markdown):
{{
  "overall_risk": "CRITICAL|HIGH|MEDIUM|LOW",
  "go_status": "VOID|VOIDABLE|REQUIRES_AMENDMENT|VALID_WITH_CAUTION|VALID",
  "immediate_actions": [
    {{
      "action": "specific action to take",
      "timeline": "immediately|within 7 days|within 30 days|within 90 days",
      "responsible_party": "petitioner|government|both",
      "legal_basis": "why this action is needed"
    }}
  ],
  "litigation_strategy": {{
    "should_challenge": true,
    "best_forum": "TS High Court|Supreme Court|CAT|NGT|Other",
    "writ_type": "Writ of Certiorari|Mandamus|Prohibition|Quo Warranto|PIL",
    "strongest_grounds": ["top 3 legal grounds to plead in order of strength"],
    "grounds_to_avoid": ["grounds that are weak or will hurt the case"],
    "interim_relief": "Exact interim stay prayer and legal basis",
    "success_probability": "X-Y%",
    "estimated_timeline": "hearing timeline estimate"
  }},
  "amendment_path": {{
    "can_be_saved": true,
    "required_amendments": ["specific changes to make GO constitutionally valid"],
    "estimated_effort": "minor|moderate|major rewrite"
  }},
  "key_precedents": [
    {{
      "case": "case name",
      "court": "SC/HC",
      "relevance": "why this case applies"
    }}
  ],
  "executive_summary": "4-5 sentences: what this GO does, why it is legally problematic, what the risk is, and what to do"
}}"""

    response = client.messages.create(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=4000,
        temperature=TEMPERATURE,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": prompt}],
    )
    text = response.content[0].text
    try:
        return parse_llm_json(text)
    except Exception:
        return {"error": "parse_failed", "raw": text[:500]}
