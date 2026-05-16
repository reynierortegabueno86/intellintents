#!/usr/bin/env python3
"""
Export fully-classified conversations from a run into a self-contained JSON file.

The export includes all metadata needed to re-import the experiment into a fresh
or existing intellintents instance: dataset, taxonomy, experiment config,
classifications, and label mappings.

READ-ONLY: opens the database in read-only mode.

Usage:
    python export_run.py <db_path> <run_id> [--output <file.json>]
"""

import argparse
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


FORMAT_VERSION = "1.0"

SENSITIVE_KEYS = {"api_key", "apiKey", "api_secret", "token", "secret"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def connect_readonly(db_path: str) -> sqlite3.Connection:
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def row_to_dict(row: sqlite3.Row) -> dict:
    return dict(row)


def redact_sensitive(obj):
    """Recursively redact sensitive keys from dicts."""
    if isinstance(obj, dict):
        return {
            k: "<REDACTED>" if k.lower() in {s.lower() for s in SENSITIVE_KEYS} else redact_sensitive(v)
            for k, v in obj.items()
        }
    if isinstance(obj, list):
        return [redact_sensitive(item) for item in obj]
    return obj


def safe_json_parse(raw):
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Export logic
# ---------------------------------------------------------------------------

def export_run(conn: sqlite3.Connection, run_id: int) -> dict:
    # --- Load Run ---
    run = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not run:
        print(f"ERROR: Run #{run_id} not found.", file=sys.stderr)
        sys.exit(1)

    cls_count = conn.execute(
        "SELECT COUNT(*) FROM run_classifications WHERE run_id = ?", (run_id,)
    ).fetchone()[0]
    if cls_count == 0:
        print(f"ERROR: Run #{run_id} has zero classifications. Nothing to export.",
              file=sys.stderr)
        sys.exit(1)

    # --- Load Experiment ---
    exp = conn.execute(
        "SELECT * FROM experiments WHERE id = ?", (run["experiment_id"],)
    ).fetchone()
    if not exp:
        print(f"ERROR: Experiment #{run['experiment_id']} not found.", file=sys.stderr)
        sys.exit(1)

    # --- Load Dataset ---
    dataset = conn.execute(
        "SELECT * FROM datasets WHERE id = ?", (exp["dataset_id"],)
    ).fetchone()

    # --- Load Taxonomy ---
    taxonomy = conn.execute(
        "SELECT * FROM intent_taxonomies WHERE id = ?", (exp["taxonomy_id"],)
    ).fetchone()

    # --- Load Categories (flat, then build tree) ---
    categories_flat = conn.execute(
        "SELECT * FROM intent_categories WHERE taxonomy_id = ? ORDER BY parent_id, priority, name",
        (exp["taxonomy_id"],),
    ).fetchall()

    children_by_parent: dict[int | None, list] = {}
    for cat in categories_flat:
        parent = cat["parent_id"]
        children_by_parent.setdefault(parent, []).append(row_to_dict(cat))

    def build_tree(parent_id):
        nodes = children_by_parent.get(parent_id, [])
        result = []
        for node in nodes:
            examples = safe_json_parse(node.get("examples"))
            kids = build_tree(node["id"])
            result.append({
                "source_id": node["id"],
                "name": node["name"],
                "description": node.get("description"),
                "color": node.get("color"),
                "source_parent_id": node.get("parent_id"),
                "priority": node.get("priority", 0),
                "examples": examples if not kids else None,
                "children": kids if kids else [],
            })
        return result

    category_tree = build_tree(None)

    # --- Load Label Mappings ---
    label_mappings = conn.execute(
        "SELECT classifier_label, taxonomy_label FROM label_mappings WHERE experiment_id = ?",
        (exp["id"],),
    ).fetchall()

    # --- Determine fully-classified conversations ---
    # A conversation is fully classified if every turn has a classification in this run
    fully_classified_conv_ids = conn.execute(
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
    conv_ids = [r[0] for r in fully_classified_conv_ids]

    if not conv_ids:
        print(f"ERROR: No fully-classified conversations found for Run #{run_id}.",
              file=sys.stderr)
        sys.exit(1)

    # --- Load Conversations + Turns (only fully-classified ones) ---
    placeholders = ",".join("?" * len(conv_ids))

    conversations_raw = conn.execute(
        f"SELECT * FROM conversations WHERE id IN ({placeholders}) ORDER BY id",
        conv_ids,
    ).fetchall()

    turns_raw = conn.execute(
        f"""SELECT * FROM turns WHERE conversation_id IN ({placeholders})
            ORDER BY conversation_id, turn_index""",
        conv_ids,
    ).fetchall()

    # Group turns by conversation
    turns_by_conv: dict[int, list] = {}
    for t in turns_raw:
        turns_by_conv.setdefault(t["conversation_id"], []).append(t)

    conversations_out = []
    total_turns_exported = 0
    for c in conversations_raw:
        conv_turns = turns_by_conv.get(c["id"], [])
        total_turns_exported += len(conv_turns)
        conversations_out.append({
            "source_id": c["id"],
            "external_id": c["external_id"],
            "turn_count": c["turn_count"],
            "turns": [
                {
                    "source_id": t["id"],
                    "turn_index": t["turn_index"],
                    "speaker": t["speaker"],
                    "text": t["text"],
                    "timestamp": t["timestamp"],
                    "thread_id": t["thread_id"],
                    "ground_truth_intent": t["ground_truth_intent"],
                }
                for t in conv_turns
            ],
        })

    # --- Load Run Classifications (only for fully-classified conversations) ---
    classifications_raw = conn.execute(
        f"""SELECT * FROM run_classifications
            WHERE run_id = ? AND conversation_id IN ({placeholders})
            ORDER BY conversation_id, id""",
        [run_id] + conv_ids,
    ).fetchall()

    run_classifications_out = [
        {
            "source_conversation_id": rc["conversation_id"],
            "source_turn_id": rc["turn_id"],
            "speaker": rc["speaker"],
            "text": rc["text"],
            "intent_label": rc["intent_label"],
            "confidence": rc["confidence"],
        }
        for rc in classifications_raw
    ]

    # --- Build classifier_parameters (redacted) ---
    classifier_params = redact_sensitive(safe_json_parse(exp["classifier_parameters"]) or {})
    config_snapshot = redact_sensitive(safe_json_parse(run["configuration_snapshot"]) or {})
    results_summary = safe_json_parse(run["results_summary"])

    # --- Assemble export document ---
    export_doc = {
        "format_version": FORMAT_VERSION,
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "source_db": str(Path(conn.execute("PRAGMA database_list").fetchone()[2]).name),
        "source_run_id": run_id,

        "dataset": {
            "source_id": dataset["id"],
            "name": dataset["name"],
            "description": dataset["description"],
            "file_type": dataset["file_type"],
            "row_count": total_turns_exported,
            "status": "ready",
        },

        "taxonomy": {
            "source_id": taxonomy["id"],
            "name": taxonomy["name"],
            "description": taxonomy["description"],
            "tags": safe_json_parse(taxonomy["tags"]),
            "metadata_json": safe_json_parse(taxonomy["metadata_json"]),
            "priority": taxonomy["priority"] or 0,
            "version": taxonomy["version"] or 1,
            "categories": category_tree,
        },

        "experiment": {
            "source_id": exp["id"],
            "name": exp["name"],
            "description": exp["description"],
            "classification_method": exp["classification_method"],
            "classifier_parameters": classifier_params,
            "created_by": exp["created_by"],
            "is_favorite": bool(exp["is_favorite"]),
        },

        "run": {
            "source_id": run["id"],
            "original_status": run["status"],
            "execution_date": run["execution_date"],
            "runtime_duration": run["runtime_duration"],
            "configuration_snapshot": config_snapshot,
            "results_summary": results_summary,
            "progress_current": run["progress_current"],
            "progress_total": run["progress_total"],
            "is_favorite": bool(run["is_favorite"]),
        },

        "label_mappings": [
            {"classifier_label": lm["classifier_label"], "taxonomy_label": lm["taxonomy_label"]}
            for lm in label_mappings
        ],

        "conversations": conversations_out,
        "run_classifications": run_classifications_out,
    }

    return export_doc


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Export fully-classified conversations from a run to JSON"
    )
    parser.add_argument("db_path", help="Path to intellintents.db")
    parser.add_argument("run_id", type=int, help="Run ID to export")
    parser.add_argument("--output", "-o", default=None,
                        help="Output JSON path (default: export_run_<id>.json)")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    if not db_path.exists():
        print(f"ERROR: {db_path} not found", file=sys.stderr)
        sys.exit(1)

    output_path = Path(args.output) if args.output else Path(f"export_run_{args.run_id}.json")

    conn = connect_readonly(str(db_path))
    try:
        export_doc = export_run(conn, args.run_id)
    finally:
        conn.close()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(export_doc, f, indent=2, ensure_ascii=False, default=str)

    n_conv = len(export_doc["conversations"])
    n_turns = sum(len(c["turns"]) for c in export_doc["conversations"])
    n_cls = len(export_doc["run_classifications"])
    size_mb = output_path.stat().st_size / (1024 * 1024)

    print(f"Export complete: {output_path}")
    print(f"  Conversations : {n_conv}")
    print(f"  Turns         : {n_turns}")
    print(f"  Classifications: {n_cls}")
    print(f"  File size     : {size_mb:.1f} MB")


if __name__ == "__main__":
    main()
