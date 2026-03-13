from abc import ABC, abstractmethod
from typing import List, Tuple, Dict, Any, NamedTuple


class TurnInfo(NamedTuple):
    """Lightweight container for a single conversation turn with metadata."""
    text: str
    speaker: str
    turn_index: int
    conversation_id: int


class ClassifierConfigError(Exception):
    """Raised for configuration errors that prevent the classifier from working.

    Examples: missing API key, missing required package, invalid provider.
    These should NOT be caught silently — they indicate the classifier cannot
    operate at all and must be fixed before running.
    """


class BaseClassifier(ABC):
    """Abstract base class for intent classifiers."""

    @abstractmethod
    def classify_turn(
        self,
        text: str,
        taxonomy_categories: List[Dict[str, Any]],
    ) -> Tuple[str, float, str]:
        """
        Classify a single turn of text.

        Args:
            text: The turn text to classify.
            taxonomy_categories: List of dicts with keys 'name' and 'description'.

        Returns:
            Tuple of (label, confidence, explanation).
        """
        ...

    def classify_batch(
        self,
        turns: List[str],
        taxonomy_categories: List[Dict[str, Any]],
    ) -> List[Tuple[str, float, str]]:
        """
        Classify a batch of turns. Default implementation calls classify_turn
        for each item. Subclasses may override for optimized batch processing.

        Args:
            turns: List of turn texts.
            taxonomy_categories: List of dicts with keys 'name' and 'description'.

        Returns:
            List of (label, confidence, explanation) tuples.
        """
        return [self.classify_turn(text, taxonomy_categories) for text in turns]
