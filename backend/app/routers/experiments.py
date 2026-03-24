import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.models import Experiment, Run, LabelMapping
from app.schemas.schemas import (
    ExperimentCreate, ExperimentUpdate, LabelMappingCreate,
)
import asyncio

from app.services.experiment_service import (
    create_experiment, update_experiment, get_experiment_read,
    validate_labels, start_experiment_run, execute_run_background,
    get_run_results, request_pause,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


@router.get("/methods", tags=["classification"])
async def list_methods():
    """List available classification methods with their configurable parameters."""
    return [
        {
            "id": "rule_based",
            "name": "Rule-Based",
            "description": "Keyword matching against category names and descriptions.",
            "config_schema": [
                {
                    "key": "keyword_map",
                    "label": "Custom Keyword Map",
                    "type": "json",
                    "description": "Override default keyword-to-intent mappings (JSON object: intent name -> keyword list)",
                    "required": False,
                },
            ],
        },
        {
            "id": "embedding",
            "name": "Embedding Similarity",
            "description": "TF-IDF vectorization with cosine similarity.",
            "config_schema": [],
        },
        {
            "id": "zero_shot",
            "name": "Zero-Shot (LLM)",
            "description": "Zero-shot classification using an LLM. No examples needed — the model infers intent from category names and descriptions alone.",
            "config_schema": [
                {
                    "key": "provider",
                    "label": "Provider",
                    "type": "select",
                    "options": ["openai", "anthropic"],
                    "default": "openai",
                    "description": "LLM provider. 'openai' works with any OpenAI-compatible API (Ollama, vLLM, LiteLLM, etc.)",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "type": "text",
                    "default": "gpt-4o-mini",
                    "description": "Model identifier (e.g. gpt-4o-mini, claude-sonnet-4-20250514, llama3.1:8b for Ollama)",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "default": "",
                    "description": "API key. Leave empty to use OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.",
                    "required": False,
                },
                {
                    "key": "base_url",
                    "label": "Base URL",
                    "type": "text",
                    "default": "",
                    "description": "Custom API base URL. For Ollama: http://localhost:11434/v1. Leave empty for default provider URL.",
                    "required": False,
                },
                {
                    "key": "temperature",
                    "label": "Temperature",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.0,
                    "description": "Sampling temperature. 0 = deterministic (recommended for classification).",
                },
                {
                    "key": "system_prompt",
                    "label": "System Prompt",
                    "type": "json",
                    "default": None,
                    "description": "Custom system prompt. Use {categories} as placeholder for the taxonomy list. Leave empty for the built-in analytical prompt.",
                    "required": False,
                },
                {
                    "key": "batch_size",
                    "label": "Texts per API Call",
                    "type": "number",
                    "default": 1,
                    "description": "Classify multiple texts in one prompt (cheaper, but may reduce accuracy for >5).",
                },
                {
                    "key": "max_tokens",
                    "label": "Max Response Tokens",
                    "type": "number",
                    "default": 256,
                    "description": "Max tokens for the LLM response. Increase for batch_size > 1.",
                },
            ],
        },
        {
            "id": "hybrid",
            "name": "Hybrid",
            "description": "Weighted combination of rule-based and embedding classifiers.",
            "config_schema": [
                {
                    "key": "rule_weight",
                    "label": "Rule-Based Weight",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.4,
                    "description": "Weight assigned to the rule-based classifier",
                },
                {
                    "key": "embedding_weight",
                    "label": "Embedding Weight",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.6,
                    "description": "Weight assigned to the embedding similarity classifier",
                },
            ],
        },
        {
            "id": "transformer",
            "name": "Transformer (HuggingFace)",
            "description": "Pre-trained transformer model for intent classification. Supports zero-shot NLI models and fine-tuned text classifiers from HuggingFace Hub or local directories. Requires 'transformers' and 'torch'.",
            "config_schema": [
                {
                    "key": "model_name",
                    "label": "Model Name / Path",
                    "type": "text",
                    "default": "facebook/bart-large-mnli",
                    "description": "HuggingFace model ID (e.g. facebook/bart-large-mnli) or absolute local path to a saved model directory.",
                },
                {
                    "key": "mode",
                    "label": "Mode",
                    "type": "select",
                    "options": ["zero_shot_nli", "fine_tuned", "probabilities"],
                    "default": "zero_shot_nli",
                    "description": "zero_shot_nli: NLI-based (no training needed). fine_tuned: pre-trained text-classification model (top label). probabilities: same but shows ALL per-intent probabilities.",
                },
                {
                    "key": "device",
                    "label": "Device",
                    "type": "select",
                    "options": ["cpu", "cuda", "mps", "auto"],
                    "default": "cpu",
                    "description": "Compute device. 'auto' detects GPU/MPS automatically.",
                },
                {
                    "key": "batch_size",
                    "label": "Batch Size",
                    "type": "number",
                    "default": 16,
                    "description": "Number of texts per inference batch.",
                },
                {
                    "key": "max_length",
                    "label": "Max Token Length",
                    "type": "number",
                    "default": 512,
                    "description": "Maximum input token length. Texts longer than this are truncated.",
                },
                {
                    "key": "hypothesis_template",
                    "label": "Hypothesis Template (NLI only)",
                    "type": "text",
                    "default": "This text is about {}.",
                    "description": "Template for NLI hypothesis. {} is replaced with each category name. Only used in zero_shot_nli mode.",
                },
                {
                    "key": "label_map",
                    "label": "Label Mapping (fine-tuned only)",
                    "type": "json",
                    "default": None,
                    "description": "Explicit mapping from model output labels to taxonomy names. JSON object: {\"LABEL_0\": \"Billing\", \"LABEL_1\": \"Support\"}. If empty, auto-detects from model config.",
                    "required": False,
                },
                {
                    "key": "confidence_threshold",
                    "label": "Confidence Threshold",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.0,
                    "description": "Minimum confidence to accept a prediction. Below this threshold, the label is set to 'Unknown'.",
                },
            ],
        },
        {
            "id": "llm_fewshot",
            "name": "LLM Few-Shot",
            "description": "Few-shot classification using an LLM API (OpenAI, Anthropic, or any OpenAI-compatible endpoint like Ollama/vLLM).",
            "config_schema": [
                {
                    "key": "provider",
                    "label": "Provider",
                    "type": "select",
                    "options": ["openai", "anthropic"],
                    "default": "openai",
                    "description": "LLM provider. 'openai' works with any OpenAI-compatible API (Ollama, vLLM, LiteLLM, etc.)",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "type": "text",
                    "default": "gpt-4o-mini",
                    "description": "Model identifier (e.g. gpt-4o-mini, claude-sonnet-4-20250514, llama3.1:8b for Ollama)",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "default": "",
                    "description": "API key. Leave empty to use OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.",
                    "required": False,
                },
                {
                    "key": "base_url",
                    "label": "Base URL",
                    "type": "text",
                    "default": "",
                    "description": "Custom API base URL. For Ollama: http://localhost:11434/v1. Leave empty for default provider URL.",
                    "required": False,
                },
                {
                    "key": "temperature",
                    "label": "Temperature",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.1,
                    "description": "Lower = more deterministic. Recommended: 0.0-0.2 for classification.",
                },
                {
                    "key": "num_examples",
                    "label": "Few-Shot Examples per Category",
                    "type": "number",
                    "default": 2,
                    "description": "Number of synthetic examples per category. More examples = better quality but higher token cost.",
                },
                {
                    "key": "batch_size",
                    "label": "Texts per API Call",
                    "type": "number",
                    "default": 1,
                    "description": "Classify multiple texts in one prompt (cheaper, but may reduce accuracy for >5).",
                },
                {
                    "key": "max_tokens",
                    "label": "Max Response Tokens",
                    "type": "number",
                    "default": 256,
                    "description": "Max tokens for the LLM response. Increase for batch_size > 1.",
                },
            ],
        },
        {
            "id": "cascading",
            "name": "Cascading (Two-Stage LLM)",
            "description": "Two-stage cascading classifier. Stage 1 routes to a top-level category (9 domains). Stage 2 classifies the specific sub-intent within that category. Uses specialized prompts loaded from external files. Supports bilingual EN/ES input.",
            "config_schema": [
                {
                    "key": "provider",
                    "label": "Provider",
                    "type": "select",
                    "options": ["openai", "anthropic"],
                    "default": "openai",
                    "description": "LLM provider. 'openai' works with any OpenAI-compatible API (Ollama, vLLM, LiteLLM, etc.)",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "type": "text",
                    "default": "gpt-5.2",
                    "description": "Default model for both stages. Override per-stage with stage1_model / stage2_model.",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "default": "",
                    "description": "API key. Leave empty to use OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.",
                    "required": False,
                },
                {
                    "key": "base_url",
                    "label": "Base URL",
                    "type": "text",
                    "default": "https://api.openai.com/v1",
                    "description": "Custom API base URL. For Ollama: http://localhost:11434/v1. Leave empty for default provider URL.",
                    "required": False,
                },
                {
                    "key": "temperature",
                    "label": "Temperature",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.0,
                    "description": "Sampling temperature. 0 = deterministic (recommended for classification).",
                },
                {
                    "key": "stage1_threshold",
                    "label": "Stage 1 Confidence Threshold",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.60,
                    "description": "Minimum confidence to proceed from Stage 1 (category) to Stage 2 (sub-intent). Below this, classified as UNKNOWN.",
                },
                {
                    "key": "stage2_threshold",
                    "label": "Stage 2 Confidence Threshold",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.65,
                    "description": "Minimum confidence for the sub-intent classification. Below this, returns UNKNOWN_SUBCATEGORY within the matched category.",
                },
                {
                    "key": "stage1_model",
                    "label": "Stage 1 Model (optional)",
                    "type": "text",
                    "default": "",
                    "description": "Override model for Stage 1 (e.g. use a faster/cheaper model for category routing). Leave empty to use the default model.",
                    "required": False,
                },
                {
                    "key": "stage2_model",
                    "label": "Stage 2 Model (optional)",
                    "type": "text",
                    "default": "",
                    "description": "Override model for Stage 2 (e.g. use a more capable model for sub-intent). Leave empty to use the default model.",
                    "required": False,
                },
                {
                    "key": "max_tokens",
                    "label": "Max Response Tokens",
                    "type": "number",
                    "default": 200,
                    "description": "Max tokens per LLM response (applies to each stage independently).",
                },
                {
                    "key": "max_concurrency",
                    "label": "Max Concurrency",
                    "type": "number",
                    "default": 5,
                    "description": "Number of turns classified in parallel. Higher = faster but may hit API rate limits. Recommended: 3-10.",
                },
            ],
        },
        {
            "id": "cascading_context",
            "name": "Cascading + Context (Two-Stage LLM)",
            "description": "Two-stage cascading classifier with conversational context. Surrounding turns are injected into the prompt so the LLM can resolve anaphora, follow-ups, and ambiguous messages. Supports two modes: static context (parallel) and chained context with previous labels (sequential per conversation).",
            "config_schema": [
                {
                    "key": "provider",
                    "label": "Provider",
                    "type": "select",
                    "options": ["openai", "anthropic"],
                    "default": "openai",
                    "description": "LLM provider. 'openai' works with any OpenAI-compatible API (Ollama, vLLM, LiteLLM, etc.)",
                },
                {
                    "key": "model",
                    "label": "Model",
                    "type": "text",
                    "default": "gpt-5.2",
                    "description": "Default model for both stages. Override per-stage with stage1_model / stage2_model.",
                },
                {
                    "key": "api_key",
                    "label": "API Key",
                    "type": "password",
                    "default": "",
                    "description": "API key. Leave empty to use OPENAI_API_KEY or ANTHROPIC_API_KEY environment variable.",
                    "required": False,
                },
                {
                    "key": "base_url",
                    "label": "Base URL",
                    "type": "text",
                    "default": "https://api.openai.com/v1",
                    "description": "Custom API base URL. For Ollama: http://localhost:11434/v1. Leave empty for default provider URL.",
                    "required": False,
                },
                {
                    "key": "temperature",
                    "label": "Temperature",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.0,
                    "description": "Sampling temperature. 0 = deterministic (recommended for classification).",
                },
                {
                    "key": "stage1_threshold",
                    "label": "Stage 1 Confidence Threshold",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.60,
                    "description": "Minimum confidence to proceed from Stage 1 (category) to Stage 2 (sub-intent).",
                },
                {
                    "key": "stage2_threshold",
                    "label": "Stage 2 Confidence Threshold",
                    "type": "range",
                    "min": 0.0,
                    "max": 1.0,
                    "step": 0.05,
                    "default": 0.65,
                    "description": "Minimum confidence for the sub-intent classification.",
                },
                {
                    "key": "stage1_model",
                    "label": "Stage 1 Model (optional)",
                    "type": "text",
                    "default": "",
                    "description": "Override model for Stage 1. Leave empty to use the default model.",
                    "required": False,
                },
                {
                    "key": "stage2_model",
                    "label": "Stage 2 Model (optional)",
                    "type": "text",
                    "default": "",
                    "description": "Override model for Stage 2. Leave empty to use the default model.",
                    "required": False,
                },
                {
                    "key": "max_tokens",
                    "label": "Max Response Tokens",
                    "type": "number",
                    "default": 250,
                    "description": "Max tokens per LLM response (applies to each stage independently).",
                },
                {
                    "key": "max_concurrency",
                    "label": "Max Concurrency",
                    "type": "number",
                    "default": 5,
                    "description": "Number of turns (Mode A) or conversations (Mode B) classified in parallel.",
                },
                {
                    "key": "context_backward",
                    "label": "Backward Context Turns",
                    "type": "number",
                    "default": 2,
                    "description": "Number of preceding turns to include as context.",
                },
                {
                    "key": "context_forward",
                    "label": "Forward Context Turns",
                    "type": "number",
                    "default": 1,
                    "description": "Number of following turns to include as context.",
                },
                {
                    "key": "context_max_chars",
                    "label": "Max Chars per Context Turn",
                    "type": "number",
                    "default": 500,
                    "description": "Maximum characters per context turn (truncation limit). Target turn is never truncated.",
                },
                {
                    "key": "use_previous_labels",
                    "label": "Chain labels across turns (sequential mode)",
                    "type": "checkbox",
                    "default": False,
                    "description": "When enabled, each turn sees the classified intent labels of previous turns in its context window. This makes classification sequential within each conversation (slower) but significantly improves accuracy for follow-up and anaphoric messages like \"Yes, that one\". When disabled, all turns are classified in full parallel with text-only context.",
                },
            ],
        },
    ]


@router.post("")
async def create(data: ExperimentCreate, db: AsyncSession = Depends(get_db)):
    try:
        exp = await create_experiment(db, data.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e))
    return await get_experiment_read(db, exp)


@router.get("")
async def list_experiments(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Experiment).order_by(Experiment.created_at.desc()).offset(skip).limit(limit)
    )
    experiments = result.scalars().all()
    return [await get_experiment_read(db, exp) for exp in experiments]


@router.get("/{exp_id}")
async def get_experiment(exp_id: int, db: AsyncSession = Depends(get_db)):
    exp = await db.get(Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    return await get_experiment_read(db, exp)


@router.put("/{exp_id}")
async def update(exp_id: int, data: ExperimentUpdate, db: AsyncSession = Depends(get_db)):
    try:
        exp = await update_experiment(db, exp_id, data.model_dump(exclude_unset=True))
    except ValueError as e:
        raise HTTPException(404, str(e))
    return await get_experiment_read(db, exp)


@router.delete("/{exp_id}")
async def delete(exp_id: int, db: AsyncSession = Depends(get_db)):
    exp = await db.get(Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    await db.delete(exp)
    await db.commit()
    return {"detail": "Experiment deleted", "id": exp_id}


# --- Runs ---

@router.post("/{exp_id}/run")
async def trigger_run(exp_id: int, db: AsyncSession = Depends(get_db)):
    """Start an experiment run in the background.

    Returns immediately with status "pending".  The classification
    executes asynchronously — poll ``GET /experiments/runs/{run_id}``
    to track progress.
    """
    try:
        run = await start_experiment_run(db, exp_id)
    except ValueError as e:
        raise HTTPException(400, str(e))

    # Launch background task (uses its own DB session)
    asyncio.create_task(
        execute_run_background(run.id, exp_id)
    )

    return _run_to_dict(run)


@router.get("/{exp_id}/runs")
async def list_runs(exp_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Run).where(Run.experiment_id == exp_id).order_by(Run.created_at.desc())
    )
    return [_run_to_dict(r) for r in result.scalars().all()]


@router.get("/runs/{run_id}", tags=["runs"])
async def get_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return _run_to_dict(run)


@router.get("/runs/{run_id}/results", tags=["runs"])
async def get_results(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return await get_run_results(db, run_id)


@router.patch("/runs/{run_id}/pause", tags=["runs"])
async def pause_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Pause a running experiment run after its current batch finishes."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "running":
        raise HTTPException(409, f"Cannot pause a run with status '{run.status}'")
    if not request_pause(run_id):
        raise HTTPException(409, "No active background task found for this run")
    return _run_to_dict(run)


@router.post("/runs/{run_id}/resume", tags=["runs"])
async def resume_run(run_id: int, db: AsyncSession = Depends(get_db)):
    """Resume a paused run from where it left off."""
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    if run.status != "paused":
        raise HTTPException(409, f"Cannot resume a run with status '{run.status}'")

    initial_offset = run.progress_current or 0
    run.status = "running"
    await db.commit()

    asyncio.create_task(
        execute_run_background(run.id, run.experiment_id, initial_offset=initial_offset)
    )
    return _run_to_dict(run)


@router.delete("/runs/{run_id}", tags=["runs"])
async def delete_run(run_id: int, db: AsyncSession = Depends(get_db)):
    run = await db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    await db.delete(run)
    await db.commit()
    return {"detail": "Run deleted", "id": run_id}


# --- Label Mapping ---

@router.get("/{exp_id}/label-mapping")
async def get_label_mapping(exp_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(LabelMapping).where(LabelMapping.experiment_id == exp_id)
    )
    return [{"id": m.id, "experiment_id": m.experiment_id, "classifier_label": m.classifier_label, "taxonomy_label": m.taxonomy_label} for m in result.scalars().all()]


@router.post("/{exp_id}/label-mapping")
async def set_label_mapping(exp_id: int, mappings: List[LabelMappingCreate], db: AsyncSession = Depends(get_db)):
    exp = await db.get(Experiment, exp_id)
    if not exp:
        raise HTTPException(404, "Experiment not found")
    # Delete existing mappings
    existing = await db.execute(select(LabelMapping).where(LabelMapping.experiment_id == exp_id))
    for m in existing.scalars().all():
        await db.delete(m)
    # Create new
    created = []
    for m in mappings:
        lm = LabelMapping(experiment_id=exp_id, classifier_label=m.classifier_label, taxonomy_label=m.taxonomy_label)
        db.add(lm)
        created.append(lm)
    await db.commit()
    return [{"id": m.id, "experiment_id": m.experiment_id, "classifier_label": m.classifier_label, "taxonomy_label": m.taxonomy_label} for m in created]


@router.get("/{exp_id}/validate-labels")
async def check_labels(exp_id: int, db: AsyncSession = Depends(get_db)):
    try:
        result = await validate_labels(db, exp_id)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return result


def _run_to_dict(run: Run) -> dict:
    config = None
    if run.configuration_snapshot:
        try:
            config = json.loads(run.configuration_snapshot)
        except Exception:
            config = None
    summary = None
    if run.results_summary:
        try:
            summary = json.loads(run.results_summary)
        except Exception:
            summary = None
    return {
        "id": run.id,
        "experiment_id": run.experiment_id,
        "status": run.status,
        "execution_date": run.execution_date.isoformat() if run.execution_date else None,
        "runtime_duration": run.runtime_duration,
        "configuration_snapshot": config,
        "results_summary": summary,
        "progress_current": run.progress_current,
        "progress_total": run.progress_total,
        "is_favorite": bool(run.is_favorite),
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
