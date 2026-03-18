from typing import List, Tuple, Dict, Any

from app.classifiers.base import BaseClassifier


# Default keyword map: maps category names to lists of keywords.
# Users can override or extend this via config.
DEFAULT_KEYWORD_MAP: Dict[str, List[str]] = {
    "Greeting": [
        "hello", "hi", "hey", "good morning", "good afternoon", "good evening",
        "greetings", "howdy", "what's up", "how are you",
    ],
    "Information Request": [
        "how do i", "how can i", "what is", "where is", "tell me", "explain",
        "information", "details", "wondering", "could you tell", "need to know",
        "question", "can you explain", "looking for",
    ],
    "Technical Problem": [
        "error", "crash", "bug", "broken", "not working", "fails", "issue",
        "problem", "exception", "timeout", "slow", "freeze", "stuck",
        "can't connect", "unable to", "doesn't work",
    ],
    "Bug Report": [
        "bug", "defect", "regression", "unexpected behavior", "reproduce",
        "steps to reproduce", "expected", "actual", "found a bug",
    ],
    "Purchase Intent": [
        "buy", "purchase", "pricing", "cost", "plan", "subscribe", "upgrade",
        "price", "payment", "checkout", "order", "discount", "trial",
    ],
    "Cancellation": [
        "cancel", "unsubscribe", "stop", "terminate", "end subscription",
        "close account", "delete account", "opt out", "remove",
    ],
    "Complaint": [
        "unhappy", "disappointed", "terrible", "awful", "worst", "frustrated",
        "unacceptable", "poor", "bad experience", "complaint", "dissatisfied",
        "angry", "ridiculous",
    ],
    "Feedback": [
        "suggest", "feedback", "improve", "recommendation", "feature request",
        "would be nice", "love it", "great", "awesome", "well done",
        "suggestion", "opinion",
    ],
    "Configuration Help": [
        "configure", "setup", "setting", "install", "integration", "config",
        "how to set up", "deployment", "environment", "api key", "credentials",
    ],
    "Account Issue": [
        "login", "password", "reset", "locked out", "access", "permission",
        "account", "sign in", "authentication", "two factor", "mfa", "2fa",
        "forgot password", "can't log in",
    ],
}


class RuleBasedClassifier(BaseClassifier):
    """
    Classifies turns by matching keywords from category names/descriptions
    against the turn text. Scores are based on keyword overlap count.
    """

    def __init__(self, keyword_map: Dict[str, List[str]] | None = None):
        self.keyword_map = keyword_map or DEFAULT_KEYWORD_MAP

    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        text_lower = text.lower()
        scores: Dict[str, float] = {}
        matched_keywords: Dict[str, List[str]] = {}

        for cat in taxonomy_categories:
            cat_name = cat["name"]
            keywords = self._get_keywords(cat)
            hits = [kw for kw in keywords if kw.lower() in text_lower]
            score = len(hits)
            # Bonus for exact category-name substring match
            if cat_name.lower() in text_lower:
                score += 2
            scores[cat_name] = score
            matched_keywords[cat_name] = hits

        if not scores or max(scores.values()) == 0:
            # No match: default to the first category with low confidence
            fallback = taxonomy_categories[0]["name"] if taxonomy_categories else "Unknown"
            return (fallback, 0.1, "No keyword matches found; assigned default category.")

        best_label = max(scores, key=scores.get)  # type: ignore[arg-type]
        total = sum(scores.values())
        confidence = round(min(scores[best_label] / max(total, 1), 1.0), 4)
        # Boost confidence floor to make results more useful
        confidence = max(confidence, 0.3) if scores[best_label] > 0 else confidence

        explanation = (
            f"Matched keywords: {matched_keywords[best_label]} "
            f"(score {scores[best_label]:.1f}/{total:.1f})"
        )
        return (best_label, confidence, explanation)

    def _get_keywords(self, category: Dict[str, Any]) -> List[str]:
        """Build keyword list from the configured map, category name and description."""
        cat_name = category["name"]
        keywords: List[str] = list(self.keyword_map.get(cat_name, []))
        # Also add individual words from category name and description
        keywords.extend(cat_name.lower().split())
        desc = category.get("description", "") or ""
        if desc:
            keywords.extend(w.lower() for w in desc.split() if len(w) > 3)
        return list(set(keywords))
