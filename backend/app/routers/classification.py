from typing import Any, Dict, List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.schemas import ClassificationRead, ClassificationRequest, SaveExperimentRequest
from app.services.classification_service import (
    classify_dataset,
    get_classification_results,
)
from app.services.experiment_service import create_experiment, get_experiment_read

router = APIRouter(prefix="/classify", tags=["classification"])


@router.post("", response_model=List[ClassificationRead])
async def trigger_classification(
    request: ClassificationRequest,
    db: AsyncSession = Depends(get_db),
):
    """Trigger classification of all turns in a dataset."""
    try:
        classifications = await classify_dataset(
            db,
            dataset_id=request.dataset_id,
            taxonomy_id=request.taxonomy_id,
            method=request.method,
            config=request.config,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Classification failed: {str(e)}")
    return classifications


@router.post("/save-experiment")
async def save_experiment(
    request: SaveExperimentRequest,
    db: AsyncSession = Depends(get_db),
):
    """Save a classification configuration as an experiment without running it.

    The experiment can later be executed via ``POST /experiments/{id}/run``.
    """
    try:
        exp = await create_experiment(db, {
            "name": request.name,
            "description": request.description,
            "dataset_id": request.dataset_id,
            "taxonomy_id": request.taxonomy_id,
            "classification_method": request.method,
            "classifier_parameters": request.config,
            "created_by": request.created_by,
        })
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return await get_experiment_read(db, exp)


@router.get("/methods")
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


@router.get("/results/{dataset_id}/{taxonomy_id}")
async def get_results(
    dataset_id: int,
    taxonomy_id: int,
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    """Get classification results for a dataset and taxonomy."""
    results = await get_classification_results(db, dataset_id, taxonomy_id)
    if not results:
        raise HTTPException(
            status_code=404,
            detail="No classification results found for this dataset/taxonomy combination.",
        )
    return results
