"""Multi-model fallback chain for resilience across API failures."""
import json
import httpx
from typing import Optional
from anthropic import Anthropic, APIConnectionError, APIError
import google.generativeai as genai
from config import (
    ANTHROPIC_API_KEY, GEMINI_API_KEY, GROK_API_KEY, GROK_BASE_URL,
    TEMPERATURE, QUALITY_CLOUD_MODEL, FAST_CLOUD_MODEL
)


class ModelChain:
    """Manages fallback chain: Claude → Gemini → Grok → Ollama → Gemma."""
    
    def __init__(self):
        self.claude_client = Anthropic(api_key=ANTHROPIC_API_KEY, max_retries=2)
        self.gemini_model = genai.GenerativeModel("gemini-2.5-flash")
        self.grok_client = None
        self.ollama_available = False
        self.gemma_available = False
        
        # Initialize Grok if available
        if GROK_API_KEY:
            try:
                from openai import OpenAI
                self.grok_client = OpenAI(api_key=GROK_API_KEY, base_url=GROK_BASE_URL)
            except Exception:
                pass
        
        # Check Ollama availability
        self._check_ollama()
        self._check_gemma()
    
    def _check_ollama(self) -> bool:
        """Check if Ollama is running locally."""
        try:
            response = httpx.get("http://localhost:11434/api/tags", timeout=2)
            self.ollama_available = response.status_code == 200
            return self.ollama_available
        except Exception:
            self.ollama_available = False
            return False
    
    def _check_gemma(self) -> bool:
        """Check if local Gemma model is available."""
        try:
            # Try to import ollama and check for gemma model
            import ollama
            models = ollama.list()
            self.gemma_available = any("gemma" in m.get("name", "") for m in models.get("models", []))
            return self.gemma_available
        except Exception:
            self.gemma_available = False
            return False
    
    def call_with_fallback(self, model_type: str, system_prompt: str, user_message: str,
                          max_tokens: int = 4000) -> dict:
        """
        Call LLM with automatic fallback chain.
        
        Fallback order:
        1. Claude Sonnet (primary)
        2. Claude Haiku (faster fallback)
        3. Gemini 2.5 Flash
        4. Grok 3 Mini
        5. Ollama Llama2
        6. Local Gemma
        
        Args:
            model_type: "quality" for Sonnet, "fast" for Haiku
            system_prompt: System prompt
            user_message: User query
            max_tokens: Max response length
        
        Returns:
            {"success": bool, "model": str, "response": str, "error": Optional[str]}
        """
        
        # Try Claude Sonnet first
        try:
            response = self.claude_client.messages.create(
                model=QUALITY_CLOUD_MODEL,
                max_tokens=max_tokens,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return {
                "success": True,
                "model": f"Claude Sonnet",
                "response": response.content[0].text,
                "error": None,
            }
        except (APIConnectionError, APIError) as e:
            print(f"  [FALLBACK] Claude Sonnet failed: {str(e)[:50]}")
        
        # Try Claude Haiku (faster)
        try:
            response = self.claude_client.messages.create(
                model=FAST_CLOUD_MODEL,
                max_tokens=max_tokens,
                temperature=TEMPERATURE,
                system=system_prompt,
                messages=[{"role": "user", "content": user_message}],
            )
            return {
                "success": True,
                "model": "Claude Haiku",
                "response": response.content[0].text,
                "error": None,
            }
        except (APIConnectionError, APIError) as e:
            print(f"  [FALLBACK] Claude Haiku failed: {str(e)[:50]}")
        
        # Try Gemini Flash
        if GEMINI_API_KEY:
            try:
                response = self.gemini_model.generate_content(
                    f"{system_prompt}\n\nUser: {user_message}",
                    generation_config=genai.types.GenerationConfig(
                        max_output_tokens=max_tokens,
                        temperature=TEMPERATURE,
                    ),
                    timeout=30,
                )
                return {
                    "success": True,
                    "model": "Gemini 2.5 Flash",
                    "response": response.text,
                    "error": None,
                }
            except Exception as e:
                print(f"  [FALLBACK] Gemini failed: {str(e)[:50]}")
        
        # Try Grok
        if self.grok_client:
            try:
                response = self.grok_client.chat.completions.create(
                    model="grok-3-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_message},
                    ],
                    temperature=TEMPERATURE,
                    max_tokens=max_tokens,
                )
                return {
                    "success": True,
                    "model": "Grok 3 Mini",
                    "response": response.choices[0].message.content,
                    "error": None,
                }
            except Exception as e:
                print(f"  [FALLBACK] Grok failed: {str(e)[:50]}")
        
        # Try Ollama Llama2
        if self.ollama_available:
            try:
                import ollama
                response = ollama.generate(
                    model="llama2",
                    prompt=f"{system_prompt}\n\n{user_message}",
                    stream=False,
                )
                return {
                    "success": True,
                    "model": "Ollama Llama2",
                    "response": response.get("response", ""),
                    "error": None,
                }
            except Exception as e:
                print(f"  [FALLBACK] Ollama Llama2 failed: {str(e)[:50]}")
        
        # Try local Gemma
        if self.gemma_available:
            try:
                import ollama
                response = ollama.generate(
                    model="gemma:2b",
                    prompt=f"{system_prompt}\n\n{user_message}",
                    stream=False,
                )
                return {
                    "success": True,
                    "model": "Ollama Gemma",
                    "response": response.get("response", ""),
                    "error": None,
                }
            except Exception as e:
                print(f"  [FALLBACK] Gemma failed: {str(e)[:50]}")
        
        # All fallbacks exhausted
        return {
            "success": False,
            "model": None,
            "response": None,
            "error": "All models in fallback chain exhausted",
        }
    
    def get_status(self) -> dict:
        """Get current status of all models in fallback chain."""
        return {
            "claude": "✓ Available",
            "gemini": "✓ Available" if GEMINI_API_KEY else "✗ No API key",
            "grok": "✓ Available" if self.grok_client else "✗ Not configured",
            "ollama": "✓ Running" if self.ollama_available else "✗ Not available",
            "gemma_local": "✓ Available" if self.gemma_available else "✗ Not installed",
        }


# Global instance
_model_chain = None

def get_model_chain() -> ModelChain:
    """Get or initialize global model chain."""
    global _model_chain
    if _model_chain is None:
        _model_chain = ModelChain()
    return _model_chain


def call_with_fallback(model_type: str, system_prompt: str, user_message: str,
                       max_tokens: int = 4000) -> dict:
    """Convenience function for calling model chain."""
    chain = get_model_chain()
    return chain.call_with_fallback(model_type, system_prompt, user_message, max_tokens)
