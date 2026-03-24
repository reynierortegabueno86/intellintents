from typing import List, Dict, Any, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.classifiers.base import ClassifierConfigError
from app.models.models import (
    Classification,
    Conversation,
    IntentCategory,
    IntentTaxonomy,
    Turn,
)
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


async def classify_dataset(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    method: str,
    config: Optional[Dict[str, Any]] = None,
) -> List[Classification]:
    """
    Classify all turns in a dataset using the specified method and taxonomy.
    Returns the list of created Classification objects.
    """
    # Load taxonomy categories
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if not taxonomy:
        raise ValueError(f"Taxonomy {taxonomy_id} not found")

    cats_result = await db.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == taxonomy_id)
    )
    categories = cats_result.scalars().all()
    if not categories:
        raise ValueError(f"Taxonomy {taxonomy_id} has no categories")

    taxonomy_categories = [
        {"name": c.name, "description": c.description or ""} for c in categories
    ]

    # Load all turns for the dataset
    turns_result = await db.execute(
        select(Turn)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(Conversation.dataset_id == dataset_id)
        .order_by(Turn.id)
    )
    turns = turns_result.scalars().all()
    if not turns:
        raise ValueError(f"No turns found for dataset {dataset_id}")

    # Validate config is a dict if provided
    if config is not None and not isinstance(config, dict):
        raise ValueError("config must be a JSON object (dict)")

    # Delete existing classifications for this dataset/taxonomy/method
    existing = await db.execute(
        select(Classification)
        .where(
            Classification.turn_id.in_([t.id for t in turns]),
            Classification.taxonomy_id == taxonomy_id,
            Classification.method == method,
        )
    )
    for cls in existing.scalars().all():
        await db.delete(cls)
    await db.flush()

    # Classify — fail fast on config errors (missing API key, missing package)
    try:
        classifier = get_classifier(method, config)
    except ClassifierConfigError as e:
        raise ValueError(f"Classifier configuration error: {e}")

    try:
        if hasattr(classifier, 'classify_conversation_batch'):
            conversations = _group_turns_by_conversation(turns)
            import asyncio
            loop = asyncio.get_event_loop()
            conv_results = await loop.run_in_executor(
                None, classifier.classify_conversation_batch,
                conversations, taxonomy_categories,
            )
            # Build a lookup: (conversation_id, turn_index) → result
            result_lookup: Dict[tuple, Any] = {}
            for conv_id, conv_result_list in conv_results.items():
                conv_turns = conversations[conv_id]
                for ti, res in zip(conv_turns, conv_result_list):
                    result_lookup[(ti.conversation_id, ti.turn_index)] = res
            # Map back to original turn order
            results = [
                result_lookup.get(
                    (t.conversation_id, t.turn_index),
                    ("UNKNOWN", 0.0, "Missing result"),
                )
                for t in turns
            ]
        else:
            turn_texts = [t.text for t in turns]
            results = classifier.classify_batch(turn_texts, taxonomy_categories)
    except ClassifierConfigError as e:
        raise ValueError(f"Classifier configuration error: {e}")

    classifications: List[Classification] = []
    for turn, (label, confidence, explanation) in zip(turns, results):
        cls = Classification(
            turn_id=turn.id,
            taxonomy_id=taxonomy_id,
            intent_label=label,
            confidence=confidence,
            method=method,
            explanation=explanation,
        )
        db.add(cls)
        classifications.append(cls)

    await db.commit()
    return classifications


async def get_classification_results(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
) -> List[Dict[str, Any]]:
    """Get classification results for a dataset and taxonomy, grouped by conversation."""
    result = await db.execute(
        select(Turn, Classification, Conversation.external_id)
        .join(Classification, Classification.turn_id == Turn.id)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(
            Conversation.dataset_id == dataset_id,
            Classification.taxonomy_id == taxonomy_id,
        )
        .order_by(Conversation.id, Turn.turn_index)
    )
    rows = result.all()

    # Group by conversation
    conversations: Dict[int, Dict[str, Any]] = {}
    for turn, cls, external_id in rows:
        conv_id = turn.conversation_id
        if conv_id not in conversations:
            conversations[conv_id] = {
                "conversation_id": conv_id,
                "external_id": external_id,
                "turns": [],
            }
        conversations[conv_id]["turns"].append({
            "turn_id": turn.id,
            "turn_index": turn.turn_index,
            "speaker": turn.speaker,
            "text": turn.text,
            "intent_label": cls.intent_label,
            "confidence": cls.confidence,
            "method": cls.method,
            "explanation": cls.explanation,
        })

    return list(conversations.values())
