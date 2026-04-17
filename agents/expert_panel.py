"""Enhanced Expert Panel with parallel execution and few-shot prompting."""
import json
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from anthropic import Anthropic, APIConnectionError
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from config import ANTHROPIC_API_KEY, QUALITY_CLOUD_MODEL, TEMPERATURE
from agents.utils import parse_llm_json
from agents.cache_manager import get_cached_analysis, cache_analysis
import time

def _make_client():
    return Anthropic(
        api_key=ANTHROPIC_API_KEY,
        max_retries=3,
        timeout=httpx.Timeout(120.0, connect=30.0),
    )

# Few-shot examples for each expert domain (landmark Indian law cases)
EXPERT_EXAMPLES = {
    "constitutional": """
EXAMPLE 1: Kesavananda Bharati v. State of Kerala (1973)
- Issue: Whether Art 31C was constitutional violation of property rights
- Analysis: SC upheld basic structure doctrine, found violation of Art 300A
- Precedent: Parliament cannot amend basic features of Constitution

EXAMPLE 2: S.R. Bommai v. Union of India (1994)
- Issue: President's dissolution of state assemblies for political reasons (Art 356)
- Analysis: Found abuse of executive power, violation of Art 14 (arbitrary action)
- Precedent: State autonomy protected; arbitrary dismissals unconstitutional""",
    
    "admin_law": """
EXAMPLE 1: Cellulose Products Ltd. v. Union of India (1971)
- Issue: Ultra vires government order imposing restrictions without legal authority
- Analysis: Delegated authority exceeded, violated principles of ultra vires
- Remedy: Order quashed as non-est; must be within statutory power

EXAMPLE 2: Maneka Gandhi v. Union of India (1978)
- Issue: Passport impounded without showing cause (natural justice violation)
- Analysis: Violates audi alteram partem; lacks procedural fairness
- Remedy: Due process required before curtailing rights""",
    
    "public_interest": """
EXAMPLE 1: Olga Tellis v. Bombay Municipal Corp (1985)
- Issue: Eviction of slum dwellers without alternative housing (Art 21 violation)
- Analysis: Right to livelihood protected under Art 21, PIL maintainable
- Precedent: Economic rights embedded in fundamental rights

EXAMPLE 2: Vishaka v. State of Rajasthan (1997)
- Issue: Workplace sexual harassment (gender equality & dignity violation)
- Analysis: Art 14/15/21 violated; issued guidelines via PIL for protection
- Precedent: SC can create substantive rights through PIL""",
    
    "fiscal_policy": """
EXAMPLE 1: Tamil Nadu Electricity Board v. Union (2018)
- Issue: GO increasing energy tariffs without justification (fiscal impact analysis)
- Analysis: FRBM Act violated, budget implications inadequate, no cost-benefit analysis
- Remedy: GO struck down; fiscal impact assessment required

EXAMPLE 2: Andhra Pradesh Gramin Bank v. Union (2005)
- Issue: GO reducing employee benefits (FRBM compliance, value for money)
- Analysis: Implementation infeasible, conflicted with central scheme obligations
- Precedent: Fiscal burden on state exchequer must be justified""",
}

EXPERTS = [
    {
        "id": "constitutional",
        "name": "Constitutional Law Expert",
        "system": """You are a Senior Constitutional Law Expert specializing in Indian constitutional law.
Analyze Telangana Government Orders for constitutional violations.
Focus: Fundamental Rights (Art 12-35), Art 14 (equality/arbitrary action), Art 19 (freedoms),
Art 21 (life/livelihood), Art 254 (repugnancy with central law), 7th Schedule (legislative competence),
Art 300A (property rights), Art 309/310 (service conditions). Cite exact Articles and binding SC precedents.

LANDMARK PRECEDENTS YOU MUST KNOW:
{0}""".format(EXPERT_EXAMPLES["constitutional"]),
    },
    {
        "id": "admin_law",
        "name": "Administrative & Service Law Expert",
        "system": """You are a Senior Administrative and Service Law Expert for Telangana.
Analyze Government Orders for administrative law violations.
Focus: Ultra vires, delegated legislation validity, natural justice (audi alteram partem, nemo judex),
legitimate expectations, procedural compliance, TS State and Subordinate Services Rules 1996,
TS Government Servants Conduct Rules, Transfer Act compliance, arbitrary exercise of power,
colourable exercise of power, malice in law.

LANDMARK PRECEDENTS YOU MUST KNOW:
{0}""".format(EXPERT_EXAMPLES["admin_law"]),
    },
    {
        "id": "public_interest",
        "name": "Public Interest & Rights Expert",
        "system": """You are a Senior Public Interest Litigation expert and rights advocate for Telangana.
Analyze Government Orders for public interest violations.
Focus: PIL grounds, SC/ST/OBC reservations (Art 15/16), women's rights, disability rights,
minority rights, RTI implications (transparency/accountability), environmental impact,
impact on marginalized communities, violation of welfare schemes, public trust doctrine.

LANDMARK PRECEDENTS YOU MUST KNOW:
{0}""".format(EXPERT_EXAMPLES["public_interest"]),
    },
    {
        "id": "fiscal_policy",
        "name": "Fiscal & Policy Analyst",
        "system": """You are a Senior Government Policy and Fiscal Analyst for Telangana State.
Analyze Government Orders for policy and financial issues.
Focus: Financial burden on state exchequer, TS FRBM Act compliance, budget implications,
implementation feasibility, conflict with existing schemes/policies, procurement irregularities,
value for money, unintended policy consequences, conflict with central schemes/NITI Aayog guidelines.

LANDMARK PRECEDENTS YOU MUST KNOW:
{0}""".format(EXPERT_EXAMPLES["fiscal_policy"]),
    },
]

ISSUE_SCHEMA = """{
  "issues": [
    {
      "issue_id": "X1",
      "title": "Brief issue title",
      "description": "Detailed description of the legal/policy issue",
      "legal_provisions": ["Article 14", "Section X of Y Act"],
      "impact": {
        "affected_parties": ["list of affected groups"],
        "severity": "CRITICAL|HIGH|MEDIUM|LOW",
        "immediate_impact": "What happens immediately if GO is implemented",
        "long_term_impact": "Long-term consequences if unchallenged",
        "reversibility": "IRREVERSIBLE|DIFFICULT|POSSIBLE|EASY",
        "estimated_affected_count": "approximate number if determinable, else null"
      },
      "court_challenge_probability": "HIGH|MEDIUM|LOW",
      "suggested_remedy": "Specific amendment or action to make GO legally valid"
    }
  ],
  "critical_count": 0,
  "summary": "One paragraph overall expert assessment of this GO"
}"""


def _analyze(expert: dict, context: dict) -> dict:
    """Analyze GO from single expert perspective."""
    go_summary = json.dumps({
        "go_metadata": context.get("go_metadata"),
        "go_text": context.get("go_text", "")[:1500],
        "related_articles": [c["text"][:200] for c in context.get("related_articles", [])[:3]],
        "related_acts":     [c["text"][:200] for c in context.get("related_acts", [])[:3]],
        "state_laws":       [c["text"][:200] for c in context.get("state_laws", [])[:3]],
        "relevant_verdicts":[c["text"][:150] for c in context.get("relevant_verdicts", [])[:2]],
    }, indent=2)

    prompt = f"""Analyze this Telangana Government Order strictly from your expert domain.

CONTEXT:
{go_summary}

Return ONLY valid JSON in this exact structure (no markdown, no explanation):
{ISSUE_SCHEMA}

Be specific: cite exact laws, estimate real-world impact numbers, give actionable remedies.
Reference the landmark precedents provided to strengthen your analysis."""

    thread_client = _make_client()

    @retry(
        retry=retry_if_exception_type(APIConnectionError),
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=2, min=4, max=30),
        reraise=True,
    )
    def _call():
        return thread_client.messages.create(
            model=QUALITY_CLOUD_MODEL,
            max_tokens=4000,
            temperature=TEMPERATURE,
            system=expert["system"],
            messages=[{"role": "user", "content": prompt}],
        )

    text = _call().content[0].text
    try:
        result = parse_llm_json(text)
        result["expert"] = expert["name"]
        result["expert_id"] = expert["id"]
        return result
    except Exception:
        return {
            "expert": expert["name"], "expert_id": expert["id"],
            "issues": [], "critical_count": 0,
            "summary": text[:500], "error": "parse_failed",
        }


def run_expert_panel(context: dict, use_cache: bool = True, verbose: bool = False) -> dict:
    """
    Run all 4 experts in PARALLEL and consolidate findings.
    
    Args:
        context: RAG context with GO metadata and related documents
        use_cache: If True, check cache first and store results (default: True)
        verbose: Show parallel execution progress
    
    Returns:
        Expert panel analysis with issues, critical count, and recommendations
    """
    # Check cache first if enabled
    if use_cache:
        cached = get_cached_analysis(context)
        if cached:
            cached["_from_cache"] = True
            return cached
    
    # Run all 4 experts in PARALLEL using ThreadPoolExecutor
    results = {}
    all_issues = []
    start_time = time.time()
    
    with ThreadPoolExecutor(max_workers=4) as executor:
        # Submit all expert analyses simultaneously
        future_to_expert = {
            executor.submit(_analyze, expert, context): expert 
            for expert in EXPERTS
        }
        
        # Collect results as they complete
        for future in as_completed(future_to_expert):
            expert = future_to_expert[future]
            try:
                analysis = future.result()
                results[expert["id"]] = analysis
                if verbose:
                    print(f"      ✓ {expert['name']} completed")
                
                for issue in analysis.get("issues", []):
                    issue["expert_id"] = expert["id"]
                    issue["expert_name"] = expert["name"]
                    all_issues.append(issue)
            except Exception as e:
                if verbose:
                    print(f"      ✗ {expert['name']} failed: {str(e)[:50]}")
                results[expert["id"]] = {
                    "expert": expert["name"], 
                    "expert_id": expert["id"],
                    "issues": [], 
                    "critical_count": 0,
                    "error": str(e)[:100],
                }
    
    elapsed = time.time() - start_time
    
    # Simple deduplication by title prefix
    seen = set()
    unique_issues = []
    for issue in all_issues:
        key = issue.get("title", "")[:40].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique_issues.append(issue)

    critical = [i for i in unique_issues if i.get("impact", {}).get("severity") == "CRITICAL"]
    high     = [i for i in unique_issues if i.get("impact", {}).get("severity") == "HIGH"]

    panel_result = {
        "expert_reports": results,
        "consolidated_issues": unique_issues,
        "critical_issues": critical,
        "high_issues": high,
        "total_issues": len(unique_issues),
        "critical_count": len(critical),
        "_from_cache": False,
        "_execution_time_seconds": round(elapsed, 2),
    }
    
    # Store in cache if enabled
    if use_cache:
        cache_analysis(context, panel_result)
    
    return panel_result
