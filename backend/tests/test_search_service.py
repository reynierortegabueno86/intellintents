"""Tests for the search service (search_turns, get_filter_options)."""

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Classification,
    Conversation,
    Dataset,
    Experiment,
    IntentCategory,
    IntentTaxonomy,
    Run,
    RunClassification,
    Turn,
)
from app.services.search_service import get_filter_options, search_turns


@pytest_asyncio.fixture
async def seed_data(db_session: AsyncSession):
    """Create a dataset with conversations, turns, taxonomy, and classifications."""
    db = db_session

    # Dataset
    ds = Dataset(name="Test DS", file_type="json", row_count=6)
    db.add(ds)
    await db.flush()

    # Taxonomy
    tax = IntentTaxonomy(name="Test Tax")
    db.add(tax)
    await db.flush()

    cat1 = IntentCategory(taxonomy_id=tax.id, name="Greeting", color="#00f")
    cat2 = IntentCategory(taxonomy_id=tax.id, name="Complaint", color="#f00")
    db.add_all([cat1, cat2])
    await db.flush()

    # Conversations and turns
    conv1 = Conversation(dataset_id=ds.id, external_id="conv-001", turn_count=3)
    db.add(conv1)
    await db.flush()

    t1 = Turn(conversation_id=conv1.id, turn_index=0, speaker="user", text="Hello there")
    t2 = Turn(conversation_id=conv1.id, turn_index=1, speaker="agent", text="Hi, how can I help?")
    t3 = Turn(conversation_id=conv1.id, turn_index=2, speaker="user", text="I have a complaint",
              ground_truth_intent="Complaint")
    db.add_all([t1, t2, t3])
    await db.flush()

    conv2 = Conversation(dataset_id=ds.id, external_id="conv-002", turn_count=3)
    db.add(conv2)
    await db.flush()

    t4 = Turn(conversation_id=conv2.id, turn_index=0, speaker="user", text="Good morning")
    t5 = Turn(conversation_id=conv2.id, turn_index=1, speaker="agent", text="Morning!")
    t6 = Turn(conversation_id=conv2.id, turn_index=2, speaker="user", text="Thanks for the help")
    db.add_all([t4, t5, t6])
    await db.flush()

    # Direct classifications
    cls1 = Classification(turn_id=t1.id, taxonomy_id=tax.id, intent_label="Greeting",
                          confidence=0.95, method="rule_based")
    cls2 = Classification(turn_id=t2.id, taxonomy_id=tax.id, intent_label="Greeting",
                          confidence=0.80, method="rule_based")
    cls3 = Classification(turn_id=t3.id, taxonomy_id=tax.id, intent_label="Complaint",
                          confidence=0.90, method="rule_based")
    db.add_all([cls1, cls2, cls3])

    # Experiment + Run + RunClassifications
    exp = Experiment(name="Test Exp", dataset_id=ds.id, taxonomy_id=tax.id,
                     classification_method="rule_based")
    db.add(exp)
    await db.flush()

    run = Run(experiment_id=exp.id, status="completed")
    db.add(run)
    await db.flush()

    for turn, label, conf in [
        (t4, "Greeting", 0.88), (t5, "Greeting", 0.75), (t6, "Greeting", 0.60),
    ]:
        rc = RunClassification(
            run_id=run.id, turn_id=turn.id,
            conversation_id=conv2.id, speaker=turn.speaker,
            text=turn.text,
            intent_label=label, confidence=conf,
        )
        db.add(rc)

    await db.commit()
    return {"ds": ds, "tax": tax, "conv1": conv1, "conv2": conv2, "run": run}


# ──────────────────────────────────────────────────────────
# search_turns tests
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_search_no_filters(db_session, seed_data):
    """Basic search returns all turns in dataset."""
    data = seed_data
    result = await search_turns(db_session, dataset_id=data["ds"].id)
    assert result["total"] == 6
    assert len(result["results"]) == 6
    assert result["page"] == 1


@pytest.mark.asyncio
async def test_search_keyword(db_session, seed_data):
    """Keyword filter matches text content."""
    data = seed_data
    result = await search_turns(db_session, dataset_id=data["ds"].id, keyword="complaint")
    assert result["total"] == 1
    assert result["results"][0]["text"] == "I have a complaint"


@pytest.mark.asyncio
async def test_search_speaker(db_session, seed_data):
    """Speaker filter returns only matching turns."""
    data = seed_data
    result = await search_turns(db_session, dataset_id=data["ds"].id, speaker="agent")
    assert result["total"] == 2
    assert all(r["speaker"] == "agent" for r in result["results"])


@pytest.mark.asyncio
async def test_search_with_taxonomy(db_session, seed_data):
    """Taxonomy filter shows classification labels."""
    data = seed_data
    result = await search_turns(db_session, dataset_id=data["ds"].id, taxonomy_id=data["tax"].id)
    # Should return all 6 turns (outer join), some with labels, some without
    assert result["total"] == 6
    labeled = [r for r in result["results"] if r["intent_label"] is not None]
    assert len(labeled) >= 3  # at least direct classifications


@pytest.mark.asyncio
async def test_search_with_run(db_session, seed_data):
    """Run-specific search returns only that run's classifications."""
    data = seed_data
    result = await search_turns(db_session, dataset_id=data["ds"].id, run_id=data["run"].id)
    assert result["total"] == 6
    # Conv2 turns should have labels from the run
    conv2_results = [r for r in result["results"] if r["conversation_id"] == data["conv2"].id]
    assert all(r["intent_label"] == "Greeting" for r in conv2_results)


@pytest.mark.asyncio
async def test_search_intent_filter(db_session, seed_data):
    """Intent label filter narrows results."""
    data = seed_data
    result = await search_turns(
        db_session, dataset_id=data["ds"].id, taxonomy_id=data["tax"].id,
        intent_labels=["Complaint"]
    )
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_search_confidence_filter(db_session, seed_data):
    """Confidence range filter works."""
    data = seed_data
    result = await search_turns(
        db_session, dataset_id=data["ds"].id, taxonomy_id=data["tax"].id,
        min_confidence=0.90
    )
    assert result["total"] >= 1
    for r in result["results"]:
        if r["confidence"] is not None:
            assert r["confidence"] >= 0.90


@pytest.mark.asyncio
async def test_search_ground_truth(db_session, seed_data):
    """Ground truth intent filter."""
    data = seed_data
    result = await search_turns(
        db_session, dataset_id=data["ds"].id, ground_truth_intent="Complaint"
    )
    assert result["total"] == 1


@pytest.mark.asyncio
async def test_search_pagination(db_session, seed_data):
    """Pagination returns correct subsets."""
    data = seed_data
    page1 = await search_turns(db_session, dataset_id=data["ds"].id, page=1, page_size=2)
    assert len(page1["results"]) == 2
    assert page1["total"] == 6
    assert page1["total_pages"] == 3

    page2 = await search_turns(db_session, dataset_id=data["ds"].id, page=2, page_size=2)
    assert len(page2["results"]) == 2
    # No overlap
    ids1 = {r["turn_id"] for r in page1["results"]}
    ids2 = {r["turn_id"] for r in page2["results"]}
    assert ids1.isdisjoint(ids2)


# ──────────────────────────────────────────────────────────
# get_filter_options tests
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_filter_options_basic(db_session, seed_data):
    """Filter options returns speakers and ground truth intents."""
    data = seed_data
    opts = await get_filter_options(db_session, data["ds"].id)
    assert "user" in opts["speakers"]
    assert "agent" in opts["speakers"]
    assert "Complaint" in opts["ground_truth_intents"]


@pytest.mark.asyncio
async def test_filter_options_with_taxonomy(db_session, seed_data):
    """Filter options with taxonomy includes intent labels."""
    data = seed_data
    opts = await get_filter_options(db_session, data["ds"].id, taxonomy_id=data["tax"].id)
    assert "Greeting" in opts["intent_labels"]
    assert opts["confidence_range"]["min"] <= opts["confidence_range"]["max"]


@pytest.mark.asyncio
async def test_filter_options_with_run(db_session, seed_data):
    """Filter options with run_id scopes to that run's labels."""
    data = seed_data
    opts = await get_filter_options(db_session, data["ds"].id, run_id=data["run"].id)
    assert "Greeting" in opts["intent_labels"]
    assert opts["confidence_range"]["min"] >= 0.0


@pytest.mark.asyncio
async def test_filter_options_no_classifications(db_session, seed_data):
    """Filter options without taxonomy/run returns empty labels."""
    data = seed_data
    opts = await get_filter_options(db_session, data["ds"].id)
    assert opts["intent_labels"] == []
    assert opts["confidence_range"] == {"min": 0.0, "max": 1.0}
