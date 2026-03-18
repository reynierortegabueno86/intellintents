"""
Taxonomy import/export service.

Handles importing a full taxonomy (with hierarchical categories at unlimited
depth) from a JSON structure, and exporting back to the same format.
Auto-assigns colors to categories that don't specify one.

Enforces the leaf-only examples constraint: examples are only stored on
nodes that have no children.
"""

import json
from typing import Dict, List, Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import IntentCategory, IntentTaxonomy
from app.schemas.schemas import (
    TaxonomyCategoryExport,
    TaxonomyCategoryImport,
    TaxonomyExport,
    TaxonomyImport,
)

# ---------------------------------------------------------------------------
# Color palette — 9 distinct hues for top-level categories, with lighter
# variants auto-generated for children.
# ---------------------------------------------------------------------------
_TOP_LEVEL_PALETTE = [
    "#4A90D9",  # blue
    "#50B86C",  # green
    "#E8913A",  # orange
    "#D94F4F",  # red
    "#9B59B6",  # purple
    "#1ABC9C",  # teal
    "#F39C12",  # amber
    "#E74C8B",  # pink
    "#34696D",  # dark teal
]

_CHILD_PALETTES = {
    "#4A90D9": ["#6BA3E3", "#8BB7ED", "#ABCBF7", "#C5DAFA", "#DEEAFD"],
    "#50B86C": ["#6CC685", "#88D49E", "#A4E2B7", "#C0F0D0", "#D8F7E3"],
    "#E8913A": ["#EDA55E", "#F2B982", "#F7CDA6", "#FCE1CA", "#FEF0E4"],
    "#D94F4F": ["#E17272", "#E99595", "#F1B8B8", "#F9DBDB", "#FCEDED"],
    "#9B59B6": ["#AF7AC5", "#C39BD3", "#D7BCE2", "#EBDEF0", "#F4ECF7"],
    "#1ABC9C": ["#48C9AD", "#76D7BE", "#A3E4CF", "#D1F2E0", "#E8F8F0"],
    "#F39C12": ["#F5B041", "#F7C470", "#F9D89F", "#FBECCE", "#FDF5E6"],
    "#E74C8B": ["#EC6FA3", "#F192BB", "#F6B5D3", "#FBD8EB", "#FDECF5"],
    "#34696D": ["#4D8387", "#669DA1", "#80B7BB", "#99D1D5", "#B3EBEF"],
}


def _assign_color(
    category_index: int,
    child_index: Optional[int] = None,
) -> str:
    """Pick a color from the palette."""
    top_color = _TOP_LEVEL_PALETTE[category_index % len(_TOP_LEVEL_PALETTE)]
    if child_index is None:
        return top_color
    variants = _CHILD_PALETTES.get(top_color, [top_color])
    return variants[child_index % len(variants)]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _serialize_json(value) -> Optional[str]:
    """Serialize a Python object to JSON string for storage."""
    if value is None:
        return None
    return json.dumps(value)


def normalize_category_name(name: str, is_root: bool) -> str:
    """Normalize a category name for DB storage.

    Root categories (parent_id=None): UPPER_CASE_WITH_UNDERSCORES
    Subcategories (has parent): lower_case_with_underscores
    """
    import re
    # Replace whitespace with underscores, collapse multiple
    normalized = re.sub(r'\s+', '_', name.strip())
    return normalized.upper() if is_root else normalized.lower()


async def _has_children(db: AsyncSession, category_id: int) -> bool:
    """Check whether a category has any child categories."""
    result = await db.execute(
        select(IntentCategory.id)
        .where(IntentCategory.parent_id == category_id)
        .limit(1)
    )
    return result.scalar_one_or_none() is not None


def _validate_examples_on_import(node: TaxonomyCategoryImport) -> None:
    """Raise ValueError if examples are set on a non-leaf node."""
    has_children = bool(node.children)
    if has_children and node.examples:
        raise ValueError(
            f"Category '{node.name}' has both children and examples. "
            "Examples are only allowed on leaf nodes (nodes without children)."
        )
    for child in (node.children or []):
        _validate_examples_on_import(child)


# ---------------------------------------------------------------------------
# Import — recursive, unlimited depth
# ---------------------------------------------------------------------------

async def import_taxonomy(
    db: AsyncSession,
    data: TaxonomyImport,
) -> IntentTaxonomy:
    """Create a full taxonomy with categories from a JSON import structure.

    - Supports unlimited nesting depth.
    - Colors are auto-assigned when not provided.
    - Examples are only allowed on leaf nodes.
    """
    # Validate examples constraint across the entire tree
    for cat in data.categories:
        _validate_examples_on_import(cat)

    taxonomy = IntentTaxonomy(
        name=data.name,
        description=data.description,
        tags=_serialize_json(data.tags),
        metadata_json=_serialize_json(data.metadata_json),
        priority=data.priority or 0,
        version=1,
    )
    db.add(taxonomy)
    await db.flush()

    async def _insert_recursive(
        nodes: List[TaxonomyCategoryImport],
        parent_id: Optional[int],
        top_level_index: int,
        depth: int,
    ) -> int:
        """Insert nodes recursively. Returns the next top_level_index."""
        for child_idx, node in enumerate(nodes):
            if depth == 0:
                color = node.color or _assign_color(top_level_index)
            else:
                color = node.color or _assign_color(top_level_index, child_idx)

            is_leaf = not node.children
            is_root = parent_id is None
            storage_name = normalize_category_name(node.name, is_root)
            examples_json = _serialize_json(node.examples) if is_leaf and node.examples else None

            category = IntentCategory(
                taxonomy_id=taxonomy.id,
                name=storage_name,
                description=node.description,
                color=color,
                parent_id=parent_id,
                priority=node.priority or 0,
                examples=examples_json,
            )
            db.add(category)
            await db.flush()

            if node.children:
                await _insert_recursive(
                    node.children, category.id, top_level_index, depth + 1
                )

            if depth == 0:
                top_level_index += 1

        return top_level_index

    await _insert_recursive(data.categories, None, 0, 0)

    await db.commit()
    await db.refresh(taxonomy)
    return taxonomy


# ---------------------------------------------------------------------------
# Export — recursive, unlimited depth
# ---------------------------------------------------------------------------

async def export_taxonomy(
    db: AsyncSession,
    taxonomy_id: int,
) -> Optional[TaxonomyExport]:
    """Export a taxonomy to the standard JSON structure (unlimited depth)."""
    result = await db.execute(
        select(IntentTaxonomy)
        .options(selectinload(IntentTaxonomy.categories))
        .where(IntentTaxonomy.id == taxonomy_id)
    )
    taxonomy = result.scalar_one_or_none()
    if not taxonomy:
        return None

    # Build lookup: parent_id -> list of children
    children_by_parent: Dict[Optional[int], List[IntentCategory]] = {}
    for cat in taxonomy.categories:
        children_by_parent.setdefault(cat.parent_id, []).append(cat)

    # Sort each group by priority then name
    for key in children_by_parent:
        children_by_parent[key].sort(key=lambda c: (c.priority or 0, c.name))

    def _build_tree(parent_id: Optional[int]) -> List[TaxonomyCategoryExport]:
        nodes = children_by_parent.get(parent_id, [])
        result = []
        for node in nodes:
            kids = _build_tree(node.id)
            examples = None
            if node.examples:
                try:
                    examples = json.loads(node.examples)
                except Exception:
                    examples = None
            result.append(TaxonomyCategoryExport(
                name=node.name,
                description=node.description,
                color=node.color,
                priority=node.priority or 0,
                examples=examples if not kids else None,  # strip if non-leaf
                children=kids or None,
            ))
        return result

    # Parse taxonomy-level JSON fields
    tags = None
    if taxonomy.tags:
        try:
            tags = json.loads(taxonomy.tags)
        except Exception:
            pass

    metadata = None
    if taxonomy.metadata_json:
        try:
            metadata = json.loads(taxonomy.metadata_json)
        except Exception:
            pass

    return TaxonomyExport(
        name=taxonomy.name,
        description=taxonomy.description,
        tags=tags,
        metadata_json=metadata,
        priority=taxonomy.priority or 0,
        version=taxonomy.version or 1,
        categories=_build_tree(None),
    )


# ---------------------------------------------------------------------------
# Examples enforcement
# ---------------------------------------------------------------------------

async def validate_examples_for_category(
    db: AsyncSession,
    category_id: int,
    examples: Optional[List[str]],
) -> None:
    """Raise ValueError if trying to set examples on a non-leaf category."""
    if not examples:
        return
    if await _has_children(db, category_id):
        raise ValueError(
            "Cannot set examples on a category that has children. "
            "Examples are only allowed on leaf nodes."
        )


async def clear_examples_if_becomes_parent(
    db: AsyncSession,
    parent_id: int,
) -> None:
    """If a category gains children, clear its examples (leaf→parent transition)."""
    parent = await db.get(IntentCategory, parent_id)
    if parent and parent.examples:
        parent.examples = None


# ---------------------------------------------------------------------------
# Move category
# ---------------------------------------------------------------------------

async def move_category(
    db: AsyncSession,
    taxonomy_id: int,
    category_id: int,
    new_parent_id: Optional[int],
) -> IntentCategory:
    """Move a category to a new parent (or to root)."""
    category = await db.get(IntentCategory, category_id)
    if not category or category.taxonomy_id != taxonomy_id:
        raise ValueError("Category not found")

    if new_parent_id is not None:
        # Validate new parent exists and belongs to same taxonomy
        new_parent = await db.get(IntentCategory, new_parent_id)
        if not new_parent or new_parent.taxonomy_id != taxonomy_id:
            raise ValueError("Invalid target parent")

        # Prevent circular reference: new_parent cannot be a descendant of category
        if await _is_descendant(db, new_parent_id, category_id):
            raise ValueError("Cannot move a category under its own descendant")

        # If new parent had examples, clear them (it's becoming non-leaf)
        await clear_examples_if_becomes_parent(db, new_parent_id)

    category.parent_id = new_parent_id

    # Bump taxonomy version
    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
    await db.refresh(category)
    return category


async def _is_descendant(db: AsyncSession, candidate_id: int, ancestor_id: int) -> bool:
    """Check if candidate_id is a descendant of ancestor_id."""
    current = candidate_id
    visited = set()
    while current is not None:
        if current == ancestor_id:
            return True
        if current in visited:
            break
        visited.add(current)
        cat = await db.get(IntentCategory, current)
        if not cat:
            break
        current = cat.parent_id
    return False


# ---------------------------------------------------------------------------
# Reorder categories
# ---------------------------------------------------------------------------

async def reorder_categories(
    db: AsyncSession,
    taxonomy_id: int,
    category_ids: List[int],
) -> None:
    """Set priority values based on the order of category_ids."""
    for idx, cat_id in enumerate(category_ids):
        cat = await db.get(IntentCategory, cat_id)
        if cat and cat.taxonomy_id == taxonomy_id:
            cat.priority = idx

    taxonomy = await db.get(IntentTaxonomy, taxonomy_id)
    if taxonomy:
        taxonomy.version = (taxonomy.version or 1) + 1

    await db.commit()
