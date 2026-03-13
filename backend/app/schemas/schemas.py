import datetime
from typing import Optional, List, Dict, Any

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# Dataset
# ---------------------------------------------------------------------------
def _validate_name(v: str) -> str:
    v = v.strip()
    if not v:
        raise ValueError("Name must not be empty")
    if len(v) > 255:
        raise ValueError("Name must be 255 characters or fewer")
    return v


class DatasetCreate(BaseModel):
    name: str
    description: Optional[str] = None
    file_type: str = "csv"

    _check_name = field_validator("name")(_validate_name)


class DatasetRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    created_at: datetime.datetime
    file_type: str
    row_count: int

    model_config = {"from_attributes": True}


class DatasetUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None


class DatasetUpload(BaseModel):
    name: str
    description: Optional[str] = None


# ---------------------------------------------------------------------------
# Conversation
# ---------------------------------------------------------------------------
class ConversationCreate(BaseModel):
    external_id: Optional[str] = None


class ConversationRead(BaseModel):
    id: int
    dataset_id: int
    external_id: Optional[str] = None
    created_at: datetime.datetime
    turn_count: int

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Turn
# ---------------------------------------------------------------------------
class TurnCreate(BaseModel):
    turn_index: int
    speaker: str
    text: str
    timestamp: Optional[datetime.datetime] = None
    thread_id: Optional[str] = None
    ground_truth_intent: Optional[str] = None


class TurnRead(BaseModel):
    id: int
    conversation_id: int
    turn_index: int
    speaker: str
    text: str
    timestamp: Optional[datetime.datetime] = None
    thread_id: Optional[str] = None
    ground_truth_intent: Optional[str] = None

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Classification
# ---------------------------------------------------------------------------
class ClassificationCreate(BaseModel):
    turn_id: int
    taxonomy_id: int
    intent_label: str
    confidence: float
    method: str
    explanation: Optional[str] = None


class ClassificationRead(BaseModel):
    id: int
    turn_id: int
    taxonomy_id: int
    intent_label: str
    confidence: float
    method: str
    explanation: Optional[str] = None
    created_at: datetime.datetime

    model_config = {"from_attributes": True}


class ClassificationRequest(BaseModel):
    dataset_id: int
    taxonomy_id: int
    method: str = "rule_based"
    config: Optional[Dict[str, Any]] = None


class SaveExperimentRequest(BaseModel):
    """Save a classification configuration as an experiment for later execution."""
    name: str
    description: Optional[str] = None
    dataset_id: int
    taxonomy_id: int
    method: str = "rule_based"
    config: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None

    _check_name = field_validator("name")(_validate_name)


# ---------------------------------------------------------------------------
# Intent Taxonomy
# ---------------------------------------------------------------------------
class IntentTaxonomyCreate(BaseModel):
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0

    _check_name = field_validator("name")(_validate_name)


class IntentTaxonomyRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0
    version: int = 1
    created_at: datetime.datetime
    updated_at: Optional[datetime.datetime] = None

    model_config = {"from_attributes": True}

    @field_validator("tags", mode="before")
    @classmethod
    def _parse_tags(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return None
        return v

    @field_validator("metadata_json", mode="before")
    @classmethod
    def _parse_metadata(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return None
        return v


class IntentTaxonomyUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    priority: Optional[int] = None


# ---------------------------------------------------------------------------
# Intent Category
# ---------------------------------------------------------------------------
class IntentCategoryCreate(BaseModel):
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None
    priority: Optional[int] = 0
    examples: Optional[List[str]] = None

    _check_name = field_validator("name")(_validate_name)


class IntentCategoryRead(BaseModel):
    id: int
    taxonomy_id: int
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None
    priority: Optional[int] = 0
    examples: Optional[List[str]] = None

    model_config = {"from_attributes": True}

    @field_validator("examples", mode="before")
    @classmethod
    def _parse_examples(cls, v):
        if isinstance(v, str):
            import json
            try:
                return json.loads(v)
            except Exception:
                return None
        return v


class IntentCategoryUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    color: Optional[str] = None
    parent_id: Optional[int] = None
    priority: Optional[int] = None
    examples: Optional[List[str]] = None


# ---------------------------------------------------------------------------
# Taxonomy with categories
# ---------------------------------------------------------------------------
class IntentTaxonomyDetail(IntentTaxonomyRead):
    categories: List[IntentCategoryRead] = []


# ---------------------------------------------------------------------------
# Taxonomy JSON Import / Export
# ---------------------------------------------------------------------------
class TaxonomyCategoryImport(BaseModel):
    """A category node in the import JSON. Supports unlimited nesting depth."""
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    priority: Optional[int] = 0
    examples: Optional[List[str]] = None
    children: Optional[List["TaxonomyCategoryImport"]] = None

    _check_name = field_validator("name")(_validate_name)


class TaxonomyImport(BaseModel):
    """Top-level schema for importing a full taxonomy from JSON."""
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0
    categories: List[TaxonomyCategoryImport] = []

    _check_name = field_validator("name")(_validate_name)


class TaxonomyCategoryExport(BaseModel):
    """A category node in the export JSON. Supports unlimited nesting depth."""
    name: str
    description: Optional[str] = None
    color: Optional[str] = None
    priority: Optional[int] = 0
    examples: Optional[List[str]] = None
    children: Optional[List["TaxonomyCategoryExport"]] = None


class TaxonomyExport(BaseModel):
    """Full taxonomy export."""
    name: str
    description: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata_json: Optional[Dict[str, Any]] = None
    priority: Optional[int] = 0
    version: int = 1
    categories: List[TaxonomyCategoryExport] = []


class CategoryMoveRequest(BaseModel):
    """Move a category to a new parent (or to root if new_parent_id is None)."""
    new_parent_id: Optional[int] = None


class CategoryReorderRequest(BaseModel):
    """Reorder categories under a parent. List of category IDs in desired order."""
    category_ids: List[int]


class CategoryExamplesUpdate(BaseModel):
    """Set examples on a leaf node."""
    examples: List[str]


# ---------------------------------------------------------------------------
# Turn with classifications
# ---------------------------------------------------------------------------
class TurnDetail(TurnRead):
    classifications: List[ClassificationRead] = []


# ---------------------------------------------------------------------------
# Conversation detail with nested turns
# ---------------------------------------------------------------------------
class ConversationDetail(ConversationRead):
    turns: List[TurnDetail] = []


# ---------------------------------------------------------------------------
# Analytics
# ---------------------------------------------------------------------------
class AnalyticsResponse(BaseModel):
    total_conversations: int = 0
    total_turns: int = 0
    avg_turns_per_conversation: float = 0.0
    unique_intents: int = 0
    intent_entropy: float = 0.0


class IntentDistributionItem(BaseModel):
    intent: str
    count: int
    percentage: float


class IntentTransition(BaseModel):
    from_intent: str
    to_intent: str
    count: int
    probability: float


class HeatmapCell(BaseModel):
    turn_index: int
    intent: str
    count: int


class TimelinePoint(BaseModel):
    time_bucket: str
    intent: str
    count: int


class ArchetypeItem(BaseModel):
    archetype_id: int
    pattern: List[str]
    count: int
    example_conversation_ids: List[int]


class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # "turn" or "intent"
    metadata: Dict[str, Any] = {}


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    weight: float = 1.0


class ConversationGraph(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------
class ExperimentCreate(BaseModel):
    name: str
    description: Optional[str] = None
    dataset_id: int
    taxonomy_id: int
    classification_method: str
    classifier_parameters: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None

    _check_name = field_validator("name")(_validate_name)


class ExperimentUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: Optional[int] = None
    taxonomy_id: Optional[int] = None
    classification_method: Optional[str] = None
    classifier_parameters: Optional[Dict[str, Any]] = None
    is_favorite: Optional[bool] = None


class ExperimentRead(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dataset_id: int
    taxonomy_id: int
    classification_method: str
    classifier_parameters: Optional[Dict[str, Any]] = None
    created_by: Optional[str] = None
    is_favorite: bool = False
    created_at: datetime.datetime
    run_count: int = 0
    last_run_date: Optional[datetime.datetime] = None
    dataset_name: Optional[str] = None
    taxonomy_name: Optional[str] = None
    model_config = {"from_attributes": True}


class RunRead(BaseModel):
    id: int
    experiment_id: int
    status: str
    execution_date: Optional[datetime.datetime] = None
    runtime_duration: Optional[float] = None
    configuration_snapshot: Optional[Dict[str, Any]] = None
    results_summary: Optional[Dict[str, Any]] = None
    is_favorite: bool = False
    created_at: datetime.datetime
    model_config = {"from_attributes": True}


class LabelMappingCreate(BaseModel):
    classifier_label: str
    taxonomy_label: str


class LabelMappingRead(BaseModel):
    id: int
    experiment_id: int
    classifier_label: str
    taxonomy_label: str
    model_config = {"from_attributes": True}


class RunClassificationRead(BaseModel):
    id: int
    run_id: int
    conversation_id: int
    turn_id: int
    speaker: str
    text: str
    intent_label: str
    confidence: float
    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Turn Search
# ---------------------------------------------------------------------------
class TurnSearchResult(BaseModel):
    turn_id: int
    conversation_id: int
    conversation_external_id: Optional[str] = None
    turn_index: int
    speaker: str
    text: str
    ground_truth_intent: Optional[str] = None
    intent_label: Optional[str] = None
    confidence: Optional[float] = None


class TurnSearchResponse(BaseModel):
    results: List[TurnSearchResult]
    total: int
    page: int
    page_size: int
    total_pages: int


class FilterOptionsResponse(BaseModel):
    speakers: List[str]
    intent_labels: List[str]
    ground_truth_intents: List[str]
    confidence_range: Dict[str, float]
