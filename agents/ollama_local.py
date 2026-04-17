"""Local model integration with Ollama for offline operation and cost savings."""
import json
import subprocess
import requests
from typing import Optional, List
from pathlib import Path


class OllamaManager:
    """Manages local LLM models via Ollama."""
    
    # Recommended models for legal analysis
    LEGAL_MODELS = {
        "llama2-legal": {
            "base_model": "llama2:13b",
            "system_prompt": """You are a legal analyst specializing in Indian government law.
Analyze Government Orders for legal violations and issues.""",
            "context_window": 4096,
            "qualityrank": 7,
            "speed": "medium",
        },
        "llama2-uncensored": {
            "base_model": "llama2-uncensored:7b",
            "system_prompt": """You are a government order analyst.
Provide technical legal analysis.""",
            "context_window": 4096,
            "quality_rank": 6,
            "speed": "fast",
        },
        "neural-chat": {
            "base_model": "neural-chat:7b",
            "system_prompt": """You are a legal expert.
Analyze government orders for issues.""",
            "context_window": 2048,
            "quality_rank": 5,
            "speed": "fast",
        },
        "mistral": {
            "base_model": "mistral:7b",
            "system_prompt": """You are a legal analyst.
Analyze documents for legal violations.""",
            "context_window": 8192,
            "quality_rank": 7,
            "speed": "fast",
        },
    }
    
    def __init__(self, host: str = "http://localhost:11434"):
        """
        Initialize Ollama manager.
        
        Args:
            host: Ollama API host (default: localhost:11434)
        """
        self.host = host
        self.api_generate = f"{host}/api/generate"
        self.api_pull = f"{host}/api/pull"
        self.api_tags = f"{host}/api/tags"
        self.available = False
        self.models = []
        self._check_availability()
    
    def _check_availability(self) -> bool:
        """Check if Ollama is running."""
        try:
            response = requests.get(self.api_tags, timeout=2)
            if response.status_code == 200:
                data = response.json()
                self.models = [m["name"] for m in data.get("models", [])]
                self.available = True
                return True
        except Exception:
            self.available = False
        return False
    
    def is_available(self) -> bool:
        """Check if Ollama is available."""
        return self._check_availability()
    
    def pull_model(self, model_name: str, stream: bool = False) -> bool:
        """
        Download and install a model from Ollama registry.
        
        Args:
            model_name: Model name (e.g., "llama2:13b", "mistral:7b")
            stream: Show download progress
        
        Returns:
            True if successful
        """
        try:
            print(f"Pulling model: {model_name}...")
            response = requests.post(
                self.api_pull,
                json={"name": model_name, "stream": stream},
                timeout=None,  # Long timeout for downloads
            )
            if response.status_code == 200:
                self._check_availability()  # Refresh model list
                print(f"✓ Model {model_name} installed successfully")
                return True
        except Exception as e:
            print(f"✗ Failed to pull model {model_name}: {e}")
        return False
    
    def generate(self, prompt: str, model: str = "llama2:13b",
                 system: Optional[str] = None, max_tokens: int = 2000) -> dict:
        """
        Generate response using local model.
        
        Args:
            prompt: User prompt
            model: Model name to use
            system: System prompt
            max_tokens: Max tokens in response
        
        Returns:
            {"success": bool, "response": str, "model": str, "error": Optional[str]}
        """
        if not self.available:
            return {
                "success": False,
                "response": None,
                "model": model,
                "error": "Ollama not available. Install: https://ollama.ai/download",
            }
        
        if model not in self.models:
            return {
                "success": False,
                "response": None,
                "model": model,
                "error": f"Model {model} not installed. Use pull_model() to download.",
            }
        
        try:
            full_prompt = f"{system}\n\n{prompt}" if system else prompt
            
            response = requests.post(
                self.api_generate,
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": False,
                    "options": {
                        "num_predict": max_tokens,
                        "temperature": 0.2,
                    },
                },
                timeout=120,
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "response": data.get("response", ""),
                    "model": model,
                    "error": None,
                }
        except Exception as e:
            return {
                "success": False,
                "response": None,
                "model": model,
                "error": str(e)[:100],
            }
        
        return {
            "success": False,
            "response": None,
            "model": model,
            "error": "Unknown error",
        }
    
    def stream_generate(self, prompt: str, model: str = "llama2:13b",
                       system: Optional[str] = None, callback=None):
        """
        Stream generation response token-by-token.
        
        Args:
            prompt: User prompt
            model: Model to use
            system: System prompt
            callback: Function(token) called for each generated token
        
        Returns:
            Full accumulated response
        """
        if not self.available:
            return None
        
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        full_response = ""
        
        try:
            response = requests.post(
                self.api_generate,
                json={
                    "model": model,
                    "prompt": full_prompt,
                    "stream": True,
                },
                stream=True,
                timeout=120,
            )
            
            for line in response.iter_lines():
                if line:
                    data = json.loads(line)
                    token = data.get("response", "")
                    full_response += token
                    if callback:
                        callback(token)
                    
                    if data.get("done"):
                        break
        except Exception as e:
            print(f"Stream error: {e}")
        
        return full_response
    
    def get_status(self) -> dict:
        """Get Ollama status and installed models."""
        return {
            "available": self.available,
            "host": self.host,
            "models_installed": self.models,
            "recommended_models": list(self.LEGAL_MODELS.keys()),
        }
    
    def benchmark_model(self, model: str, test_prompt: str = None) -> dict:
        """
        Benchmark a model's speed and quality.
        
        Args:
            model: Model to benchmark
            test_prompt: Optional test prompt
        
        Returns:
            Benchmark results
        """
        if test_prompt is None:
            test_prompt = "Analyze this: Article 14 guarantees equality before law."
        
        import time
        start = time.time()
        result = self.generate(test_prompt, model=model, max_tokens=200)
        elapsed = time.time() - start
        
        return {
            "model": model,
            "success": result["success"],
            "response_length": len(result.get("response", "")),
            "time_seconds": round(elapsed, 2),
            "tokens_per_second": round(len(result.get("response", "").split()) / elapsed, 1) if elapsed > 0 else 0,
        }


class OfflineExpertAnalysis:
    """Run expert panel analysis locally using Ollama (for offline operation)."""
    
    def __init__(self, model: str = "llama2:13b"):
        """
        Initialize offline expert analysis.
        
        Args:
            model: Ollama model to use
        """
        self.ollama = OllamaManager()
        self.model = model
        
        if not self.ollama.is_available():
            print("⚠ Warning: Ollama not available. Some features may not work.")
    
    def analyze_offline(self, go_text: str, context: dict) -> dict:
        """
        Analyze GO locally without cloud API.
        
        Args:
            go_text: GO text
            context: RAG context
        
        Returns:
            Analysis results
        """
        system_prompt = """You are a legal expert analyzing Indian Government Orders.
Provide analysis in structured format."""
        
        prompt = f"""Analyze this Government Order for issues:

{go_text[:1000]}

Provide: key_issues (list), legal_violations (list), severity_level, recommendation."""
        
        result = self.ollama.generate(prompt, model=self.model, system=system_prompt)
        
        return {
            "offline": True,
            "model": self.model,
            "analysis": result.get("response"),
            "success": result["success"],
            "note": "Local analysis - may have lower accuracy than cloud models",
        }


# Setup helper
def setup_ollama_for_legal_analysis():
    """One-time setup to pull recommended models."""
    ollama = OllamaManager()
    
    if not ollama.is_available():
        print("✗ Ollama not installed. Download from: https://ollama.ai/download")
        return False
    
    # Pull recommended models
    models_to_pull = ["llama2:13b", "mistral:7b", "neural-chat:7b"]
    for model in models_to_pull:
        if model not in ollama.models:
            print(f"\nInstalling {model}... (this may take a few minutes)")
            ollama.pull_model(model, stream=True)
    
    print("\n✓ Ollama setup complete!")
    print(f"Available models: {ollama.models}")
    return True
