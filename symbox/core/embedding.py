import difflib
import math
import os
from typing import Any, Dict, List, Optional, Tuple
from dotenv import load_dotenv
import httpx


class EmbeddingDetector:
    """Embedding similarity detector for Adj threshold checking."""

    def __init__(self, env_file: Optional[str] = None):
        if env_file and os.path.exists(env_file):
            load_dotenv(env_file)
        else:
            load_dotenv()

        self.base_url = os.getenv("EMBEDDING_BASE_URL", "https://api.openai.com/v1").rstrip("/")
        self.api_key = os.getenv("EMBEDDING_API_KEY", "")
        self.model = os.getenv("EMBEDDING_MODEL", "text-embedding-3-small")
        try:
            self.threshold = float(os.getenv("SIMILARITY_THRESHOLD", "0.9"))
        except ValueError:
            self.threshold = 0.9

    def _cosine_similarity(self, vec1: List[float], vec2: List[float]) -> float:
        dot = sum(a * b for a, b in zip(vec1, vec2))
        norm1 = math.sqrt(sum(a * a for a in vec1))
        norm2 = math.sqrt(sum(b * b for b in vec2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)

    def _get_api_embeddings(self, texts: List[str]) -> Optional[List[List[float]]]:
        if not self.api_key or not self.base_url:
            return None
        url = f"{self.base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": self.model,
            "input": texts,
        }
        try:
            with httpx.Client(timeout=3.0) as client:
                resp = client.post(url, json=payload, headers=headers)
                if resp.status_code == 200:
                    data = resp.json()
                    # Expecting data['data'][i]['embedding']
                    embeddings = [item["embedding"] for item in data.get("data", [])]
                    if len(embeddings) == len(texts):
                        return embeddings
        except Exception:
            pass
        return None

    def _string_fallback_similarity(self, s1: str, s2: str) -> float:
        """Fallback string similarity when embedding API is not available."""
        # Check direct antonym / synonym heuristic mappings
        known_opposites = {
            ("fixed", "broken"),
            ("broken", "fixed"),
            ("on", "off"),
            ("off", "on"),
            ("active", "inactive"),
            ("inactive", "active"),
            ("true", "false"),
            ("false", "true"),
            ("open", "closed"),
            ("closed", "open"),
        }
        if (s1.lower(), s2.lower()) in known_opposites:
            return 0.95  # High similarity threshold for opposite state key conflict!

        # Sequence matcher ratio
        ratio = difflib.SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
        return ratio

    def check_threshold(
        self, target_obj: str, proposed_key: str, existing_keys: List[str]
    ) -> Tuple[bool, Optional[Dict[str, Any]]]:
        """Check if proposed_key similarity with existing_keys exceeds threshold.

        Returns (confirm_needed, confirmation_dict).
        """
        if not existing_keys:
            return False, None

        if proposed_key in existing_keys:
            return False, None

        # Try API embeddings first
        texts = [proposed_key] + existing_keys
        embeddings = self._get_api_embeddings(texts)

        max_sim = 0.0
        most_similar_key = None

        if embeddings:
            prop_vec = embeddings[0]
            for key, key_vec in zip(existing_keys, embeddings[1:]):
                sim = self._cosine_similarity(prop_vec, key_vec)
                if sim > max_sim:
                    max_sim = sim
                    most_similar_key = key
        else:
            # Fallback to string similarity
            for key in existing_keys:
                sim = self._string_fallback_similarity(proposed_key, key)
                if sim > max_sim:
                    max_sim = sim
                    most_similar_key = key

        if max_sim >= self.threshold and most_similar_key:
            question = f'"{proposed_key}" 与现有 "{most_similar_key}" 高度相似 ({max_sim:.2f} >= {self.threshold})，是反转还是新增？'
            conf_data = {
                "status": "confirm_needed",
                "question": question,
                "target": target_obj,
                "existing": most_similar_key,
                "proposed": proposed_key,
                "similarity": round(max_sim, 4),
            }
            return True, conf_data

        return False, None
