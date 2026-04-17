"""Multi-model consensus voting for high-accuracy verdicts on critical issues."""
import json
import httpx
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Optional
from anthropic import Anthropic
import google.generativeai as genai
from config import ANTHROPIC_API_KEY, GEMINI_API_KEY, TEMPERATURE


class MultiModelConsensus:
    """Run verdicts through multiple LLM models and reach consensus."""
    
    def __init__(self):
        """Initialize multi-model consensus system."""
        self.claude_client = Anthropic(api_key=ANTHROPIC_API_KEY)
        self.gemini_available = bool(GEMINI_API_KEY)
        if self.gemini_available:
            genai.configure(api_key=GEMINI_API_KEY)
    
    def _call_claude_sonnet(self, system: str, prompt: str) -> Optional[dict]:
        """Call Claude Sonnet for verdict."""
        try:
            response = self.claude_client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                temperature=TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            # Parse JSON from response
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"  Claude Sonnet error: {str(e)[:50]}")
        return None
    
    def _call_claude_opus(self, system: str, prompt: str) -> Optional[dict]:
        """Call Claude Opus (if available) for deep reasoning."""
        try:
            response = self.claude_client.messages.create(
                model="claude-opus-4-1-20250805",
                max_tokens=2000,
                temperature=TEMPERATURE,
                system=system,
                messages=[{"role": "user", "content": prompt}],
            )
            text = response.content[0].text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"  Claude Opus error: {str(e)[:50]}")
        return None
    
    def _call_gemini(self, system: str, prompt: str) -> Optional[dict]:
        """Call Gemini for alternative perspective."""
        if not self.gemini_available:
            return None
        
        try:
            model = genai.GenerativeModel("gemini-2.5-flash")
            response = model.generate_content(
                f"{system}\n\n{prompt}",
                generation_config=genai.types.GenerationConfig(
                    temperature=TEMPERATURE,
                    max_output_tokens=2000,
                ),
                timeout=30,
            )
            text = response.text
            start = text.find('{')
            end = text.rfind('}') + 1
            if start >= 0 and end > start:
                return json.loads(text[start:end])
        except Exception as e:
            print(f"  Gemini error: {str(e)[:50]}")
        return None
    
    def _call_local_model(self, system: str, prompt: str) -> Optional[dict]:
        """Call local model if available via Ollama."""
        try:
            from agents.ollama_local import OllamaManager
            ollama = OllamaManager()
            if ollama.is_available():
                result = ollama.generate(
                    prompt=prompt,
                    model="llama2:13b",
                    system=system,
                    max_tokens=2000
                )
                if result["success"]:
                    text = result["response"]
                    start = text.find('{')
                    end = text.rfind('}') + 1
                    if start >= 0 and end > start:
                        return json.loads(text[start:end])
        except Exception as e:
            print(f"  Local model error: {str(e)[:50]}")
        return None
    
    def consensus_verdict(self, context: dict, transcript: dict,
                         critical_only: bool = True, verbose: bool = False) -> dict:
        """
        Generate verdict through multiple models and reach consensus.
        
        Args:
            context: RAG context with GO metadata
            transcript: Debate transcript
            critical_only: If True, only use multi-model consensus for critical issues
            verbose: Show progress
        
        Returns:
            Consensus verdict with agreement scores
        """
        system_prompt = """You are a Supreme Court judge evaluating a legal debate.
Analyze the arguments on their legal merit, constitutional basis, precedent application.
Return ONLY valid JSON with: verdict, composite_score (0-10), hc_success_probability (0-100),
key_finding, reasoning (one paragraph)."""
        
        transcript_summary = json.dumps({
            "go_number": context.get("go_metadata", {}).get("go_number"),
            "rounds": len(transcript.get("rounds", [])),
            "go_position": transcript.get("rounds", [{}])[0].get("go_lawyer", "")[:200] if transcript.get("rounds") else "",
            "constitutional_position": transcript.get("rounds", [{}])[0].get("const_lawyer", "")[:200] if transcript.get("rounds") else "",
        }, indent=2)
        
        user_prompt = f"""Render verdict on this debate transcript:

{transcript_summary}

Return JSON with: verdict (STRUCK_DOWN|UPHELD|CONDITIONAL|INVALID), composite_score, hc_success_probability, 
key_finding, reasoning."""
        
        # Collect verdicts from multiple models in parallel
        verdicts = {}
        models = [
            ("claude_sonnet", self._call_claude_sonnet),
            ("claude_opus", self._call_claude_opus),
            ("gemini", self._call_gemini),
            ("local_model", self._call_local_model),
        ]
        
        if verbose:
            print("  Collecting consensus verdicts from multiple models...")
        
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = {
                executor.submit(model_func, system_prompt, user_prompt): name
                for name, model_func in models
            }
            
            for future in as_completed(futures):
                model_name = futures[future]
                try:
                    verdict = future.result()
                    if verdict:
                        verdicts[model_name] = verdict
                        if verbose:
                            print(f"    ✓ {model_name}: {verdict.get('verdict', 'N/A')}")
                except Exception as e:
                    if verbose:
                        print(f"    ✗ {model_name}: {str(e)[:30]}")
        
        # Compute consensus
        consensus = self._compute_consensus(verdicts, verbose)
        
        return {
            "consensus_verdict": consensus["verdict"],
            "consensus_score": consensus["score"],
            "hc_success_probability": consensus["hc_prob"],
            "agreement_level": consensus["agreement"],
            "model_results": verdicts,
            "num_models": len(verdicts),
            "_use_consensus": len(verdicts) >= 2,
        }
    
    def _compute_consensus(self, verdicts: Dict, verbose: bool = False) -> dict:
        """
        Compute consensus from multiple model verdicts.
        
        Args:
            verdicts: Dict of model_name -> verdict_dict
            verbose: Show progress
        
        Returns:
            Consensus verdict with agreement metrics
        """
        if not verdicts:
            return {
                "verdict": "INDETERMINATE",
                "score": 5.0,
                "hc_prob": 50,
                "agreement": 0.0,
            }
        
        # Collect scores
        scores = []
        hc_probs = []
        verdict_names = []
        
        for model, result in verdicts.items():
            if result:
                score = result.get("composite_score")
                hc_prob = result.get("hc_success_probability")
                verdict = result.get("verdict")
                
                if score is not None:
                    scores.append(float(score))
                if hc_prob is not None:
                    hc_probs.append(float(hc_prob))
                if verdict:
                    verdict_names.append(verdict)
        
        # Compute average score
        avg_score = sum(scores) / len(scores) if scores else 5.0
        avg_hc_prob = sum(hc_probs) / len(hc_probs) if hc_probs else 50
        
        # Determine majority verdict
        if verdict_names:
            from collections import Counter
            verdict_counts = Counter(verdict_names)
            majority_verdict = verdict_counts.most_common(1)[0][0]
            agreement = verdict_counts.most_common(1)[0][1] / len(verdict_names)
        else:
            majority_verdict = "STRUCK_DOWN" if avg_score < 4 else "UPHELD" if avg_score > 6 else "CONDITIONAL"
            agreement = 0.0
        
        if verbose:
            print(f"    Consensus: {majority_verdict} (score: {avg_score:.1f}/10, "
                  f"HC prob: {avg_hc_prob:.0f}%, agreement: {agreement:.0%})")
        
        return {
            "verdict": majority_verdict,
            "score": round(avg_score, 2),
            "hc_prob": round(avg_hc_prob, 0),
            "agreement": round(agreement, 2),
        }
    
    def get_status(self) -> dict:
        """Get status of available models for consensus."""
        return {
            "claude_sonnet": "✓ Available",
            "claude_opus": "✓ Available (extended reasoning)",
            "gemini": "✓ Available" if self.gemini_available else "✗ No API key",
            "local_model": "Check Ollama status separately",
        }


def run_consensus_verdict(context: dict, transcript: dict, 
                         critical_only: bool = True, verbose: bool = False) -> dict:
    """Convenience function for multi-model consensus verdict."""
    consensus = MultiModelConsensus()
    return consensus.consensus_verdict(context, transcript, critical_only, verbose)
