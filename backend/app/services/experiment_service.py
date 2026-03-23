import asyncio
import json
import logging
import os
import time
import datetime
from typing import Dict, Any
from collections import Counter

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import (
    Experiment, Run, RunClassification, LabelMapping,
    Conversation, Turn, IntentCategory, IntentTaxonomy, Dataset
)
from app.classifiers.base import ClassifierConfigError
from app.database import get_session_factory
from app.services.classification_service import get_classifier, is_fallback_label, _group_turns_by_conversation

logger = logging.getLogger(__name__)


async def create_experiment(db: AsyncSession, data: dict) -> Experiment:
    # Validate that dataset and taxonomy exist
    dataset = await db.get(Dataset, data["dataset_id"])
    if not dataset:
        raise ValueError(f"Dataset {data['dataset_id']} not found")
    taxonomy = await db.get(IntentTaxonomy, data["taxonomy_id"])
    if not taxonomy:
        raise ValueError(f"Taxonomy {data['taxonomy_id']} not found")

    params = data.get("classifier_parameters")
    exp = Experiment(
        name=data["name"],
        description=data.get("description"),
        dataset_id=data["dataset_id"],
        taxonomy_id=data["taxonomy_id"],
        classification_method=data["classification_method"],
        classifier_parameters=json.dumps(params) if params else None,
        created_by=data.get("created_by"),
    )
    db.add(exp)
    await db.commit()
    await db.refresh(exp)
    return exp


async def update_experiment(db: AsyncSession, exp_id: int, data: dict) -> Experiment:
    exp = await db.get(Experiment, exp_id)
    if not exp:
        raise ValueError(f"Experiment {exp_id} not found")
    # Validate FK references if being updated
    if "dataset_id" in data and data["dataset_id"] is not None:
        dataset = await db.get(Dataset, data["dataset_id"])
        if not dataset:
            raise ValueError(f"Dataset {data['dataset_id']} not found")
    if "taxonomy_id" in data and data["taxonomy_id"] is not None:
        taxonomy = await db.get(IntentTaxonomy, data["taxonomy_id"])
        if not taxonomy:
            raise ValueError(f"Taxonomy {data['taxonomy_id']} not found")

    for key in ["name", "description", "dataset_id", "taxonomy_id", "classification_method", "created_by"]:
        if key in data and data[key] is not None:
            setattr(exp, key, data[key])
    if "classifier_parameters" in data:
        exp.classifier_parameters = json.dumps(data["classifier_parameters"]) if data["classifier_parameters"] else None
    if "is_favorite" in data and data["is_favorite"] is not None:
        exp.is_favorite = data["is_favorite"]
    await db.commit()
    await db.refresh(exp)
    return exp


async def get_experiment_read(db: AsyncSession, exp: Experiment) -> dict:
    """Build the read dict with run_count, last_run_date, dataset_name, taxonomy_name."""
    run_count_q = await db.execute(select(func.count(Run.id)).where(Run.experiment_id == exp.id))
    run_count = run_count_q.scalar() or 0

    last_run_q = await db.execute(
        select(Run.execution_date)
        .where(Run.experiment_id == exp.id)
        .order_by(Run.execution_date.desc())
        .limit(1)
    )
    last_run_date = last_run_q.scalar()

    dataset = await db.get(Dataset, exp.dataset_id)
    taxonomy = await db.get(IntentTaxonomy, exp.taxonomy_id)

    params = None
    if exp.classifier_parameters:
        try:
            params = json.loads(exp.classifier_parameters)
        except Exception:
            params = None

    return {
        "id": exp.id,
        "name": exp.name,
        "description": exp.description,
        "dataset_id": exp.dataset_id,
        "taxonomy_id": exp.taxonomy_id,
        "classification_method": exp.classification_method,
        "classifier_parameters": params,
        "created_by": exp.created_by,
        "is_favorite": bool(exp.is_favorite),
        "created_at": exp.created_at,
        "run_count": run_count,
        "last_run_date": last_run_date,
        "dataset_name": dataset.name if dataset else None,
        "taxonomy_name": taxonomy.name if taxonomy else None,
    }


async def validate_labels(db: AsyncSession, experiment_id: int) -> dict:
    """Run classifier on a sample and compare labels against taxonomy."""
    exp = await db.get(Experiment, experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    # Get taxonomy labels
    cats_result = await db.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == exp.taxonomy_id)
    )
    categories = cats_result.scalars().all()
    taxonomy_labels = {c.name for c in categories}
    taxonomy_categories = [{"name": c.name, "description": c.description or ""} for c in categories]

    # Get sample turns
    turns_result = await db.execute(
        select(Turn)
        .join(Conversation, Turn.conversation_id == Conversation.id)
        .where(Conversation.dataset_id == exp.dataset_id)
        .limit(20)
    )
    sample_turns = turns_result.scalars().all()
    if not sample_turns:
        return {"compatible": True, "taxonomy_labels": list(taxonomy_labels), "classifier_labels": [], "mismatches": []}

    params = json.loads(exp.classifier_parameters) if exp.classifier_parameters else None
    classifier = get_classifier(exp.classification_method, params)
    results = classifier.classify_batch([t.text for t in sample_turns], taxonomy_categories)

    classifier_labels = {label for label, _, _ in results}
    # Fallback labels (UNKNOWN, None, null, empty, UNKNOWN_SUBCATEGORY, …)
    # are valid complementary classes — exclude them from mismatch detection.
    mismatches = {
        label for label in classifier_labels - taxonomy_labels
        if not is_fallback_label(label)
    }

    return {
        "compatible": len(mismatches) == 0,
        "taxonomy_labels": sorted(taxonomy_labels),
        "classifier_labels": sorted(classifier_labels),
        "mismatches": sorted(mismatches),
    }


async def start_experiment_run(db: AsyncSession, experiment_id: int) -> Run:
    """Create a run record and validate config. Returns immediately with 'pending' status.

    The caller (router) is responsible for launching the background execution
    via ``execute_run_background()``.
    """
    exp = await db.get(Experiment, experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    params = json.loads(exp.classifier_parameters) if exp.classifier_parameters else None

    # Validate classifier can be created (fail fast on config errors)
    try:
        get_classifier(exp.classification_method, params)
    except ClassifierConfigError as e:
        raise ValueError(f"Classifier configuration error: {e}")

    run = Run(
        experiment_id=experiment_id,
        status="pending",
        execution_date=datetime.datetime.utcnow(),
        configuration_snapshot=json.dumps({
            "classification_method": exp.classification_method,
            "classifier_parameters": params,
            "dataset_id": exp.dataset_id,
            "taxonomy_id": exp.taxonomy_id,
        }),
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def execute_run_background(run_id: int, experiment_id: int) -> None:
    """Execute the classification. Uses its own DB session (safe for background tasks)."""
    try:
        async with get_session_factory()() as db:
            await _execute_run(db, run_id, experiment_id)
    except Exception as e:
        # Last-resort handler: ensure the run is marked as failed
        logger.error("Background run %d crashed: %s", run_id, str(e))
        try:
            async with get_session_factory()() as db:
                run = await db.get(Run, run_id)
                if run and run.status in ("pending", "running"):
                    run.status = "failed"
                    run.results_summary = json.dumps({"error": f"Background task crashed: {str(e)}"})
                    await db.commit()
        except Exception:
            logger.error("Failed to mark run %d as failed after crash", run_id)


async def run_experiment(db: AsyncSession, experiment_id: int) -> Run:
    """Execute an experiment run synchronously (used by tests and simple classifiers)."""
    exp = await db.get(Experiment, experiment_id)
    if not exp:
        raise ValueError("Experiment not found")

    params = json.loads(exp.classifier_parameters) if exp.classifier_parameters else None

    try:
        get_classifier(exp.classification_method, params)
    except ClassifierConfigError as e:
        raise ValueError(f"Classifier configuration error: {e}")

    run = Run(
        experiment_id=experiment_id,
        status="pending",
        execution_date=datetime.datetime.utcnow(),
        configuration_snapshot=json.dumps({
            "classification_method": exp.classification_method,
            "classifier_parameters": params,
            "dataset_id": exp.dataset_id,
            "taxonomy_id": exp.taxonomy_id,
        }),
    )
    db.add(run)
    await db.flush()

    await _execute_run(db, run.id, experiment_id)
    await db.refresh(run)
    return run


async def _execute_run(
    db: AsyncSession,
    run_id: int,
    experiment_id: int,
    batch_size: int = 500,
) -> None:
    """Core classification logic shared by sync and background execution.

    Processes turns in batches of ``batch_size`` to avoid loading the entire
    dataset into memory at once.
    """
    run = await db.get(Run, run_id)
    exp = await db.get(Experiment, experiment_id)
    if not run or not exp:
        return

    run.status = "running"
    run.progress_current = 0
    run.progress_total = 0
    await db.commit()

    params = json.loads(exp.classifier_parameters) if exp.classifier_parameters else None
    start_time = time.time()

    try:
        # Load taxonomy categories
        cats_result = await db.execute(
            select(IntentCategory).where(IntentCategory.taxonomy_id == exp.taxonomy_id)
        )
        categories = cats_result.scalars().all()
        taxonomy_categories = [{"name": c.name, "description": c.description or ""} for c in categories]

        # Load label mappings
        mappings_result = await db.execute(
            select(LabelMapping).where(LabelMapping.experiment_id == experiment_id)
        )
        label_map = {m.classifier_label: m.taxonomy_label for m in mappings_result.scalars().all()}

        # Count total turns for progress tracking
        count_result = await db.execute(
            select(func.count(Turn.id))
            .join(Conversation, Turn.conversation_id == Conversation.id)
            .where(Conversation.dataset_id == exp.dataset_id)
        )
        total_turns = count_result.scalar() or 0
        run.progress_total = total_turns
        await db.commit()

        # Build classifier
        try:
            classifier = get_classifier(exp.classification_method, params)
        except ClassifierConfigError as e:
            raise ValueError(f"Classifier configuration error: {e}")

        # Pre-flight check on first turn
        preflight_result = await db.execute(
            select(Turn)
            .join(Conversation, Turn.conversation_id == Conversation.id)
            .where(Conversation.dataset_id == exp.dataset_id)
            .limit(1)
        )
        first_turn = preflight_result.scalar_one_or_none()
        if first_turn:
            try:
                classifier.classify_turn(first_turn.text, taxonomy_categories)
            except ClassifierConfigError as e:
                raise ValueError(f"Classifier configuration error: {e}")

        loop = asyncio.get_event_loop()
        use_conv_batch = hasattr(classifier, 'classify_conversation_batch')

        intent_counter: Counter = Counter()
        total_confidence = 0.0
        processed = 0
        conversation_ids = set()

        # Process turns in batches
        offset = 0
        while offset < total_turns:
            # Load a batch of turns
            batch_result = await db.execute(
                select(Turn)
                .join(Conversation, Turn.conversation_id == Conversation.id)
                .where(Conversation.dataset_id == exp.dataset_id)
                .order_by(Conversation.id, Turn.turn_index)
                .offset(offset)
                .limit(batch_size)
            )
            batch_turns = batch_result.scalars().all()
            if not batch_turns:
                break

            # Classify the batch
            if use_conv_batch:
                conversations = _group_turns_by_conversation(batch_turns)
                conv_results = await loop.run_in_executor(
                    None, classifier.classify_conversation_batch,
                    conversations, taxonomy_categories,
                )
                result_lookup = {}
                for conv_id, conv_result_list in conv_results.items():
                    conv_turns_info = conversations[conv_id]
                    for ti, res in zip(conv_turns_info, conv_result_list):
                        result_lookup[(ti.conversation_id, ti.turn_index)] = res
                results = [
                    result_lookup.get(
                        (t.conversation_id, t.turn_index),
                        ("UNKNOWN", 0.0, "Missing result"),
                    )
                    for t in batch_turns
                ]
            else:
                batch_texts = [t.text for t in batch_turns]
                results = await loop.run_in_executor(
                    None, classifier.classify_batch, batch_texts, taxonomy_categories
                )

            # Store classifications for this batch
            for turn, (label, confidence, _explanation) in zip(batch_turns, results):
                mapped_label = label_map.get(label, label)
                db.add(RunClassification(
                    run_id=run.id,
                    conversation_id=turn.conversation_id,
                    turn_id=turn.id,
                    speaker=turn.speaker,
                    text=turn.text,
                    intent_label=mapped_label,
                    confidence=confidence,
                ))
                intent_counter[mapped_label] += 1
                total_confidence += confidence
                conversation_ids.add(turn.conversation_id)

            processed += len(batch_turns)
            offset += batch_size

            # Update progress and commit batch
            run.progress_current = processed
            await db.commit()
            logger.info("Run %d: classified %d / %d turns", run_id, processed, total_turns)

        fallback_count = sum(
            count for label, count in intent_counter.items()
            if is_fallback_label(label)
        )

        run.status = "completed"
        run.progress_current = processed
        run.runtime_duration = round(time.time() - start_time, 3)
        summary = {
            "total_turns": processed,
            "total_conversations": len(conversation_ids),
            "unique_intents": len(intent_counter),
            "avg_confidence": round(total_confidence / max(processed, 1), 4),
            "intent_distribution": dict(intent_counter.most_common()),
        }

        if processed > 0 and fallback_count == processed:
            summary["warning"] = (
                "All turns were classified as UNKNOWN/fallback. "
                "This usually means the LLM API call is failing silently. "
                "Check: (1) API key is set, (2) model name is correct, "
                "(3) base_url is reachable."
            )

        run.results_summary = json.dumps(summary)

    except Exception as e:
        logger.error("Experiment run %d failed: %s", run_id, str(e))
        # Sanitize error message: never expose API keys or internal paths
        error_msg = str(e)
        for env_var in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            key_val = os.environ.get(env_var, "")
            if key_val and key_val in error_msg:
                error_msg = error_msg.replace(key_val, "***")
        run.status = "failed"
        run.runtime_duration = round(time.time() - start_time, 3)
        run.results_summary = json.dumps({"error": error_msg})

    await db.commit()


async def get_run_results(db: AsyncSession, run_id: int) -> list:
    """Get run classifications grouped by conversation."""
    result = await db.execute(
        select(RunClassification)
        .where(RunClassification.run_id == run_id)
        .order_by(RunClassification.conversation_id, RunClassification.id)
    )
    rows = result.scalars().all()

    conversations: Dict[int, Dict[str, Any]] = {}
    for rc in rows:
        cid = rc.conversation_id
        if cid not in conversations:
            conversations[cid] = {"conversation_id": cid, "turns": []}
        conversations[cid]["turns"].append({
            "id": rc.id,
            "turn_id": rc.turn_id,
            "speaker": rc.speaker,
            "text": rc.text,
            "intent_label": rc.intent_label,
            "confidence": rc.confidence,
        })

    return list(conversations.values())
