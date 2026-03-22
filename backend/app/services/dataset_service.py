import csv
import io
import json
import datetime
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Dataset, Conversation, Turn

logger = logging.getLogger(__name__)


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


async def create_dataset_placeholder(
    db: AsyncSession,
    name: str,
    description: str | None,
    file_type: str,
) -> Dataset:
    """Create a dataset row with status='processing'. Returns immediately."""
    dataset = Dataset(
        name=name,
        description=description,
        file_type=file_type,
        row_count=0,
        status="processing",
        status_detail="Starting ingestion...",
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)
    return dataset


async def ingest_dataset_background(
    dataset_id: int,
    file_path: Path,
    file_type: str,
    batch_size: int = 1000,
) -> None:
    """Background task: stream-parse a file and bulk-insert into the DB.

    Uses its own DB session. Updates dataset status on completion/failure.
    Uses raw SQL INSERT for performance — avoids ORM object tracking overhead.
    """
    from sqlalchemy import text
    from app.database import get_session_factory

    factory = get_session_factory()

    try:
        async with factory() as db:
            if file_type == "json":
                content = file_path.read_text(encoding="utf-8")
                conversations_data = parse_json(content)
                valid, msg = validate_schema(conversations_data)
                if not valid:
                    raise ValueError(f"Schema validation failed: {msg}")
                total = await _bulk_insert_conversations(db, dataset_id, conversations_data, batch_size)
            elif file_type == "jsonl":
                total = await _stream_jsonl_bulk(db, dataset_id, file_path, batch_size)
            elif file_type == "csv":
                total = await _stream_csv_bulk(db, dataset_id, file_path, batch_size)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")

            await db.execute(
                text("UPDATE datasets SET row_count = :cnt, status = 'ready', status_detail = NULL WHERE id = :id"),
                {"cnt": total, "id": dataset_id},
            )
            await db.commit()
            logger.info(f"Background ingest complete: dataset {dataset_id}, {total} turns")

    except Exception as e:
        logger.exception(f"Background ingest failed for dataset {dataset_id}")
        try:
            async with factory() as db:
                detail = str(e)[:500]
                await db.execute(
                    text("UPDATE datasets SET status = 'failed', status_detail = :detail WHERE id = :id"),
                    {"detail": detail, "id": dataset_id},
                )
                await db.commit()
        except Exception:
            logger.exception("Failed to update dataset status to 'failed'")


async def _bulk_insert_conversations(
    db: AsyncSession,
    dataset_id: int,
    conversations_data: List[Dict[str, Any]],
    batch_size: int,
) -> int:
    """Insert parsed conversations using raw SQL bulk inserts."""
    from sqlalchemy import text

    total_turns = 0
    turn_batch = []

    for conv_data in conversations_data:
        result = await db.execute(
            text(
                "INSERT INTO conversations (dataset_id, external_id, turn_count, created_at) "
                "VALUES (:did, :eid, :tc, :ts)"
            ),
            {
                "did": dataset_id,
                "eid": conv_data.get("external_id"),
                "tc": len(conv_data["turns"]),
                "ts": datetime.datetime.utcnow().isoformat(),
            },
        )
        conv_id = result.lastrowid

        for turn_data in conv_data["turns"]:
            ts = turn_data.get("timestamp")
            if isinstance(ts, str) and ts:
                try:
                    ts = datetime.datetime.fromisoformat(ts).isoformat()
                except (ValueError, TypeError):
                    ts = None

            turn_batch.append({
                "cid": conv_id,
                "ti": turn_data["turn_index"],
                "sp": turn_data["speaker"],
                "tx": turn_data["text"],
                "ts": ts,
                "thid": turn_data.get("thread_id"),
                "gti": turn_data.get("ground_truth_intent"),
            })
            total_turns += 1

            if len(turn_batch) >= batch_size:
                await _flush_turn_batch(db, turn_batch)
                turn_batch = []

    if turn_batch:
        await _flush_turn_batch(db, turn_batch)

    return total_turns


async def _flush_turn_batch(db: AsyncSession, batch: List[Dict]) -> None:
    """Insert a batch of turns using executemany-style raw SQL."""
    from sqlalchemy import text

    await db.execute(
        text(
            "INSERT INTO turns (conversation_id, turn_index, speaker, text, timestamp, thread_id, ground_truth_intent) "
            "VALUES (:cid, :ti, :sp, :tx, :ts, :thid, :gti)"
        ),
        batch,
    )


async def _stream_jsonl_bulk(
    db: AsyncSession, dataset_id: int, file_path: Path, batch_size: int
) -> int:
    """Stream JSONL line-by-line, bulk-insert turns in batches."""
    from sqlalchemy import text

    total_turns = 0
    turn_batch = []

    with open(file_path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, 1):
            line = line.strip()
            if not line:
                continue

            try:
                conv = json.loads(line)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON on line {line_num}: {e}")

            if not isinstance(conv, dict):
                continue

            raw_turns = conv.get("turns", [])
            if not isinstance(raw_turns, list) or not raw_turns:
                continue

            turns = [_normalize_turn(t, i) for i, t in enumerate(raw_turns)]
            valid_turns = [t for t in turns if t.get("text") and t.get("speaker")]
            if not valid_turns:
                continue

            external_id = conv.get("conversation_id") or conv.get("external_id") or str(line_num)

            result = await db.execute(
                text(
                    "INSERT INTO conversations (dataset_id, external_id, turn_count, created_at) "
                    "VALUES (:did, :eid, :tc, :ts)"
                ),
                {
                    "did": dataset_id,
                    "eid": str(external_id),
                    "tc": len(valid_turns),
                    "ts": datetime.datetime.utcnow().isoformat(),
                },
            )
            conv_id = result.lastrowid

            for turn_data in valid_turns:
                ts = turn_data.get("timestamp")
                if isinstance(ts, str) and ts:
                    try:
                        ts = datetime.datetime.fromisoformat(ts).isoformat()
                    except (ValueError, TypeError):
                        ts = None

                turn_batch.append({
                    "cid": conv_id,
                    "ti": turn_data["turn_index"],
                    "sp": turn_data["speaker"],
                    "tx": turn_data["text"],
                    "ts": ts,
                    "thid": turn_data.get("thread_id"),
                    "gti": turn_data.get("ground_truth_intent"),
                })
                total_turns += 1

            if len(turn_batch) >= batch_size:
                await _flush_turn_batch(db, turn_batch)
                turn_batch = []
                # Commit periodically to avoid huge transaction
                if total_turns % (batch_size * 10) == 0:
                    await db.commit()
                    logger.info(f"  ...ingested {total_turns} turns so far")

    if turn_batch:
        await _flush_turn_batch(db, turn_batch)

    await db.commit()
    return total_turns


async def _stream_csv_bulk(
    db: AsyncSession, dataset_id: int, file_path: Path, batch_size: int
) -> int:
    """Stream CSV row-by-row, bulk-insert turns in batches."""
    from sqlalchemy import text

    total_turns = 0
    turn_batch = []
    conv_ids: Dict[str, int] = {}
    conv_counts: Dict[str, int] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            conv_ext_id = row.get("conversation_id", row.get("external_id", "default"))
            turn_data = _normalize_turn(row, 0)

            if not turn_data.get("text") or not turn_data.get("speaker"):
                continue

            if conv_ext_id not in conv_ids:
                result = await db.execute(
                    text(
                        "INSERT INTO conversations (dataset_id, external_id, turn_count, created_at) "
                        "VALUES (:did, :eid, :tc, :ts)"
                    ),
                    {
                        "did": dataset_id,
                        "eid": conv_ext_id,
                        "tc": 0,
                        "ts": datetime.datetime.utcnow().isoformat(),
                    },
                )
                conv_ids[conv_ext_id] = result.lastrowid
                conv_counts[conv_ext_id] = 0

            ts = turn_data.get("timestamp")
            if isinstance(ts, str) and ts:
                try:
                    ts = datetime.datetime.fromisoformat(ts).isoformat()
                except (ValueError, TypeError):
                    ts = None

            turn_batch.append({
                "cid": conv_ids[conv_ext_id],
                "ti": turn_data["turn_index"],
                "sp": turn_data["speaker"],
                "tx": turn_data["text"],
                "ts": ts,
                "thid": turn_data.get("thread_id"),
                "gti": turn_data.get("ground_truth_intent"),
            })
            conv_counts[conv_ext_id] += 1
            total_turns += 1

            if len(turn_batch) >= batch_size:
                await _flush_turn_batch(db, turn_batch)
                turn_batch = []
                if total_turns % (batch_size * 10) == 0:
                    await db.commit()

    if turn_batch:
        await _flush_turn_batch(db, turn_batch)

    # Update turn counts
    for ext_id, count in conv_counts.items():
        await db.execute(
            text("UPDATE conversations SET turn_count = :tc WHERE id = :id"),
            {"tc": count, "id": conv_ids[ext_id]},
        )

    await db.commit()
    return total_turns
