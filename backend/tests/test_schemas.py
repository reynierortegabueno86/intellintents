"""Tests for Pydantic schema validation (BUG-004 fixes)."""
import pytest
from pydantic import ValidationError

from app.schemas.schemas import (
    DatasetCreate,
    IntentTaxonomyCreate,
    IntentCategoryCreate,
    ExperimentCreate,
    ClassificationRequest,
)


class TestNameValidation:
    """Verify empty/whitespace names are rejected across all create schemas."""

    @pytest.mark.parametrize("name", ["", "   ", "\t", "\n"])
    def test_dataset_rejects_empty_name(self, name):
        with pytest.raises(ValidationError, match="Name must not be empty"):
            DatasetCreate(name=name)

    @pytest.mark.parametrize("name", ["", "   ", "\t"])
    def test_taxonomy_rejects_empty_name(self, name):
        with pytest.raises(ValidationError, match="Name must not be empty"):
            IntentTaxonomyCreate(name=name)

    @pytest.mark.parametrize("name", ["", "   "])
    def test_category_rejects_empty_name(self, name):
        with pytest.raises(ValidationError, match="Name must not be empty"):
            IntentCategoryCreate(name=name)

    @pytest.mark.parametrize("name", ["", "   "])
    def test_experiment_rejects_empty_name(self, name):
        with pytest.raises(ValidationError, match="Name must not be empty"):
            ExperimentCreate(
                name=name,
                dataset_id=1,
                taxonomy_id=1,
                classification_method="rule_based",
            )

    def test_name_too_long(self):
        long_name = "x" * 256
        with pytest.raises(ValidationError, match="255 characters"):
            DatasetCreate(name=long_name)

    def test_valid_name_passes(self):
        d = DatasetCreate(name="My Dataset")
        assert d.name == "My Dataset"

    def test_name_is_stripped(self):
        d = DatasetCreate(name="  padded  ")
        assert d.name == "padded"


class TestClassificationRequest:
    def test_defaults(self):
        req = ClassificationRequest(dataset_id=1, taxonomy_id=1)
        assert req.method == "rule_based"
        assert req.config is None

    def test_with_config(self):
        req = ClassificationRequest(
            dataset_id=1, taxonomy_id=1, method="zero_shot", config={"model": "gpt-4o"}
        )
        assert req.config == {"model": "gpt-4o"}
