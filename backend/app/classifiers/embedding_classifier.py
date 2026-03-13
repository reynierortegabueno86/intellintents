from typing import List, Tuple, Dict, Any

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.classifiers.base import BaseClassifier


class EmbeddingSimilarityClassifier(BaseClassifier):
    """
    Classifies turns by computing TF-IDF vectors for the turn text and
    category descriptions, then selecting the category with the highest
    cosine similarity.
    """

    def __init__(self):
        self.vectorizer = TfidfVectorizer(
            stop_words="english",
            max_features=5000,
            ngram_range=(1, 2),
        )

    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        results = self.classify_batch([text], taxonomy_categories)
        return results[0]

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        if not taxonomy_categories:
            return [("Unknown", 0.0, "No categories available")] * len(turns)

        # Build category documents from name + description
        cat_docs = []
        cat_names = []
        for cat in taxonomy_categories:
            doc = cat["name"]
            desc = cat.get("description", "") or ""
            if desc:
                doc = f"{doc} {desc}"
            cat_docs.append(doc)
            cat_names.append(cat["name"])

        # Fit vectorizer on all documents (categories + turns)
        all_docs = cat_docs + turns
        tfidf_matrix = self.vectorizer.fit_transform(all_docs)

        cat_vectors = tfidf_matrix[: len(cat_docs)]
        turn_vectors = tfidf_matrix[len(cat_docs) :]

        # Compute cosine similarities: turns x categories
        similarities = cosine_similarity(turn_vectors, cat_vectors)

        results: List[Tuple[str, float, str]] = []
        for i, sim_row in enumerate(similarities):
            best_idx = int(np.argmax(sim_row))
            confidence = float(round(sim_row[best_idx], 4))
            # Ensure minimum confidence floor
            confidence = max(confidence, 0.05)

            top_3_indices = np.argsort(sim_row)[-3:][::-1]
            top_3 = [
                f"{cat_names[j]} ({sim_row[j]:.3f})" for j in top_3_indices
            ]
            explanation = f"TF-IDF cosine similarity. Top matches: {', '.join(top_3)}"
            results.append((cat_names[best_idx], confidence, explanation))

        return results
