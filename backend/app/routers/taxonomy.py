import json
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.models import IntentCategory, IntentTaxonomy
from app.schemas.schemas import (
    CategoryExamplesUpdate,
    CategoryMoveRequest,
    CategoryReorderRequest,
    IntentCategoryCreate,
    IntentCategoryRead,
    IntentCategoryUpdate,
    IntentTaxonomyCreate,
    IntentTaxonomyDetail,
    IntentTaxonomyRead,
    IntentTaxonomyUpdate,
    TaxonomyExport,
    TaxonomyImport,
)
from app.services.taxonomy_service import (
    clear_examples_if_becomes_parent,
    export_taxonomy,
    import_taxonomy,
    move_category,
    normalize_category_name,
    reorder_categories,
    validate_examples_for_category,
)

router = APIRouter(prefix="/taxonomies", tags=["taxonomies"])


# ---------------------------------------------------------------------------
# Taxonomy CRUD
# ---------------------------------------------------------------------------

@router.post("", response_model=IntentTaxonomyRead)
async def create_taxonomy(
    data: IntentTaxonomyCreate,
    db: AsyncSession = Depends(get_db),
):
    taxonomy = IntentTaxonomy(
        name=data.name,
        description=data.description,
        tags=json.dumps(data.tags) if data.tags else None,
        metadata_json=json.dumps(data.metadata_json) if data.metadata_json else None,
        priority=data.priority or 0,
        version=1,
    )
    db.add(taxonomy)
    await db.commit()
    await db.refresh(taxonomy)
    return taxonomy


@router.get("", response_model=List[IntentTaxonomyRead])
async def list_taxonomies(
    skip: int = 0,
    limit: int = 100,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(IntentTaxonomy).order_by(IntentTaxonomy.created_at.desc()).offset(skip).limit(limit)
    )
    return result.scalars().all()


@router.get("/{taxonomy_id}", response_model=IntentTaxonomyDetail)
async def get_taxonomy(taxonomy_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(IntentTaxonomy)
        .options(selectinload(IntentTaxonomy.categories))
        .where(IntentTaxonomy.id == taxonomy_id)
    )
    taxonomy = result.scalar_one_or_none()
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return taxonomy


@router.put("/{taxonomy_id}", response_model=IntentTaxonomyRead)
async def update_taxonomy(
    taxonomy_id: int,
    data: IntentTaxonomyUpdate,
    db: AsyncSession = Depends(get_db),
):
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    if data.name is not None:
        taxonomy.name = data.name
    if data.description is not None:
        taxonomy.description = data.description
    if data.tags is not None:
        taxonomy.tags = json.dumps(data.tags)
    if data.metadata_json is not None:
        taxonomy.metadata_json = json.dumps(data.metadata_json)
    if data.priority is not None:
        taxonomy.priority = data.priority

    taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(taxonomy)
    return taxonomy


@router.delete("/{taxonomy_id}")
async def delete_taxonomy(taxonomy_id: int, db: AsyncSession = Depends(get_db)):
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    await db.delete(taxonomy)
    await db.commit()
    return {"detail": "Taxonomy deleted", "id": taxonomy_id}


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------

@router.post("/import", response_model=IntentTaxonomyDetail)
async def import_taxonomy_json(
    data: TaxonomyImport,
    db: AsyncSession = Depends(get_db),
):
    """Import a full taxonomy (with hierarchical categories) from JSON.

    Supports unlimited nesting depth. Examples are only allowed on leaf nodes.
    Colors are auto-assigned when not provided.
    """
    try:
        taxonomy = await import_taxonomy(db, data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Import failed: {str(e)}")

    result = await db.execute(
        select(IntentTaxonomy)
        .options(selectinload(IntentTaxonomy.categories))
        .where(IntentTaxonomy.id == taxonomy.id)
    )
    return result.scalar_one()


@router.get("/{taxonomy_id}/export", response_model=TaxonomyExport)
async def export_taxonomy_json(
    taxonomy_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Export a taxonomy to the standard JSON format (unlimited depth)."""
    result = await export_taxonomy(db, taxonomy_id)
    if not result:
        raise HTTPException(status_code=404, detail="Taxonomy not found")
    return result


# ---------------------------------------------------------------------------
# Category CRUD
# ---------------------------------------------------------------------------

@router.post("/{taxonomy_id}/categories", response_model=IntentCategoryRead)
async def create_category(
    taxonomy_id: int,
    data: IntentCategoryCreate,
    db: AsyncSession = Depends(get_db),
):
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    if data.parent_id is not None:
        parent = await db.get(IntentCategory, data.parent_id)
        if not parent or parent.taxonomy_id != taxonomy_id:
            raise HTTPException(status_code=400, detail="Invalid parent category")
        # Parent gains a child — clear its examples
        await clear_examples_if_becomes_parent(db, data.parent_id)

    # Normalize name: root = UPPER_CASE, child = lower_case
    is_root = data.parent_id is None
    storage_name = normalize_category_name(data.name, is_root)

    # Examples only allowed if this will be a leaf (no children at creation time = always leaf)
    examples_json = json.dumps(data.examples) if data.examples else None

    category = IntentCategory(
        taxonomy_id=taxonomy_id,
        name=storage_name,
        description=data.description,
        color=data.color,
        parent_id=data.parent_id,
        priority=data.priority or 0,
        examples=examples_json,
    )
    db.add(category)

    taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(category)
    return category


@router.put("/{taxonomy_id}/categories/{category_id}", response_model=IntentCategoryRead)
async def update_category(
    taxonomy_id: int,
    category_id: int,
    data: IntentCategoryUpdate,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(IntentCategory, category_id)
    if not category or category.taxonomy_id != taxonomy_id:
        raise HTTPException(status_code=404, detail="Category not found")

    if data.name is not None:
        # Determine root status: use new parent_id if being moved, else current
        effective_parent = data.parent_id if data.parent_id is not None else category.parent_id
        is_root = effective_parent is None
        category.name = normalize_category_name(data.name, is_root)
    if data.description is not None:
        category.description = data.description
    if data.color is not None:
        category.color = data.color
    if data.priority is not None:
        category.priority = data.priority

    if data.parent_id is not None:
        if data.parent_id != category.parent_id:
            new_parent = await db.get(IntentCategory, data.parent_id)
            if not new_parent or new_parent.taxonomy_id != taxonomy_id:
                raise HTTPException(status_code=400, detail="Invalid parent category")
            await clear_examples_if_becomes_parent(db, data.parent_id)
        category.parent_id = data.parent_id

    if data.examples is not None:
        try:
            await validate_examples_for_category(db, category_id, data.examples)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        category.examples = json.dumps(data.examples) if data.examples else None

    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{taxonomy_id}/categories/{category_id}")
async def delete_category(
    taxonomy_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    category = await db.get(IntentCategory, category_id)
    if not category or category.taxonomy_id != taxonomy_id:
        raise HTTPException(status_code=404, detail="Category not found")
    await db.delete(category)

    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    return {"detail": "Category deleted", "id": category_id}


# ---------------------------------------------------------------------------
# Move & Reorder
# ---------------------------------------------------------------------------

@router.put("/{taxonomy_id}/categories/{category_id}/move", response_model=IntentCategoryRead)
async def move_category_endpoint(
    taxonomy_id: int,
    category_id: int,
    data: CategoryMoveRequest,
    db: AsyncSession = Depends(get_db),
):
    """Move a category to a new parent or to root (new_parent_id=null)."""
    try:
        category = await move_category(db, taxonomy_id, category_id, data.new_parent_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    return category


@router.put("/{taxonomy_id}/categories/reorder")
async def reorder_categories_endpoint(
    taxonomy_id: int,
    data: CategoryReorderRequest,
    db: AsyncSession = Depends(get_db),
):
    """Set display order for categories. Pass category IDs in desired order."""
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if not taxonomy:
        raise HTTPException(status_code=404, detail="Taxonomy not found")

    await reorder_categories(db, taxonomy_id, data.category_ids)
    return {"detail": "Categories reordered"}


# ---------------------------------------------------------------------------
# Examples
# ---------------------------------------------------------------------------

@router.put("/{taxonomy_id}/categories/{category_id}/examples", response_model=IntentCategoryRead)
async def set_category_examples(
    taxonomy_id: int,
    category_id: int,
    data: CategoryExamplesUpdate,
    db: AsyncSession = Depends(get_db),
):
    """Set examples on a leaf category. Fails if category has children."""
    category = await db.get(IntentCategory, category_id)
    if not category or category.taxonomy_id != taxonomy_id:
        raise HTTPException(status_code=404, detail="Category not found")

    try:
        await validate_examples_for_category(db, category_id, data.examples)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    category.examples = json.dumps(data.examples) if data.examples else None

    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(category)
    return category


@router.delete("/{taxonomy_id}/categories/{category_id}/examples", response_model=IntentCategoryRead)
async def clear_category_examples(
    taxonomy_id: int,
    category_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Remove all examples from a category."""
    category = await db.get(IntentCategory, category_id)
    if not category or category.taxonomy_id != taxonomy_id:
        raise HTTPException(status_code=404, detail="Category not found")

    category.examples = None

    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(category)
    return category
