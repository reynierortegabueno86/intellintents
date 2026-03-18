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
    get_run_results,
)

router = APIRouter(prefix="/experiments", tags=["experiments"])


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
        "is_favorite": bool(run.is_favorite),
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }
