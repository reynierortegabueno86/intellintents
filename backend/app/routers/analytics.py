from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.analytics_service import (
    get_conversation_archetypes,
    get_conversation_graph,
    get_intent_distribution,
    get_intent_heatmap,
    get_intent_timeline,
    get_intent_transitions,
    get_summary_metrics,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/summary/{dataset_id}")
async def summary(
    dataset_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await get_summary_metrics(db, dataset_id)


@router.get("/distribution/{dataset_id}/{taxonomy_id}")
async def distribution(
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = Query(None),
    min_confidence: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await get_intent_distribution(
        db, dataset_id, taxonomy_id,
        intent_labels=intent_labels,
        min_confidence=min_confidence,
    )


@router.get("/transitions/{dataset_id}/{taxonomy_id}")
async def transitions(
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = Query(None),
    min_confidence: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await get_intent_transitions(
        db, dataset_id, taxonomy_id,
        intent_labels=intent_labels,
        min_confidence=min_confidence,
    )


@router.get("/heatmap/{dataset_id}/{taxonomy_id}")
async def heatmap(
    dataset_id: int,
    taxonomy_id: int,
    max_turns: Optional[int] = Query(None),
    min_confidence: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await get_intent_heatmap(
        db, dataset_id, taxonomy_id,
        max_turns=max_turns,
        min_confidence=min_confidence,
    )


@router.get("/timeline/{dataset_id}/{taxonomy_id}")
async def timeline(
    dataset_id: int,
    taxonomy_id: int,
    intent_labels: Optional[List[str]] = Query(None),
    min_confidence: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await get_intent_timeline(
        db, dataset_id, taxonomy_id,
        intent_labels=intent_labels,
        min_confidence=min_confidence,
    )


@router.get("/archetypes/{dataset_id}/{taxonomy_id}")
async def archetypes(
    dataset_id: int,
    taxonomy_id: int,
    min_turns: Optional[int] = Query(None),
    max_turns: Optional[int] = Query(None),
    min_confidence: Optional[float] = Query(None),
    db: AsyncSession = Depends(get_db),
) -> List[Dict[str, Any]]:
    return await get_conversation_archetypes(
        db, dataset_id, taxonomy_id,
        min_turns=min_turns,
        max_turns=max_turns,
        min_confidence=min_confidence,
    )


@router.get("/graph/{conversation_id}")
async def graph(
    conversation_id: int,
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    return await get_conversation_graph(db, conversation_id)
