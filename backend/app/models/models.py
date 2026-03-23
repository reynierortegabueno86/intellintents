import datetime
from typing import Optional, List

from sqlalchemy import Integer, String, Text, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    file_type: Mapped[str] = mapped_column(String(10), nullable=False)
    row_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True, default="ready")
    status_detail: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    conversations: Mapped[List["Conversation"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )
    experiments: Mapped[List["Experiment"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan",
        foreign_keys="Experiment.dataset_id",
    )


class Conversation(Base):
    __tablename__ = "conversations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    dataset_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True
    )
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    turn_count: Mapped[int] = mapped_column(Integer, default=0)

    dataset: Mapped["Dataset"] = relationship(back_populates="conversations")
    turns: Mapped[List["Turn"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan",
        order_by="Turn.turn_index"
    )


class Turn(Base):
    __tablename__ = "turns"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    conversation_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False)
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True
    )
    thread_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    ground_truth_intent: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )

    conversation: Mapped["Conversation"] = relationship(back_populates="turns")
    classifications: Mapped[List["Classification"]] = relationship(
        back_populates="turn", cascade="all, delete-orphan"
    )


class IntentTaxonomy(Base):
    __tablename__ = "intent_taxonomies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array of strings
    metadata_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON object
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, nullable=True, onupdate=datetime.datetime.utcnow
    )

    categories: Mapped[List["IntentCategory"]] = relationship(
        back_populates="taxonomy", cascade="all, delete-orphan"
    )


class IntentCategory(Base):
    __tablename__ = "intent_categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    taxonomy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("intent_taxonomies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    color: Mapped[Optional[str]] = mapped_column(String(7), nullable=True)
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("intent_categories.id"), nullable=True, index=True
    )
    priority: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=0)
    examples: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON array, leaf-only

    taxonomy: Mapped["IntentTaxonomy"] = relationship(back_populates="categories")
    parent: Mapped[Optional["IntentCategory"]] = relationship(
        remote_side="IntentCategory.id", backref="children"
    )


class Classification(Base):
    __tablename__ = "classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    turn_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True
    )
    taxonomy_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("intent_taxonomies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    intent_label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    method: Mapped[str] = mapped_column(String(50), nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime, default=datetime.datetime.utcnow
    )

    turn: Mapped["Turn"] = relationship(back_populates="classifications")


class Experiment(Base):
    __tablename__ = "experiments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dataset_id: Mapped[int] = mapped_column(Integer, ForeignKey("datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    taxonomy_id: Mapped[int] = mapped_column(Integer, ForeignKey("intent_taxonomies.id", ondelete="CASCADE"), nullable=False, index=True)
    classification_method: Mapped[str] = mapped_column(String(50), nullable=False)
    classifier_parameters: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string
    created_by: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_favorite: Mapped[bool] = mapped_column(Integer, default=False)  # SQLite boolean
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    dataset: Mapped["Dataset"] = relationship(back_populates="experiments")
    taxonomy: Mapped["IntentTaxonomy"] = relationship()
    runs: Mapped[List["Run"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")
    label_mappings: Mapped[List["LabelMapping"]] = relationship(back_populates="experiment", cascade="all, delete-orphan")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(20), default="pending")  # pending, running, completed, failed
    execution_date: Mapped[Optional[datetime.datetime]] = mapped_column(DateTime, nullable=True)
    runtime_duration: Mapped[Optional[float]] = mapped_column(Float, nullable=True)  # seconds
    configuration_snapshot: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    results_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON
    progress_current: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    progress_total: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    is_favorite: Mapped[bool] = mapped_column(Integer, default=False)
    created_at: Mapped[datetime.datetime] = mapped_column(DateTime, default=datetime.datetime.utcnow)

    experiment: Mapped["Experiment"] = relationship(back_populates="runs")
    run_classifications: Mapped[List["RunClassification"]] = relationship(back_populates="run", cascade="all, delete-orphan")


class LabelMapping(Base):
    __tablename__ = "label_mappings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    experiment_id: Mapped[int] = mapped_column(Integer, ForeignKey("experiments.id", ondelete="CASCADE"), nullable=False, index=True)
    classifier_label: Mapped[str] = mapped_column(String(255), nullable=False)
    taxonomy_label: Mapped[str] = mapped_column(String(255), nullable=False)

    experiment: Mapped["Experiment"] = relationship(back_populates="label_mappings")


class RunClassification(Base):
    __tablename__ = "run_classifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    run_id: Mapped[int] = mapped_column(Integer, ForeignKey("runs.id", ondelete="CASCADE"), nullable=False, index=True)
    conversation_id: Mapped[int] = mapped_column(Integer, ForeignKey("conversations.id", ondelete="CASCADE"), nullable=False, index=True)
    turn_id: Mapped[int] = mapped_column(Integer, ForeignKey("turns.id", ondelete="CASCADE"), nullable=False, index=True)
    speaker: Mapped[str] = mapped_column(String(50), nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    intent_label: Mapped[str] = mapped_column(String(255), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)

    run: Mapped["Run"] = relationship(back_populates="run_classifications")
