import math
from collections import Counter, defaultdict
from typing import Any, Dict, List, Optional

from sqlalchemy import func, select, union_all
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Classification, Conversation, Run, RunClassification, Turn,
)


def _classification_query(dataset_id: int, taxonomy_id: int):
    """Build a unified query across Classification and RunClassification tables.

    Returns rows of (conversation_id, turn_id, turn_index, speaker, intent_label, confidence)
    from both direct classifications and the latest completed experiment run.
    """
    # Direct classifications (from /classify endpoint)
    direct = (
        select(
            Turn.conversation_id,
            Turn.id.label("turn_id"),
            Turn.turn_index,
            Turn.speaker,
            Classification.intent_label,
            Classification.confidence,
        )
        .join(Classification, Classification.turn_id == Turn.id)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(
            Conversation.dataset_id == dataset_id,
            Classification.taxonomy_id == taxonomy_id,
        )
    )

    # Run classifications (from experiment runs) — uses latest completed run
    # for the given dataset+taxonomy via the experiment's config
    from app.models.models import Experiment
    run_cls = (
        select(
            RunClassification.conversation_id,
            RunClassification.turn_id,
            Turn.turn_index,
            RunClassification.speaker,
            RunClassification.intent_label,
            RunClassification.confidence,
        )
        .join(Run, RunClassification.run_id == Run.id)
        .join(Experiment, Run.experiment_id == Experiment.id)
        .join(Turn, RunClassification.turn_id == Turn.id)
        .where(
            Experiment.dataset_id == dataset_id,
            Experiment.taxonomy_id == taxonomy_id,
            Run.status == "completed",
        )
    )

    return union_all(direct, run_cls)


async def get_summary_metrics(
    db: AsyncSession,
    dataset_id: int,
) -> Dict[str, Any]:
    """Summary metrics for a dataset."""
    conv_count = await db.scalar(
        select(func.count(Conversation.id)).where(
            Conversation.dataset_id == dataset_id
        )
    )
    turn_count = await db.scalar(
        select(func.count(Turn.id))
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(Conversation.dataset_id == dataset_id)
    )
    avg_turns = await db.scalar(
        select(func.avg(Conversation.turn_count)).where(
            Conversation.dataset_id == dataset_id
        )
    )

    # Unique intents and entropy from classifications (both direct and run-based)
    # Use all taxonomies for this dataset in the summary
    cls_result = await db.execute(
        select(Classification.intent_label)
        .join(Turn, Classification.turn_id == Turn.id)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(Conversation.dataset_id == dataset_id)
    )
    labels = [row[0] for row in cls_result.all()]

    # Also include labels from experiment run classifications
    from app.models.models import Experiment, RunClassification, Run
    run_cls_result = await db.execute(
        select(RunClassification.intent_label)
        .join(Run, RunClassification.run_id == Run.id)
        .join(Experiment, Run.experiment_id == Experiment.id)
        .where(
            Experiment.dataset_id == dataset_id,
            Run.status == "completed",
        )
    )
    labels.extend(row[0] for row in run_cls_result.all())
    unique_intents = len(set(labels)) if labels else 0

    # Shannon entropy
    entropy = 0.0
    if labels:
        total = len(labels)
        counts = Counter(labels)
        for count in counts.values():
            p = count / total
            if p > 0:
                entropy -= p * math.log2(p)

    return {
        "total_conversations": conv_count or 0,
        "total_turns": turn_count or 0,
        "avg_turns_per_conversation": round(float(avg_turns or 0), 2),
        "unique_intents": unique_intents,
        "intent_entropy": round(entropy, 4),
    }


async def get_intent_distribution(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """Intent distribution with counts and percentages."""
    unified = _classification_query(dataset_id, taxonomy_id).subquery()

    query = (
        select(unified.c.intent_label, func.count())
        .select_from(unified)
    )
    if intent_labels:
        query = query.where(unified.c.intent_label.in_(intent_labels))
    if min_confidence is not None:
        query = query.where(unified.c.confidence >= min_confidence)

    query = query.group_by(unified.c.intent_label)
    result = await db.execute(query)
    rows = result.all()

    total = sum(r[1] for r in rows)
    distribution = []
    for label, count in rows:
        distribution.append({
            "intent": label,
            "count": count,
            "percentage": round(count / total * 100, 2) if total > 0 else 0.0,
        })
    distribution.sort(key=lambda x: x["count"], reverse=True)
    return distribution


async def get_intent_transitions(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Compute intent transitions: consecutive turns in the same conversation.
    """
    # Fetch all classified turns ordered by conversation and turn_index
    unified = _classification_query(dataset_id, taxonomy_id).subquery()

    query = (
        select(unified.c.conversation_id, unified.c.turn_index, unified.c.intent_label)
        .select_from(unified)
    )
    if min_confidence is not None:
        query = query.where(unified.c.confidence >= min_confidence)

    query = query.order_by(unified.c.conversation_id, unified.c.turn_index)
    result = await db.execute(query)
    rows = result.all()

    if intent_labels:
        rows = [r for r in rows if r[2] in intent_labels]

    # Group by conversation
    convs: Dict[int, List] = defaultdict(list)
    for conv_id, turn_idx, label in rows:
        convs[conv_id].append(label)

    transition_counts: Counter = Counter()
    from_counts: Counter = Counter()
    for labels in convs.values():
        for i in range(len(labels) - 1):
            pair = (labels[i], labels[i + 1])
            transition_counts[pair] += 1
            from_counts[labels[i]] += 1

    transitions = []
    for (from_i, to_i), count in transition_counts.items():
        prob = count / from_counts[from_i] if from_counts[from_i] > 0 else 0.0
        transitions.append({
            "from_intent": from_i,
            "to_intent": to_i,
            "count": count,
            "probability": round(prob, 4),
        })
    transitions.sort(key=lambda x: x["count"], reverse=True)
    return transitions


async def get_intent_heatmap(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    max_turns: Optional[int] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Heatmap data: count of each intent at each turn_index.
    """
    unified = _classification_query(dataset_id, taxonomy_id).subquery()

    query = (
        select(
            unified.c.turn_index,
            unified.c.intent_label,
            func.count(),
        )
        .select_from(unified)
    )
    if min_confidence is not None:
        query = query.where(unified.c.confidence >= min_confidence)
    if max_turns is not None:
        query = query.where(unified.c.turn_index < max_turns)

    query = query.group_by(unified.c.turn_index, unified.c.intent_label)
    result = await db.execute(query)
    rows = result.all()

    heatmap = []
    for turn_index, intent, count in rows:
        heatmap.append({
            "turn_index": turn_index,
            "intent": intent,
            "count": count,
        })
    return heatmap


async def get_intent_timeline(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Time-based intent data. Groups by conversation created_at date bucket.
    """
    # Timeline needs conversation created_at, so we join back to Conversation
    unified = _classification_query(dataset_id, taxonomy_id).subquery()

    query = (
        select(
            func.date(Conversation.created_at).label("date_bucket"),
            unified.c.intent_label,
            func.count(),
        )
        .select_from(unified)
        .join(Conversation, unified.c.conversation_id == Conversation.id)
    )
    if intent_labels:
        query = query.where(unified.c.intent_label.in_(intent_labels))
    if min_confidence is not None:
        query = query.where(unified.c.confidence >= min_confidence)

    query = query.group_by("date_bucket", unified.c.intent_label)
    result = await db.execute(query)
    rows = result.all()

    timeline = []
    for date_bucket, intent, count in rows:
        timeline.append({
            "time_bucket": str(date_bucket),
            "intent": intent,
            "count": count,
        })
    return timeline


async def get_conversation_archetypes(
    db: AsyncSession,
    dataset_id: int,
    taxonomy_id: int,
    min_turns: Optional[int] = None,
    max_turns: Optional[int] = None,
    min_confidence: Optional[float] = None,
) -> List[Dict[str, Any]]:
    """
    Cluster conversations by their intent sequence patterns.
    An archetype is a unique ordered sequence of intents.
    """
    unified = _classification_query(dataset_id, taxonomy_id).subquery()

    query = (
        select(
            unified.c.conversation_id,
            unified.c.turn_index,
            unified.c.intent_label,
        )
        .select_from(unified)
    )
    if min_confidence is not None:
        query = query.where(unified.c.confidence >= min_confidence)

    query = query.order_by(unified.c.conversation_id, unified.c.turn_index)
    result = await db.execute(query)
    rows = result.all()

    # Build sequences per conversation
    conv_sequences: Dict[int, List[str]] = defaultdict(list)
    for conv_id, _, label in rows:
        conv_sequences[conv_id].append(label)

    # Filter by turn counts
    if min_turns is not None:
        conv_sequences = {
            k: v for k, v in conv_sequences.items() if len(v) >= min_turns
        }
    if max_turns is not None:
        conv_sequences = {
            k: v for k, v in conv_sequences.items() if len(v) <= max_turns
        }

    # Group by pattern
    pattern_groups: Dict[tuple, List[int]] = defaultdict(list)
    for conv_id, seq in conv_sequences.items():
        pattern_groups[tuple(seq)].append(conv_id)

    archetypes = []
    for i, (pattern, conv_ids) in enumerate(
        sorted(pattern_groups.items(), key=lambda x: len(x[1]), reverse=True)
    ):
        archetypes.append({
            "archetype_id": i,
            "pattern": list(pattern),
            "count": len(conv_ids),
            "example_conversation_ids": conv_ids[:5],
        })

    return archetypes


async def get_conversation_graph(
    db: AsyncSession,
    conversation_id: int,
) -> Dict[str, Any]:
    """
    Build a graph representation of a conversation for visualization.
    Nodes: turns and their classified intents.
    Edges: sequential turn connections and turn-to-intent links.
    """
    # Get turns
    turns_result = await db.execute(
        select(Turn)
        .where(Turn.conversation_id == conversation_id)
        .order_by(Turn.turn_index)
    )
    turns = turns_result.scalars().all()

    if not turns:
        return {"nodes": [], "edges": []}

    # Get classifications for these turns (from both tables)
    turn_ids = [t.id for t in turns]
    cls_result = await db.execute(
        select(Classification).where(Classification.turn_id.in_(turn_ids))
    )
    classifications = list(cls_result.scalars().all())

    # Also check run_classifications if no direct classifications
    if not classifications:
        run_cls_result = await db.execute(
            select(RunClassification)
            .join(Run, RunClassification.run_id == Run.id)
            .where(
                RunClassification.turn_id.in_(turn_ids),
                Run.status == "completed",
            )
        )
        classifications = list(run_cls_result.scalars().all())

    cls_by_turn: Dict[int, List] = defaultdict(list)
    for cls in classifications:
        cls_by_turn[cls.turn_id].append(cls)

    nodes = []
    edges = []
    intent_nodes_added = set()

    for turn in turns:
        turn_node_id = f"turn_{turn.id}"
        nodes.append({
            "id": turn_node_id,
            "label": f"T{turn.turn_index}: {turn.speaker}",
            "type": "turn",
            "metadata": {
                "text": turn.text[:100],
                "speaker": turn.speaker,
                "turn_index": turn.turn_index,
            },
        })

        # Intent nodes and edges
        for cls in cls_by_turn.get(turn.id, []):
            intent_node_id = f"intent_{cls.intent_label}"
            if intent_node_id not in intent_nodes_added:
                nodes.append({
                    "id": intent_node_id,
                    "label": cls.intent_label,
                    "type": "intent",
                    "metadata": {},
                })
                intent_nodes_added.add(intent_node_id)

            edges.append({
                "source": turn_node_id,
                "target": intent_node_id,
                "label": f"{cls.confidence:.2f}",
                "weight": cls.confidence,
            })

    # Sequential edges between turns
    for i in range(len(turns) - 1):
        edges.append({
            "source": f"turn_{turns[i].id}",
            "target": f"turn_{turns[i + 1].id}",
            "label": "next",
            "weight": 1.0,
        })

    return {"nodes": nodes, "edges": edges}
