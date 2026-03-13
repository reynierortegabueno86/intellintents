"""Tests for taxonomy service (import, export, move, reorder, examples)."""

import json

import pytest
import pytest_asyncio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import IntentCategory, IntentTaxonomy
from app.schemas.schemas import TaxonomyCategoryImport, TaxonomyImport
from app.services.taxonomy_service import (
    export_taxonomy,
    import_taxonomy,
    move_category,
    normalize_category_name,
    reorder_categories,
    validate_examples_for_category,
)


# ──────────────────────────────────────────────────────────
# normalize_category_name
# ──────────────────────────────────────────────────────────

def test_normalize_root_uppercase():
    assert normalize_category_name("Hello World", is_root=True) == "HELLO_WORLD"


def test_normalize_child_lowercase():
    assert normalize_category_name("Hello World", is_root=False) == "hello_world"


def test_normalize_strips_whitespace():
    assert normalize_category_name("  some name  ", is_root=True) == "SOME_NAME"


def test_normalize_collapses_spaces():
    assert normalize_category_name("a   b   c", is_root=False) == "a_b_c"


# ──────────────────────────────────────────────────────────
# import_taxonomy
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_import_flat(db_session):
    """Import a taxonomy with flat categories."""
    data = TaxonomyImport(
        name="Test",
        description="Test taxonomy",
        categories=[
            TaxonomyCategoryImport(name="Greeting", description="Hi"),
            TaxonomyCategoryImport(name="Complaint", description="Bad"),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    assert tax.id is not None
    assert tax.name == "Test"

    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = result.scalars().all()
    assert len(cats) == 2
    names = {c.name for c in cats}
    assert "GREETING" in names  # root names are uppercased
    assert "COMPLAINT" in names


@pytest.mark.asyncio
async def test_import_nested(db_session):
    """Import a taxonomy with nested categories."""
    data = TaxonomyImport(
        name="Nested",
        categories=[
            TaxonomyCategoryImport(
                name="Support",
                children=[
                    TaxonomyCategoryImport(name="Billing"),
                    TaxonomyCategoryImport(name="Technical"),
                ],
            ),
        ],
    )
    tax = await import_taxonomy(db_session, data)

    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = result.scalars().all()
    assert len(cats) == 3  # Support + Billing + Technical
    children = [c for c in cats if c.parent_id is not None]
    assert len(children) == 2


@pytest.mark.asyncio
async def test_import_with_examples_on_leaf(db_session):
    """Examples on leaf nodes are preserved."""
    data = TaxonomyImport(
        name="WithExamples",
        categories=[
            TaxonomyCategoryImport(
                name="Greeting",
                examples=["Hello", "Hi there"],
            ),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cat = result.scalar_one()
    assert json.loads(cat.examples) == ["Hello", "Hi there"]


@pytest.mark.asyncio
async def test_import_examples_on_parent_raises(db_session):
    """Examples on non-leaf nodes raise ValueError."""
    data = TaxonomyImport(
        name="Bad",
        categories=[
            TaxonomyCategoryImport(
                name="Parent",
                examples=["Should fail"],
                children=[TaxonomyCategoryImport(name="Child")],
            ),
        ],
    )
    with pytest.raises(ValueError, match="both children and examples"):
        await import_taxonomy(db_session, data)


@pytest.mark.asyncio
async def test_import_auto_assigns_colors(db_session):
    """Colors are auto-assigned when not provided."""
    data = TaxonomyImport(
        name="Colors",
        categories=[
            TaxonomyCategoryImport(name="A"),
            TaxonomyCategoryImport(name="B"),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = result.scalars().all()
    colors = [c.color for c in cats]
    assert all(c is not None for c in colors)
    assert colors[0] != colors[1]  # Different colors for different categories


# ──────────────────────────────────────────────────────────
# export_taxonomy
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_export_roundtrip(db_session):
    """Import then export produces consistent structure."""
    data = TaxonomyImport(
        name="Roundtrip",
        description="Test roundtrip",
        categories=[
            TaxonomyCategoryImport(
                name="Category A",
                children=[TaxonomyCategoryImport(name="Sub1")],
            ),
            TaxonomyCategoryImport(name="Category B"),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    exported = await export_taxonomy(db_session, tax.id)
    assert exported is not None
    assert exported.name == "Roundtrip"
    assert len(exported.categories) == 2


@pytest.mark.asyncio
async def test_export_nonexistent(db_session):
    """Export of nonexistent taxonomy returns None."""
    result = await export_taxonomy(db_session, 99999)
    assert result is None


# ──────────────────────────────────────────────────────────
# move_category
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_move_category_to_new_parent(db_session):
    """Move a category under a new parent."""
    data = TaxonomyImport(
        name="Move Test",
        categories=[
            TaxonomyCategoryImport(name="A"),
            TaxonomyCategoryImport(name="B"),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = {c.name: c for c in result.scalars().all()}

    moved = await move_category(db_session, tax.id, cats["B"].id, cats["A"].id)
    assert moved.parent_id == cats["A"].id


@pytest.mark.asyncio
async def test_move_category_circular_raises(db_session):
    """Moving a parent under its own child raises error."""
    data = TaxonomyImport(
        name="Circular",
        categories=[
            TaxonomyCategoryImport(
                name="Parent",
                children=[TaxonomyCategoryImport(name="Child")],
            ),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = {c.name: c for c in result.scalars().all()}

    with pytest.raises(ValueError, match="descendant"):
        await move_category(db_session, tax.id, cats["PARENT"].id, cats["child"].id)


# ──────────────────────────────────────────────────────────
# reorder_categories
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reorder(db_session):
    """Reorder sets priority values."""
    data = TaxonomyImport(
        name="Reorder",
        categories=[
            TaxonomyCategoryImport(name="A"),
            TaxonomyCategoryImport(name="B"),
            TaxonomyCategoryImport(name="C"),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cats = result.scalars().all()
    # Reverse order
    reversed_ids = [c.id for c in reversed(cats)]
    await reorder_categories(db_session, tax.id, reversed_ids)

    result = await db_session.execute(
        select(IntentCategory)
        .where(IntentCategory.taxonomy_id == tax.id)
        .order_by(IntentCategory.priority)
    )
    reordered = result.scalars().all()
    assert reordered[0].id == reversed_ids[0]


# ──────────────────────────────────────────────────────────
# validate_examples_for_category
# ──────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_validate_examples_leaf_ok(db_session):
    """Leaf category can have examples."""
    data = TaxonomyImport(
        name="ExVal",
        categories=[TaxonomyCategoryImport(name="Leaf")],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(IntentCategory.taxonomy_id == tax.id)
    )
    cat = result.scalar_one()
    # Should not raise
    await validate_examples_for_category(db_session, cat.id, ["example1"])


@pytest.mark.asyncio
async def test_validate_examples_parent_raises(db_session):
    """Non-leaf category cannot have examples."""
    data = TaxonomyImport(
        name="ExValP",
        categories=[
            TaxonomyCategoryImport(
                name="Parent",
                children=[TaxonomyCategoryImport(name="Child")],
            ),
        ],
    )
    tax = await import_taxonomy(db_session, data)
    result = await db_session.execute(
        select(IntentCategory).where(
            IntentCategory.taxonomy_id == tax.id,
            IntentCategory.parent_id.is_(None),
        )
    )
    parent = result.scalar_one()
    with pytest.raises(ValueError, match="children"):
        await validate_examples_for_category(db_session, parent.id, ["bad"])
