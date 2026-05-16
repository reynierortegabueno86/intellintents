from typing import Dict, Any, Optional

from app.classifiers.base import BaseClassifier
from app.classifiers.rule_based import RuleBasedClassifier
from app.classifiers.embedding_classifier import EmbeddingSimilarityClassifier
from app.classifiers.zero_shot import ZeroShotClassifier
from app.classifiers.hybrid import HybridClassifier
from app.classifiers.transformer_classifier import TransformerClassifier
from app.classifiers.llm_fewshot_classifier import LLMFewShotClassifier
from app.classifiers.cascading_classifier import CascadingClassifier
from app.classifiers.context_cascading_classifier import ContextCascadingClassifier
from app.classifiers.base import TurnInfo

# ---------------------------------------------------------------------------
# Fallback / complementary labels — valid classifier outputs that do not need
# to match any taxonomy category.  These represent cases where the input does
# not match any defined class.
# ---------------------------------------------------------------------------
FALLBACK_LABELS = frozenset({
    "UNKNOWN",
    "Unknown",
    "unknown",
    "NONE",
    "None",
    "none",
    "NULL",
    "null",
    "EMPTY",
    "empty",
    "",
})


def is_fallback_label(label: str) -> bool:
    """Return True if *label* is a complementary/fallback class.

    Recognises exact matches (UNKNOWN, None, null, empty, …) as well as
    patterns like ``CATEGORY/UNKNOWN_SUBCATEGORY``.
    """
    if label in FALLBACK_LABELS:
        return True
    if "UNKNOWN" in label.upper():
        return True
    return False


def get_classifier(method: str, config: Optional[Dict[str, Any]] = None) -> BaseClassifier:
    """Return a classifier instance for the given method name."""
    config = config or {}
    if method == "rule_based":
        keyword_map = config.get("keyword_map")
        return RuleBasedClassifier(keyword_map=keyword_map)
    elif method == "embedding":
        return EmbeddingSimilarityClassifier()
    elif method == "zero_shot":
        return ZeroShotClassifier(
            provider=config.get("provider", "openai"),
            model=config.get("model", "gpt-4o-mini"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 256),
            system_prompt=config.get("system_prompt"),
            batch_size=config.get("batch_size", 1),
        )
    elif method == "hybrid":
        rule_weight = config.get("rule_weight", 0.4)
        embedding_weight = config.get("embedding_weight", 0.6)
        return HybridClassifier(
            rule_weight=rule_weight, embedding_weight=embedding_weight
        )
    elif method == "transformer":
        return TransformerClassifier(
            model_name=config.get("model_name", "facebook/bart-large-mnli"),
            mode=config.get("mode", "zero_shot_nli"),
            device=config.get("device", "cpu"),
            batch_size=config.get("batch_size", 16),
            max_length=config.get("max_length", 512),
            hypothesis_template=config.get("hypothesis_template", "This text is about {}."),
            multi_label=config.get("multi_label", False),
            label_map=config.get("label_map"),
            confidence_threshold=config.get("confidence_threshold", 0.0),
        )
    elif method == "llm_fewshot":
        return LLMFewShotClassifier(
            provider=config.get("provider", "openai"),
            model=config.get("model", "gpt-4o-mini"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.1),
            max_tokens=config.get("max_tokens", 256),
            num_examples=config.get("num_examples", 2),
            system_prompt=config.get("system_prompt"),
            examples=config.get("examples"),
            batch_size=config.get("batch_size", 1),
        )
    elif method == "cascading":
        return CascadingClassifier(
            provider=config.get("provider", "openai"),
            model=config.get("model", "gpt-5.2"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 200),
            stage1_threshold=config.get("stage1_threshold", 0.60),
            stage2_threshold=config.get("stage2_threshold", 0.65),
            stage1_model=config.get("stage1_model"),
            stage2_model=config.get("stage2_model"),
            max_concurrency=config.get("max_concurrency", 5),
        )
    elif method == "cascading_context":
        return ContextCascadingClassifier(
            provider=config.get("provider", "openai"),
            model=config.get("model", "gpt-5.2"),
            api_key=config.get("api_key"),
            base_url=config.get("base_url"),
            temperature=config.get("temperature", 0.0),
            max_tokens=config.get("max_tokens", 250),
            stage1_threshold=config.get("stage1_threshold", 0.60),
            stage2_threshold=config.get("stage2_threshold", 0.65),
            stage1_model=config.get("stage1_model"),
            stage2_model=config.get("stage2_model"),
            max_concurrency=config.get("max_concurrency", 5),
            context_backward=config.get("context_backward", 2),
            context_forward=config.get("context_forward", 1),
            context_max_chars=config.get("context_max_chars", 500),
            use_previous_labels=config.get("use_previous_labels", False) in (True, "true", "True"),
        )
    else:
        raise ValueError(f"Unknown classification method: {method}")


def _group_turns_by_conversation(turns: list) -> Dict[int, list]:
    """Group Turn ORM objects into {conversation_id: [TurnInfo, ...]} sorted by turn_index."""
    from collections import defaultdict
    groups: Dict[int, list] = defaultdict(list)
    for t in turns:
        groups[t.conversation_id].append(
            TurnInfo(
                text=t.text,
                speaker=t.speaker,
                turn_index=t.turn_index,
                conversation_id=t.conversation_id,
            )
        )
    # Ensure each conversation's turns are sorted by turn_index
    for conv_id in groups:
        groups[conv_id].sort(key=lambda ti: ti.turn_index)
    return dict(groups)
