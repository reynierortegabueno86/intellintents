"""Turn search and filter service."""
import math
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, literal_column, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Conversation, Run, RunClassification, Turn
from app.services.analytics_service import _classification_query


def _run_classification_subquery(run_id: int):
    """Build a subquery for classifications from a specific run."""
    return (
        select(
            RunClassification.turn_id,
            RunClassification.intent_label,
            RunClassification.confidence,
        )
        .where(RunClassification.run_id == run_id)
    )


async def get_filter_options(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: Optional[int] = None,
    run_id: Optional[int] = None,
) -> Dict[str, Any]:
    """Return distinct values for filter dropdowns."""
    # Distinct speakers
    speaker_q = await db.execute(
        select(Turn.speaker)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(Conversation.dataset_id == dataset_id)
        .distinct()
    )
    speakers = sorted([r[0] for r in speaker_q.all()])

    # Distinct ground truth intents
    gt_q = await db.execute(
        select(Turn.ground_truth_intent)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(
            Conversation.dataset_id == dataset_id,
            Turn.ground_truth_intent.isnot(None),
        )
        .distinct()
    )
    ground_truth_intents = sorted([r[0] for r in gt_q.all()])

    # Classification-based options (intent labels, confidence range)
    intent_labels = []
    confidence_range = {"min": 0.0, "max": 1.0}

    if run_id is not None:
        # Specific run — use RunClassification directly
        rc_sub = _run_classification_subquery(run_id).subquery()
        label_q = await db.execute(
            select(rc_sub.c.intent_label).select_from(rc_sub).distinct()
        )
        intent_labels = sorted([r[0] for r in label_q.all()])

        conf_q = await db.execute(
            select(
                func.min(rc_sub.c.confidence),
                func.max(rc_sub.c.confidence),
            ).select_from(rc_sub)
        )
        row = conf_q.one_or_none()
        if row and row[0] is not None:
            confidence_range = {
                "min": round(float(row[0]), 4),
                "max": round(float(row[1]), 4),
            }
    elif taxonomy_id is not None:
        unified = _classification_query(dataset_id, taxonomy_id).subquery()
        label_q = await db.execute(
            select(unified.c.intent_label).select_from(unified).distinct()
        )
        intent_labels = sorted([r[0] for r in label_q.all()])

        conf_q = await db.execute(
            select(
                func.min(unified.c.confidence),
                func.max(unified.c.confidence),
            ).select_from(unified)
        )
        row = conf_q.one_or_none()
        if row and row[0] is not None:
            confidence_range = {
                "min": round(float(row[0]), 4),
                "max": round(float(row[1]), 4),
            }

    return {
        "speakers": speakers,
        "intent_labels": intent_labels,
        "ground_truth_intents": ground_truth_intents,
        "confidence_range": confidence_range,
    }


async def search_turns(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: Optional[int] = None,
    run_id: Optional[int] = None,
    keyword: Optional[str] = None,
    speaker: Optional[str] = None,
    intent_labels: Optional[List[str]] = None,
    min_confidence: Optional[float] = None,
    max_confidence: Optional[float] = None,
    ground_truth_intent: Optional[str] = None,
    page: int = 1,
    page_size: int = 50,
) -> Dict[str, Any]:
    """Search and filter turns across a dataset with optional classification data."""

    has_classifications = False

    if run_id is not None:
        # Specific run — clean, unambiguous labels
        unified = _run_classification_subquery(run_id).subquery("unified")
        has_classifications = True

        base = (
            select(
                Turn.id.label("turn_id"),
                Turn.conversation_id,
                Conversation.external_id.label("conversation_external_id"),
                Turn.turn_index,
                Turn.speaker,
                Turn.text,
                Turn.ground_truth_intent,
                unified.c.intent_label,
                unified.c.confidence,
            )
            .join(Conversation, Turn.conversation_id == Conversation.id)
            .outerjoin(unified, unified.c.turn_id == Turn.id)
            .where(Conversation.dataset_id == dataset_id)
        )
    elif taxonomy_id is not None:
        has_classifications = True
        # Build unified classification subquery, then deduplicate by keeping
        # the highest-confidence classification per turn
        raw_unified = _classification_query(dataset_id, taxonomy_id).subquery()
        max_conf = (
            select(
                raw_unified.c.turn_id,
                func.max(raw_unified.c.confidence).label("max_conf"),
            )
            .select_from(raw_unified)
            .group_by(raw_unified.c.turn_id)
        ).subquery("max_conf_sq")

        unified = (
            select(
                raw_unified.c.turn_id,
                raw_unified.c.intent_label,
                raw_unified.c.confidence,
            )
            .select_from(raw_unified)
            .join(max_conf, and_(
                raw_unified.c.turn_id == max_conf.c.turn_id,
                raw_unified.c.confidence == max_conf.c.max_conf,
            ))
            .distinct()
        ).subquery("unified")

        # Use outerjoin so turns without classifications still appear
        base = (
            select(
                Turn.id.label("turn_id"),
                Turn.conversation_id,
                Conversation.external_id.label("conversation_external_id"),
                Turn.turn_index,
                Turn.speaker,
                Turn.text,
                Turn.ground_truth_intent,
                unified.c.intent_label,
                unified.c.confidence,
            )
            .join(Conversation, Turn.conversation_id == Conversation.id)
            .outerjoin(unified, unified.c.turn_id == Turn.id)
            .where(Conversation.dataset_id == dataset_id)
        )
    else:
        base = (
            select(
                Turn.id.label("turn_id"),
                Turn.conversation_id,
                Conversation.external_id.label("conversation_external_id"),
                Turn.turn_index,
                Turn.speaker,
                Turn.text,
                Turn.ground_truth_intent,
                literal_column("NULL").label("intent_label"),
                literal_column("NULL").label("confidence"),
            )
            .join(Conversation, Turn.conversation_id == Conversation.id)
            .where(Conversation.dataset_id == dataset_id)
        )

    # Apply filters
    if keyword:
        base = base.where(Turn.text.ilike(f"%{keyword}%"))
    if speaker:
        base = base.where(Turn.speaker == speaker)
    if ground_truth_intent:
        base = base.where(Turn.ground_truth_intent == ground_truth_intent)
    if intent_labels and has_classifications:
        base = base.where(unified.c.intent_label.in_(intent_labels))
    if min_confidence is not None and has_classifications:
        base = base.where(unified.c.confidence >= min_confidence)
    if max_confidence is not None and has_classifications:
        base = base.where(unified.c.confidence <= max_confidence)

    # Count total
    count_q = select(func.count()).select_from(base.subquery())
    total = await db.scalar(count_q) or 0

    # Paginated results
    results_q = (
        base.order_by(Turn.conversation_id, Turn.turn_index)
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(results_q)
    rows = result.all()

    results = []
    for row in rows:
        results.append({
            "turn_id": row.turn_id,
            "conversation_id": row.conversation_id,
            "conversation_external_id": row.conversation_external_id,
            "turn_index": row.turn_index,
            "speaker": row.speaker,
            "text": row.text,
            "ground_truth_intent": row.ground_truth_intent,
            "intent_label": row.intent_label,
            "confidence": round(float(row.confidence), 4) if row.confidence is not None else None,
        })

    total_pages = math.ceil(total / page_size) if total > 0 else 1

    return {
        "results": results,
        "total": total,
        "page": page,
        "page_size": page_size,
        "total_pages": total_pages,
    }
