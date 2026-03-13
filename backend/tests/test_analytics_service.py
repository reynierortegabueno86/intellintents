"""Tests for analytics service functions."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Classification,
    Conversation,
    Dataset,
    IntentCategory,
    IntentTaxonomy,
    Turn,
)
from app.services.analytics_service import (
    get_conversation_graph,
    get_intent_distribution,
    get_intent_heatmap,
    get_intent_transitions,
    get_summary_metrics,
)


@pytest_asyncio.fixture
async def analytics_data(db_session: AsyncSession):
    """Seed data for analytics tests."""
    db = db_session

    ds = Dataset(name="Analytics DS", file_type="json", row_count=6)
    db.add(ds)
    await db.flush()

    tax = IntentTaxonomy(name="Analytics Tax")
    db.add(tax)
    await db.flush()

    for name, color in [("Greeting", "#0f0"), ("Complaint", "#f00"), ("Info", "#00f")]:
        db.add(IntentCategory(taxonomy_id=tax.id, name=name, color=color))
    await db.flush()

    # Conv 1: Greeting -> Info -> Complaint
    conv1 = Conversation(dataset_id=ds.id, external_id="c1", turn_count=3)
    db.add(conv1)
    await db.flush()

    turns = []
    for idx, (speaker, text, label, conf) in enumerate([
        ("user", "Hello", "Greeting", 0.95),
        ("agent", "How can I help?", "Info", 0.80),
        ("user", "I'm unhappy", "Complaint", 0.90),
    ]):
        t = Turn(conversation_id=conv1.id, turn_index=idx, speaker=speaker, text=text)
        db.add(t)
        await db.flush()
        turns.append(t)
        db.add(Classification(
            turn_id=t.id, taxonomy_id=tax.id,
            intent_label=label, confidence=conf, method="rule_based",
        ))

    # Conv 2: Greeting -> Greeting
    conv2 = Conversation(dataset_id=ds.id, external_id="c2", turn_count=2)
    db.add(conv2)
    await db.flush()

    for idx, (speaker, text, label, conf) in enumerate([
        ("user", "Hi there", "Greeting", 0.92),
        ("agent", "Hello!", "Greeting", 0.85),
    ]):
        t = Turn(conversation_id=conv2.id, turn_index=idx, speaker=speaker, text=text)
        db.add(t)
        await db.flush()
        turns.append(t)
        db.add(Classification(
            turn_id=t.id, taxonomy_id=tax.id,
            intent_label=label, confidence=conf, method="rule_based",
        ))

    await db.commit()
    return {"ds": ds, "tax": tax, "conv1": conv1, "conv2": conv2, "turns": turns}


@pytest.mark.asyncio
async def test_summary_metrics(db_session, analytics_data):
    """Summary returns correct counts."""
    data = analytics_data
    summary = await get_summary_metrics(db_session, data["ds"].id)
    assert summary["total_conversations"] == 2
    assert summary["total_turns"] == 5
    assert summary["unique_intents"] == 3
    assert summary["intent_entropy"] > 0


@pytest.mark.asyncio
async def test_summary_empty_dataset(db_session):
    """Summary for dataset with no data."""
    db = db_session
    ds = Dataset(name="Empty", file_type="json", row_count=0)
    db.add(ds)
    await db.commit()

    summary = await get_summary_metrics(db_session, ds.id)
    assert summary["total_conversations"] == 0
    assert summary["total_turns"] == 0
    assert summary["intent_entropy"] == 0.0


@pytest.mark.asyncio
async def test_intent_distribution(db_session, analytics_data):
    """Distribution has correct counts and percentages."""
    data = analytics_data
    dist = await get_intent_distribution(db_session, data["ds"].id, data["tax"].id)
    labels = {d["intent"]: d for d in dist}
    assert labels["Greeting"]["count"] == 3  # 3 Greeting turns
    assert labels["Complaint"]["count"] == 1
    assert labels["Info"]["count"] == 1
    total_pct = sum(d["percentage"] for d in dist)
    assert abs(total_pct - 100.0) < 0.1


@pytest.mark.asyncio
async def test_intent_distribution_filtered(db_session, analytics_data):
    """Distribution can be filtered by label."""
    data = analytics_data
    dist = await get_intent_distribution(
        db_session, data["ds"].id, data["tax"].id,
        intent_labels=["Greeting"]
    )
    assert len(dist) == 1
    assert dist[0]["intent"] == "Greeting"


@pytest.mark.asyncio
async def test_intent_transitions(db_session, analytics_data):
    """Transitions capture consecutive intent pairs."""
    data = analytics_data
    transitions = await get_intent_transitions(db_session, data["ds"].id, data["tax"].id)
    pairs = {(t["from_intent"], t["to_intent"]) for t in transitions}
    # Conv1: Greeting->Info, Info->Complaint. Conv2: Greeting->Greeting
    assert ("Greeting", "Info") in pairs
    assert ("Info", "Complaint") in pairs
    assert ("Greeting", "Greeting") in pairs


@pytest.mark.asyncio
async def test_intent_heatmap(db_session, analytics_data):
    """Heatmap returns turn_index x intent counts."""
    data = analytics_data
    heatmap = await get_intent_heatmap(db_session, data["ds"].id, data["tax"].id)
    assert len(heatmap) > 0
    # Turn index 0 should have Greeting counts
    t0_greeting = [h for h in heatmap if h["turn_index"] == 0 and h["intent"] == "Greeting"]
    assert len(t0_greeting) == 1
    assert t0_greeting[0]["count"] == 2  # Both conv1 and conv2


@pytest.mark.asyncio
async def test_heatmap_max_turns(db_session, analytics_data):
    """Heatmap respects max_turns filter."""
    data = analytics_data
    heatmap = await get_intent_heatmap(
        db_session, data["ds"].id, data["tax"].id, max_turns=1
    )
    assert all(h["turn_index"] < 1 for h in heatmap)


@pytest.mark.asyncio
async def test_conversation_graph(db_session, analytics_data):
    """Graph returns nodes and edges for a conversation."""
    data = analytics_data
    graph = await get_conversation_graph(db_session, data["conv1"].id)
    assert len(graph["nodes"]) > 0
    assert len(graph["edges"]) > 0

    turn_nodes = [n for n in graph["nodes"] if n["type"] == "turn"]
    intent_nodes = [n for n in graph["nodes"] if n["type"] == "intent"]
    assert len(turn_nodes) == 3  # 3 turns in conv1
    assert len(intent_nodes) == 3  # Greeting, Info, Complaint


@pytest.mark.asyncio
async def test_conversation_graph_empty(db_session):
    """Graph for nonexistent conversation returns empty."""
    graph = await get_conversation_graph(db_session, 99999)
    assert graph == {"nodes": [], "edges": []}
