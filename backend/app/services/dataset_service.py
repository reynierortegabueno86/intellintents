import csv
import io
import json
import datetime
from typing import List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Dataset, Conversation, Turn


def parse_csv(file_content: str) -> List[Dict[str, Any]]:
    """
    Parse CSV content into a list of conversations with turns.

    Expected columns: conversation_id, turn_index, speaker, text
    Optional columns: timestamp, thread_id, ground_truth_intent
    """
    reader = csv.DictReader(io.StringIO(file_content))
    conversations: Dict[str, List[Dict[str, Any]]] = {}

    for row in reader:
        conv_id = row.get("conversation_id", row.get("external_id", "default"))
        if conv_id not in conversations:
            conversations[conv_id] = []

        turn = _normalize_turn(row, len(conversations[conv_id]))
        conversations[conv_id].append(turn)

    result = []
    for ext_id, turns in conversations.items():
        turns.sort(key=lambda t: t["turn_index"])
        result.append({"external_id": ext_id, "turns": turns})

    return result


def parse_json(file_content: str) -> List[Dict[str, Any]]:
    """
    Parse JSON content into a list of conversations with turns.

    Supports two formats:
    1. List of conversation objects with 'turns' array.
    2. Flat list of turn objects with 'conversation_id' field.
    """
    data = json.loads(file_content)

    if isinstance(data, list) and len(data) > 0:
        # Format 1: list of conversations
        if "turns" in data[0]:
            result = []
            for conv in data:
                turns = [_normalize_turn(t, i) for i, t in enumerate(conv.get("turns", []))]
                result.append({
                    "external_id": conv.get(
                        "external_id", conv.get("conversation_id", str(len(result)))
                    ),
                    "turns": turns,
                })
            return result

        # Format 2: flat list of turns
        if "conversation_id" in data[0] or "external_id" in data[0]:
            conversations: Dict[str, List[Dict[str, Any]]] = {}
            for row in data:
                conv_id = row.get("conversation_id", row.get("external_id", "default"))
                if conv_id not in conversations:
                    conversations[conv_id] = []
                conversations[conv_id].append(_normalize_turn(row, len(conversations[conv_id])))
            result = []
            for ext_id, turns in conversations.items():
                turns.sort(key=lambda t: t["turn_index"])
                result.append({"external_id": ext_id, "turns": turns})
            return result

    raise ValueError(
        "Unsupported JSON format. Expected list of conversations or list of turns."
    )


def _extract_turn_text(turn: Dict[str, Any]) -> str:
    """
    Extract the best text representation from a turn.

    Supports:
    - Simple fields: text, message, content_text
    - Structured content_blocks: list of {type, text} objects
    - content as a plain string
    """
    # Direct text fields
    text = turn.get("text") or turn.get("message") or turn.get("content_text")
    if text:
        return text.strip()

    # content_blocks: concatenate all text parts
    blocks = turn.get("content_blocks")
    if isinstance(blocks, list) and blocks:
        parts = []
        for block in blocks:
            if isinstance(block, dict):
                part = block.get("text") or block.get("raw") or ""
                if part:
                    parts.append(part.strip())
            elif isinstance(block, str):
                parts.append(block.strip())
        if parts:
            return "\n".join(parts)

    # content as plain string
    content = turn.get("content")
    if isinstance(content, str) and content.strip():
        return content.strip()

    return ""


def _normalize_turn(turn: Dict[str, Any], index: int) -> Dict[str, Any]:
    """Normalize a turn dict from any supported format into the internal schema."""
    return {
        "turn_index": turn.get("turn_index", index),
        "speaker": turn.get("speaker", turn.get("role", "unknown")),
        "text": _extract_turn_text(turn),
        "timestamp": turn.get("timestamp", turn.get("created_at")),
        "thread_id": turn.get("thread_id"),
        "ground_truth_intent": turn.get("ground_truth_intent", turn.get("intent")),
    }


def parse_jsonl(file_content: str) -> List[Dict[str, Any]]:
    """
    Parse JSONL content (one JSON object per line) into conversations.

    Each line must be a conversation record with a 'turns' array.
    Designed for chat-platform exports (e.g. with content_text,
    content_blocks, role, metadata fields).

    Field mapping:
      conversation_id → external_id
      role            → speaker
      content_text    → text (fallback: content_blocks → concatenated text)
      created_at      → timestamp
      thread_id       → thread_id
    """
    result = []

    for line_num, line in enumerate(file_content.splitlines(), 1):
        line = line.strip()
        if not line:
            continue

        try:
            conv = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON on line {line_num}: {e}")

        if not isinstance(conv, dict):
            raise ValueError(f"Line {line_num}: expected a JSON object, got {type(conv).__name__}")

        raw_turns = conv.get("turns", [])
        if not isinstance(raw_turns, list):
            raise ValueError(f"Line {line_num}: 'turns' must be an array")

        turns = [_normalize_turn(t, i) for i, t in enumerate(raw_turns)]

        external_id = conv.get("conversation_id") or conv.get("external_id") or str(line_num)

        result.append({
            "external_id": str(external_id),
            "turns": turns,
        })

    return result


def validate_schema(data: List[Dict[str, Any]]) -> Tuple[bool, str]:
    """Validate parsed conversation data."""
    if not data:
        return False, "No conversations found in data."

    for i, conv in enumerate(data):
        if "turns" not in conv:
            return False, f"Conversation {i} missing 'turns' field."
        if not conv["turns"]:
            return False, f"Conversation {i} has no turns."
        for j, turn in enumerate(conv["turns"]):
            if not turn.get("text"):
                return (
                    False,
                    f"Conversation {i}, turn {j} has empty text.",
                )
            if not turn.get("speaker"):
                return (
                    False,
                    f"Conversation {i}, turn {j} has no speaker.",
                )

    return True, "Valid"


async def ingest_dataset(
    db: AsyncSession,
    name: str,
    description: str | None,
    file_content: str,
    file_type: str,
) -> Dataset:
    """Parse file content, validate, and persist to database."""
    if file_type == "csv":
        conversations_data = parse_csv(file_content)
    elif file_type == "json":
        conversations_data = parse_json(file_content)
    elif file_type == "jsonl":
        conversations_data = parse_jsonl(file_content)
    else:
        raise ValueError(f"Unsupported file type: {file_type}. Use csv, json, or jsonl.")

    valid, msg = validate_schema(conversations_data)
    if not valid:
        raise ValueError(f"Schema validation failed: {msg}")

    total_turns = sum(len(c["turns"]) for c in conversations_data)

    dataset = Dataset(
        name=name,
        description=description,
        file_type=file_type,
        row_count=total_turns,
    )
    db.add(dataset)
    await db.flush()

    for conv_data in conversations_data:
        conversation = Conversation(
            dataset_id=dataset.id,
            external_id=conv_data.get("external_id"),
            turn_count=len(conv_data["turns"]),
        )
        db.add(conversation)
        await db.flush()

        for turn_data in conv_data["turns"]:
            ts = turn_data.get("timestamp")
            if isinstance(ts, str) and ts:
                try:
                    ts = datetime.datetime.fromisoformat(ts)
                except (ValueError, TypeError):
                    ts = None

            turn = Turn(
                conversation_id=conversation.id,
                turn_index=turn_data["turn_index"],
                speaker=turn_data["speaker"],
                text=turn_data["text"],
                timestamp=ts,
                thread_id=turn_data.get("thread_id"),
                ground_truth_intent=turn_data.get("ground_truth_intent"),
            )
            db.add(turn)

    await db.commit()
    await db.refresh(dataset)
    return dataset
