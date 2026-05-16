#!/usr/bin/env python3
"""
Export fully-classified conversations from a run as a dataset file
compatible with the intellintents app upload/load-source flow.

Supports two output formats:
    --format jsonl  (default) One JSON object per line. Use .jsonl extension.
    --format json   Single JSON array. Use .json extension.

IMPORTANT: the file extension must match the format so the app picks the
correct parser on upload.

READ-ONLY: opens the database in read-only mode.

Usage:
    python export_dataset.py <db_path> <run_id> [-o file.jsonl]
    python export_dataset.py <db_path> <run_id> [-o file.json] --format json
"""

import argparse
import json
import sqlite3
import sys
from pathlib import Path


def connect_readonly(db_path: str) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _build_conversation_obj(conn, conv_id):
    """Build a single conversation dict from DB rows."""
    conv = conn.execute(
        "SELECT id, external_id FROM conversations WHERE id = ?",
        (conv_id,),
    ).fetchone()

    turns = conn.execute(
        """SELECT turn_index, speaker, text, timestamp, thread_id, ground_truth_intent
           FROM turns
           WHERE conversation_id = ?
           ORDER BY turn_index""",
        (conv_id,),
    ).fetchall()

    return {
        "conversation_id": conv["external_id"] or str(conv["id"]),
        "turns": [
            {
                k: t[k]
                for k in ("turn_index", "speaker", "text", "timestamp",
                          "thread_id", "ground_truth_intent")
                if t[k] is not None
            }
            for t in turns
        ],
    }, len(turns)


def export_dataset(conn: sqlite3.Connection, run_id: int, output: Path,
                   fmt: str = "jsonl") -> dict:
    # --- Validate run exists and has classifications ---
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        print(f"ERROR: Run #{run_id} not found.", file=sys.stderr)
        sys.exit(1)

    cls_count = conn.execute(
        "SELECT COUNT(*) FROM run_classifications WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    if cls_count == 0:
        print(f"ERROR: Run #{run_id} has zero classifications.", file=sys.stderr)
        sys.exit(1)

    # --- Get fully-classified conversation IDs ---
    fully_classified = conn.execute(
        """
        SELECT rc.conversation_id
        FROM (
            SELECT conversation_id, COUNT(DISTINCT turn_id) AS classified
            FROM run_classifications
            WHERE run_id = ?
            GROUP BY conversation_id
        ) rc
        JOIN conversations c ON c.id = rc.conversation_id
        WHERE rc.classified = c.turn_count
        """,
        (run_id,),
    ).fetchall()

    conv_ids = [r[0] for r in fully_classified]
    if not conv_ids:
        print(f"ERROR: No fully-classified conversations in Run #{run_id}.", file=sys.stderr)
        sys.exit(1)

    # --- Write output ---
    total_convs = 0
    total_turns = 0
    output.parent.mkdir(parents=True, exist_ok=True)

    if fmt == "jsonl":
        with open(output, "w", encoding="utf-8") as f:
            for conv_id in conv_ids:
                conv_obj, n_turns = _build_conversation_obj(conn, conv_id)
                f.write(json.dumps(conv_obj, ensure_ascii=False) + "\n")
                total_convs += 1
                total_turns += n_turns
    else:
        # JSON: single array of conversation objects
        all_convs = []
        for conv_id in conv_ids:
            conv_obj, n_turns = _build_conversation_obj(conn, conv_id)
            all_convs.append(conv_obj)
            total_convs += 1
            total_turns += n_turns
        with open(output, "w", encoding="utf-8") as f:
            json.dump(all_convs, f, ensure_ascii=False, indent=2)

    return {
        "conversations": total_convs,
        "turns": total_turns,
        "classifications": cls_count,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export fully-classified conversations as a JSONL dataset file"
    )
    parser.add_argument("db_path", help="Path to intellintents.db")
    parser.add_argument("run_id", type=int, help="Run ID to extract conversations from")
    parser.add_argument("--output", "-o", default=None,
                        help="Output path (default: dataset_run_<id>.<format>)")
    parser.add_argument("--format", "-f", choices=("jsonl", "json"), default="jsonl",
                        help="Output format: jsonl (one obj/line) or json (single array)")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"ERROR: {db_path} not found", file=sys.stderr)
        sys.exit(1)

    ext = args.format
    output = Path(args.output) if args.output else Path(f"dataset_run_{args.run_id}.{ext}")

    # Warn if extension doesn't match format (the app uses extension to pick parser)
    actual_ext = output.suffix.lstrip(".").lower()
    if actual_ext != ext:
        print(f"WARNING: File extension '.{actual_ext}' does not match format '{ext}'.",
              file=sys.stderr)
        print(f"  The intellintents app uses the extension to pick the parser.",
              file=sys.stderr)
        print(f"  Rename to '.{ext}' before uploading, or use --output with .{ext} extension.",
              file=sys.stderr)

    conn = connect_readonly(str(db_path))
    try:
        summary = export_dataset(conn, args.run_id, output, fmt=ext)
    finally:
        conn.close()

    size_mb = output.stat().st_size / (1024 * 1024)
    print(f"Dataset exported: {output}")
    print(f"  Conversations : {summary['conversations']}")
    print(f"  Turns         : {summary['turns']}")
    print(f"  File size     : {size_mb:.1f} MB")
    print()
    print("To import into intellintents:")
    print(f"  1. App UI  : Upload Dataset -> select {output.name}")
    print(f"  2. API     : POST /api/datasets/load-source with path={output}")


if __name__ == "__main__":
    main()
