"""Advanced embeddings support for improved RAG performance."""
from typing import List, Optional
import numpy as np
from sentence_transformers import SentenceTransformer


class EmbeddingManager:
    """Manages multiple embedding models for flexible RAG pipeline."""
    
    AVAILABLE_MODELS = {
        "default": {
            "name": "sentence-transformers/all-mpnet-base-v2",
            "dim": 768,
            "speed": "medium",
            "quality": "good",
            "domain": "general",
        },
        "legal-optimized": {
            "name": "sentence-transformers/all-minilm-l12-v2",
            "dim": 384,
            "speed": "fast",
            "quality": "excellent",
            "domain": "legal",
        },
        "bge-large": {
            "name": "BAAI/bge-large-en-v1.5",
            "dim": 1024,
            "speed": "medium",
            "quality": "excellent",
            "domain": "retrieval",
        },
        "gte-large": {
            "name": "thenlper/gte-large",
            "dim": 1024,
            "speed": "medium",
            "quality": "excellent",
            "domain": "retrieval",
        },
        "all-roberta": {
            "name": "sentence-transformers/all-roberta-large-v1",
            "dim": 768,
            "speed": "slow",
            "quality": "excellent",
            "domain": "semantic",
        },
        "mpnet-base": {
            "name": "sentence-transformers/mpnet-base-v2",
            "dim": 768,
            "speed": "medium",
            "quality": "excellent",
            "domain": "semantic",
        },
    }
    
    def __init__(self, model_key: str = "default"):
        """
        Initialize embedding manager with specified model.
        
        Args:
            model_key: Key from AVAILABLE_MODELS (e.g., "default", "legal-optimized", "bge-large")
        """
        if model_key not in self.AVAILABLE_MODELS:
            raise ValueError(f"Unknown model: {model_key}. Available: {list(self.AVAILABLE_MODELS.keys())}")
        
        self.model_key = model_key
        model_info = self.AVAILABLE_MODELS[model_key]
        self.model_name = model_info["name"]
        self.dimension = model_info["dim"]
        
        # Load model
        try:
            self.model = SentenceTransformer(self.model_name)
            print(f"✓ Loaded embedding model: {model_key} ({self.model_name})")
        except Exception as e:
            raise RuntimeError(f"Failed to load embedding model {self.model_name}: {str(e)}")
    
    def embed_texts(self, texts: List[str]) -> np.ndarray:
        """
        Embed a list of texts.
        
        Args:
            texts: List of text strings to embed
        
        Returns:
            numpy array of shape (len(texts), embedding_dim)
        """
        embeddings = self.model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return embeddings
    
    def embed_single(self, text: str) -> np.ndarray:
        """Embed single text."""
        return self.embed_texts([text])[0]
    
    def cosine_similarity(self, query_embedding: np.ndarray, 
                         doc_embeddings: np.ndarray) -> np.ndarray:
        """
        Compute cosine similarity between query and documents.
        
        Args:
            query_embedding: Query embedding (shape: embedding_dim,)
            doc_embeddings: Document embeddings (shape: num_docs, embedding_dim)
        
        Returns:
            Similarity scores (shape: num_docs,)
        """
        from sklearn.metrics.pairwise import cosine_similarity
        return cosine_similarity(
            query_embedding.reshape(1, -1),
            doc_embeddings
        ).flatten()
    
    def search_similar(self, query: str, documents: List[str], 
                       top_k: int = 5) -> List[tuple]:
        """
        Find top-k similar documents to query.
        
        Args:
            query: Query text
            documents: List of document texts
            top_k: Number of top results to return
        
        Returns:
            List of (score, index, document) tuples sorted by score
        """
        query_emb = self.embed_single(query)
        doc_embs = self.embed_texts(documents)
        
        scores = self.cosine_similarity(query_emb, doc_embs)
        
        # Get top-k indices
        top_indices = np.argsort(scores)[::-1][:top_k]
        
        results = [
            (float(scores[idx]), idx, documents[idx])
            for idx in top_indices
        ]
        return results
    
    def get_info(self) -> dict:
        """Get information about current embedding model."""
        info = self.AVAILABLE_MODELS[self.model_key]
        return {
            "key": self.model_key,
            "name": self.model_name,
            **info
        }


class MultiEmbeddingSearch:
    """Hybrid search using multiple embedding models for consensus."""
    
    def __init__(self, model_keys: List[str] = None):
        """
        Initialize multi-embedding search.
        
        Args:
            model_keys: List of model keys to use (default: ["default", "bge-large"])
        """
        if model_keys is None:
            model_keys = ["default", "bge-large"]
        
        self.managers = {}
        for key in model_keys:
            try:
                self.managers[key] = EmbeddingManager(key)
            except Exception as e:
                print(f"⚠ Failed to load {key}: {e}")
    
    def consensus_search(self, query: str, documents: List[str], 
                        top_k: int = 5) -> List[tuple]:
        """
        Find top documents using consensus from multiple embedding models.
        
        Args:
            query: Query text
            documents: List of document texts
            top_k: Number of results
        
        Returns:
            List of (consensus_score, index, document) tuples
        """
        if not self.managers:
            raise RuntimeError("No embedding models available")
        
        # Collect scores from all models
        all_scores = {}
        for model_key, manager in self.managers.items():
            results = manager.search_similar(query, documents, top_k=len(documents))
            for score, idx, _ in results:
                if idx not in all_scores:
                    all_scores[idx] = []
                all_scores[idx].append(score)
        
        # Compute consensus scores (average)
        consensus = {
            idx: {
                "score": np.mean(scores),
                "std_dev": np.std(scores),
                "num_models": len(scores),
            }
            for idx, scores in all_scores.items()
        }
        
        # Sort by consensus score
        sorted_indices = sorted(
            consensus.keys(),
            key=lambda idx: consensus[idx]["score"],
            reverse=True
        )[:top_k]
        
        results = [
            (consensus[idx]["score"], idx, documents[idx])
            for idx in sorted_indices
        ]
        return results
    
    def get_status(self) -> dict:
        """Get status of all embedding models."""
        return {
            key: manager.get_info()
            for key, manager in self.managers.items()
        }


# Convenience functions
_default_manager = None

def get_embedding_manager(model_key: str = "default") -> EmbeddingManager:
    """Get or create embedding manager."""
    global _default_manager
    if _default_manager is None or _default_manager.model_key != model_key:
        _default_manager = EmbeddingManager(model_key)
    return _default_manager


def embed_texts(texts: List[str], model_key: str = "default") -> np.ndarray:
    """Quick function to embed texts."""
    manager = get_embedding_manager(model_key)
    return manager.embed_texts(texts)


def search_similar(query: str, documents: List[str], 
                   top_k: int = 5, model_key: str = "default") -> List[tuple]:
    """Quick function for similarity search."""
    manager = get_embedding_manager(model_key)
    return manager.search_similar(query, documents, top_k)
