"""Shared utilities for agent JSON parsing."""
import json
import re


def parse_llm_json(text: str) -> dict:
    """Robustly parse JSON from LLM output — handles markdown code blocks and truncation."""
    # Strip markdown code fences
    text = re.sub(r"```(?:json)?\s*", "", text).strip()

    # Find outermost JSON object
    start = text.find("{")
    end = text.rfind("}") + 1
    if start == -1 or end == 0:
        raise ValueError("No JSON object found in response")

    json_str = text[start:end]
    return json.loads(json_str)
