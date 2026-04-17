"""Streaming response handler for real-time feedback during analysis."""
import json
from anthropic import Anthropic
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL, TEMPERATURE

client = Anthropic(api_key=ANTHROPIC_API_KEY)


def stream_expert_analysis(expert: dict, context: dict, callback=None) -> dict:
    """
    Stream expert analysis response in real-time with callback for each chunk.
    
    Args:
        expert: Expert definition dict with id, name, and system prompt
        context: RAG context with GO metadata and documents
        callback: Optional function(chunk_text) called for each streamed chunk
    
    Returns:
        Parsed expert analysis result
    """
    import json as json_module
    from agents.utils import parse_llm_json
    
    go_summary = json_module.dumps({
        "go_metadata": context.get("go_metadata"),
        "go_text": context.get("go_text", "")[:1500],
        "related_articles": [c["text"][:200] for c in context.get("related_articles", [])[:3]],
        "related_acts": [c["text"][:200] for c in context.get("related_acts", [])[:3]],
        "state_laws": [c["text"][:200] for c in context.get("state_laws", [])[:3]],
        "relevant_verdicts": [c["text"][:150] for c in context.get("relevant_verdicts", [])[:2]],
    }, indent=2)
    
    ISSUE_SCHEMA = """{
  "issues": [
    {
      "issue_id": "X1",
      "title": "Brief issue title",
      "description": "Detailed description",
      "legal_provisions": ["Article 14"],
      "impact": {
        "affected_parties": ["list"],
        "severity": "CRITICAL|HIGH|MEDIUM|LOW",
        "immediate_impact": "...",
        "long_term_impact": "...",
        "reversibility": "IRREVERSIBLE|DIFFICULT|POSSIBLE|EASY",
        "estimated_affected_count": null
      },
      "court_challenge_probability": "HIGH|MEDIUM|LOW",
      "suggested_remedy": "..."
    }
  ],
  "critical_count": 0,
  "summary": "One paragraph assessment"
}"""
    
    prompt = f"""Analyze this Telangana Government Order strictly from your expert domain.

CONTEXT:
{go_summary}

Return ONLY valid JSON in this exact structure (no markdown, no explanation):
{ISSUE_SCHEMA}

Be specific: cite exact laws, estimate real-world impact numbers, give actionable remedies."""
    
    # Stream the response
    full_text = ""
    with client.messages.stream(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=4000,
        temperature=TEMPERATURE,
        system=expert["system"],
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            if callback:
                callback(text)
    
    # Parse the full accumulated response
    try:
        result = parse_llm_json(full_text)
        result["expert"] = expert["name"]
        result["expert_id"] = expert["id"]
        return result
    except Exception as e:
        return {
            "expert": expert["name"],
            "expert_id": expert["id"],
            "issues": [],
            "critical_count": 0,
            "summary": full_text[:500],
            "error": f"parse_failed: {str(e)[:50]}",
        }


def stream_debate_response(lawyer_type: str, system_prompt: str, user_prompt: str, 
                          callback=None) -> str:
    """
    Stream debate argument in real-time.
    
    Args:
        lawyer_type: "go_lawyer" or "const_lawyer"
        system_prompt: System prompt for the lawyer
        user_prompt: The debate prompt
        callback: Optional function(chunk_text) called for each streamed chunk
    
    Returns:
        Full accumulated argument text
    """
    full_text = ""
    with client.messages.stream(
        model="claude-haiku-4-5-20251001",
        max_tokens=2000,
        temperature=TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": user_prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            if callback:
                callback(text)
    
    return full_text


def stream_judge_verdict(context: dict, transcript: dict, callback=None) -> dict:
    """
    Stream judge verdict in real-time.
    
    Args:
        context: RAG context
        transcript: Debate transcript
        callback: Optional function(chunk_text) called for streamed chunk
    
    Returns:
        Parsed verdict JSON
    """
    import json as json_module
    from agents.utils import parse_llm_json
    
    system_prompt = """You are the Supreme Court judge presiding over this constitutional debate.
Score the arguments on legal merit, precedent application, reasoning quality.
Render a neutral verdict with conflict analysis."""
    
    transcript_json = json_module.dumps(transcript, indent=2)[:2000]
    
    prompt = f"""Score this debate:
{transcript_json}

Return ONLY valid JSON with: verdict, composite_score (0-10), hc_success_probability (%), 
conflict_analysis, key_legal_points."""
    
    full_text = ""
    with client.messages.stream(
        model=QUALITY_CLOUD_MODEL,
        max_tokens=3000,
        temperature=TEMPERATURE,
        system=system_prompt,
        messages=[{"role": "user", "content": prompt}],
    ) as stream:
        for text in stream.text_stream:
            full_text += text
            if callback:
                callback(text)
    
    try:
        result = parse_llm_json(full_text)
        return result
    except Exception:
        return {
            "verdict": "INDETERMINATE",
            "composite_score": 5,
            "hc_success_probability": 50,
            "conflict_analysis": full_text[:300],
            "error": "parse_failed",
        }
