import asyncio
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import Conversation, Dataset, Experiment, Run, Turn
from app.schemas.schemas import (
    ConversationDetail,
    ConversationRead,
    DatasetLoadSource,
    DatasetRead,
    DatasetUpdate,
    FilterOptionsResponse,
    TurnSearchResponse,
)
from app.services.dataset_service import (
    ingest_dataset,
    create_dataset_placeholder,
    ingest_dataset_background,
)
from app.services.search_service import get_filter_options, search_turns
from app.services.source_fetcher import (
    SourceFetchError,
    fetch_source,
    is_local_source,
    resolve_local_path,
)

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/upload", response_model=DatasetRead)
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    """Upload a CSV or JSON file to create a new dataset."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file provided")

    ext = file.filename.rsplit(".", 1)[-1].lower() if "." in file.filename else ""
    if ext not in ("csv", "json", "jsonl"):
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file type: {ext}. Use CSV, JSON, or JSONL.",
        )

    content = await file.read()

    MAX_UPLOAD_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB
    if len(content) > MAX_UPLOAD_SIZE:
        raise HTTPException(
            status_code=400,
            detail=f"File too large ({len(content) / 1024 / 1024:.1f} MB). Maximum allowed is 2048 MB.",
        )

    try:
        file_content = content.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")

    try:
        dataset = await ingest_dataset(db, name, description, file_content, ext)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return dataset


@router.post("/load-source", response_model=DatasetRead)
async def load_dataset_from_source(
    data: DatasetLoadSource,
    db: AsyncSession = Depends(get_db),
):
    """Load a dataset from a URL or server file path.

    For local files, ingestion runs in the background — the response returns
    immediately with status='processing'. Poll GET /datasets/{id} to check
    when status becomes 'ready' or 'failed'.
    """
    # ── Local files: validate path, create placeholder, background ingest ──
    if is_local_source(data.source):
        try:
            resolved = resolve_local_path(data.source)
        except SourceFetchError as e:
            raise HTTPException(status_code=400, detail=str(e))

        ext = resolved.suffix.lstrip(".").lower()
        if ext not in ("csv", "json", "jsonl"):
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file type: '.{ext}'. Use CSV, JSON, or JSONL.",
            )

        dataset = await create_dataset_placeholder(db, data.name, data.description, ext)
        asyncio.create_task(
            ingest_dataset_background(dataset.id, resolved, ext)
        )
        return dataset

    # ── Remote URLs: fetch into memory then ingest ──
    try:
        content_bytes, filename = await fetch_source(data.source)
    except SourceFetchError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in ("csv", "json", "jsonl"):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot determine file type from '{filename}'. "
            "URL must point to a .csv, .json, or .jsonl file.",
        )

    try:
        file_content = content_bytes.decode("utf-8")
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File must be UTF-8 encoded.")

    try:
        dataset = await ingest_dataset(db, data.name, data.description, file_content, ext)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return dataset


@router.get("", response_model=List[DatasetRead])
async def list_datasets(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List all datasets."""
    result = await db.execute(
        select(Dataset).order_by(Dataset.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{dataset_id}", response_model=DatasetRead)
async def get_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Get a single dataset by ID."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return dataset


@router.get("/{dataset_id}/conversations", response_model=List[ConversationRead])
async def list_conversations(
    dataset_id: int,
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    """List conversations in a dataset."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    result = await db.execute(
        select(Conversation)
        .where(Conversation.dataset_id == dataset_id)
        .order_by(Conversation.id)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all()


@router.get(
    "/{dataset_id}/conversations/{conversation_id}",
    response_model=ConversationDetail,
)
async def get_conversation(
    dataset_id: int,
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Get a conversation with all turns and their classifications."""
    result = await db.execute(
        select(Conversation)
        .options(
            selectinload(Conversation.turns).selectinload(Turn.classifications)
        )
        .where(
            Conversation.id == conversation_id,
            Conversation.dataset_id == dataset_id,
        )
    )
    conversation = result.scalar_one_or_none()
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@router.get("/{dataset_id}/runs")
async def list_dataset_runs(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
):
    """List completed experiment runs for a dataset, for the run picker."""
    result = await db.execute(
        select(
            Run.id,
            Run.status,
            Run.execution_date,
            Experiment.name.label("experiment_name"),
            Experiment.classification_method,
            Experiment.taxonomy_id,
        )
        .join(Experiment, Run.experiment_id == Experiment.id)
        .where(
            Experiment.dataset_id == dataset_id,
            Run.status == "completed",
        )
        .order_by(Run.execution_date.desc())
    )
    rows = result.all()
    return [
        {
            "run_id": r.id,
            "experiment_name": r.experiment_name,
            "classification_method": r.classification_method,
            "taxonomy_id": r.taxonomy_id,
            "execution_date": r.execution_date.isoformat() if r.execution_date else None,
        }
        for r in rows
    ]


@router.get("/{dataset_id}/turns/filter-options", response_model=FilterOptionsResponse)
async def turn_filter_options(
    dataset_id: int,
    taxonomy_id: Optional[int] = Query(None),
    run_id: Optional[int] = Query(None),
    db: AsyncSession = Depends(get_db),
):
    """Get distinct filter values for the turn search UI."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return await get_filter_options(db, dataset_id, taxonomy_id, run_id)


@router.get("/{dataset_id}/turns/search", response_model=TurnSearchResponse)
async def turn_search(
    dataset_id: int,
    taxonomy_id: Optional[int] = Query(None),
    run_id: Optional[int] = Query(None),
    keyword: Optional[str] = Query(None),
    speaker: Optional[str] = Query(None),
    intent_labels: Optional[List[str]] = Query(None),
    min_confidence: Optional[float] = Query(None),
    max_confidence: Optional[float] = Query(None),
    ground_truth_intent: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    db: AsyncSession = Depends(get_db),
):
    """Search and filter turns across a dataset."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return await search_turns(
        db,
        dataset_id=dataset_id,
        taxonomy_id=taxonomy_id,
        run_id=run_id,
        keyword=keyword,
        speaker=speaker,
        intent_labels=intent_labels,
        min_confidence=min_confidence,
        max_confidence=max_confidence,
        ground_truth_intent=ground_truth_intent,
        page=page,
        page_size=page_size,
    )


@router.patch("/{dataset_id}", response_model=DatasetRead)
async def update_dataset(
    dataset_id: int,
    data: DatasetUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Update a dataset's name and/or description."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    if data.name is not None:
        dataset.name = data.name
    if data.description is not None:
        dataset.description = data.description

    await db.commit()
    await db.refresh(dataset)
    return dataset


@router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: int, db: AsyncSession = Depends(get_db)):
    """Delete a dataset and all associated data."""
    dataset = await db.get(Dataset, dataset_id)
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    await db.delete(dataset)
    await db.commit()
    return {"detail": "Dataset deleted", "id": dataset_id}
