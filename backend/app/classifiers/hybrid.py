from typing import List, Tuple, Dict, Any

from app.classifiers.base import BaseClassifier
from app.classifiers.rule_based import RuleBasedClassifier
from app.classifiers.embedding_classifier import EmbeddingSimilarityClassifier


class HybridClassifier(BaseClassifier):
    """
    Combines rule-based and embedding classifiers with configurable weights.
    The final label is chosen by weighted confidence; if both agree, the
    confidence is boosted.
    """

    def __init__(
        self,
        rule_weight: float = 0.4,
        embedding_weight: float = 0.6,
    ):
        self.rule_weight = rule_weight
        self.embedding_weight = embedding_weight
        self.rule_classifier = RuleBasedClassifier()
        self.embedding_classifier = EmbeddingSimilarityClassifier()

    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        rule_label, rule_conf, rule_expl = self.rule_classifier.classify_turn(
            text, taxonomy_categories
        )
        emb_label, emb_conf, emb_expl = self.embedding_classifier.classify_turn(
            text, taxonomy_categories
        )

        rule_score = rule_conf * self.rule_weight
        emb_score = emb_conf * self.embedding_weight

        if rule_label == emb_label:
            # Both agree: boost confidence
            final_label = rule_label
            final_conf = min(rule_score + emb_score + 0.1, 1.0)
        elif rule_score >= emb_score:
            final_label = rule_label
            final_conf = rule_score
        else:
            final_label = emb_label
            final_conf = emb_score

        final_conf = round(final_conf, 4)
        explanation = (
            f"Hybrid: rule-based -> {rule_label} ({rule_conf:.3f} * {self.rule_weight}), "
            f"embedding -> {emb_label} ({emb_conf:.3f} * {self.embedding_weight}). "
            f"Selected: {final_label}"
        )
        return (final_label, final_conf, explanation)

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        rule_results = self.rule_classifier.classify_batch(turns, taxonomy_categories)
        emb_results = self.embedding_classifier.classify_batch(turns, taxonomy_categories)

        results: List[Tuple[str, float, str]] = []
        for (r_label, r_conf, r_expl), (e_label, e_conf, e_expl) in zip(
            rule_results, emb_results
        ):
            r_score = r_conf * self.rule_weight
            e_score = e_conf * self.embedding_weight

            if r_label == e_label:
                final_label = r_label
                final_conf = min(r_score + e_score + 0.1, 1.0)
            elif r_score >= e_score:
                final_label = r_label
                final_conf = r_score
            else:
                final_label = e_label
                final_conf = e_score

            final_conf = round(final_conf, 4)
            explanation = (
                f"Hybrid: rule-based -> {r_label} ({r_conf:.3f} * {self.rule_weight}), "
                f"embedding -> {e_label} ({e_conf:.3f} * {self.embedding_weight}). "
                f"Selected: {final_label}"
            )
            results.append((final_label, final_conf, explanation))

        return results
