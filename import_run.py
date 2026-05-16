#!/usr/bin/env python3
"""
Import experiment classifications into an intellintents database.

Designed to work AFTER the dataset has been imported through the app
(via UI upload or /datasets/load-source). This script creates only the
experiment, taxonomy (if needed), run, and classifications — linking them
to the existing dataset conversations by external_id.

Workflow:
    1. python export_dataset.py <db> <run_id> -o subset.jsonl
    2. Upload subset.jsonl through the intellintents app → dataset #N
    3. python export_run.py <db> <run_id> -o run_export.json
    4. python import_run.py <target_db> run_export.json --dataset-id N

Usage:
    python import_run.py <db_path> <export_file.json> --dataset-id <ID> [options]

Options:
    --dataset-id ID       (required) Existing dataset ID in target DB
    --taxonomy-id ID      Reuse existing taxonomy instead of creating a new one
    --experiment-name STR Override the experiment name
    --dry-run             Validate only, do not write to the database
"""

import argparse
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path


FORMAT_VERSION = "1.0"


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_export(data: dict) -> list[str]:
    """Validate the export JSON structure. Returns error messages (empty = OK)."""
    errors = []

    if data.get("format_version") != FORMAT_VERSION:
        errors.append(f"Unsupported format_version: {data.get('format_version')} "
                      f"(expected {FORMAT_VERSION})")

    required = ("dataset", "taxonomy", "experiment", "run",
                "conversations", "run_classifications")
    for key in required:
        if key not in data:
            errors.append(f"Missing required key: '{key}'")

    if errors:
        return errors

    if not data["conversations"]:
        errors.append("'conversations' array is empty")
    if not data["run_classifications"]:
        errors.append("'run_classifications' array is empty")

    if errors:
        return errors

    # Referential integrity within the JSON
    conv_source_ids = set()
    turn_source_ids = set()
    turn_to_conv: dict[int, int] = {}

    for conv in data["conversations"]:
        cid = conv.get("source_id")
        if cid is None:
            errors.append("Conversation missing 'source_id'")
            continue
        conv_source_ids.add(cid)

        for turn in conv.get("turns", []):
            tid = turn.get("source_id")
            if tid is None:
                continue
            turn_source_ids.add(tid)
            turn_to_conv[tid] = cid

    for i, rc in enumerate(data["run_classifications"]):
        sc = rc.get("source_conversation_id")
        st = rc.get("source_turn_id")
        if sc not in conv_source_ids:
            errors.append(f"Classification [{i}] references unknown conversation {sc}")
        if st not in turn_source_ids:
            errors.append(f"Classification [{i}] references unknown turn {st}")

        conf = rc.get("confidence")
        if conf is not None and not (0.0 <= conf <= 1.0):
            errors.append(f"Classification [{i}] confidence {conf} out of [0, 1]")
        if not rc.get("intent_label"):
            errors.append(f"Classification [{i}] has empty intent_label")

    # Limit error output
    if len(errors) > 30:
        errors = errors[:30] + [f"... and {len(errors) - 30} more"]

    return errors


def validate_dataset_match(conn: sqlite3.Connection, dataset_id: int,
                           data: dict) -> tuple[dict[int, int], dict[int, int], list[str]]:
    """
    Match export conversations/turns to existing dataset rows by external_id
    and (conversation_id, turn_index).

    Returns:
        conv_id_map:  source_conv_id -> DB conversation.id
        turn_id_map:  source_turn_id -> DB turn.id
        errors:       list of mismatch errors
    """
    errors = []
    conv_id_map: dict[int, int] = {}
    turn_id_map: dict[int, int] = {}

    # Check dataset exists
    ds = conn.execute("SELECT id, name FROM datasets WHERE id = ?", (dataset_id,)).fetchone()
    if not ds:
        errors.append(f"Dataset #{dataset_id} not found in target database")
        return conv_id_map, turn_id_map, errors

    # Build external_id -> DB conversation ID lookup
    db_convs = conn.execute(
        "SELECT id, external_id FROM conversations WHERE dataset_id = ?",
        (dataset_id,),
    ).fetchall()
    ext_to_db_conv: dict[str, int] = {}
    for row in db_convs:
        if row[1]:  # external_id
            ext_to_db_conv[str(row[1])] = row[0]

    # Match each export conversation
    for conv in data["conversations"]:
        ext_id = conv.get("external_id") or str(conv["source_id"])
        db_conv_id = ext_to_db_conv.get(str(ext_id))
        if db_conv_id is None:
            errors.append(f"Conversation external_id='{ext_id}' not found in dataset #{dataset_id}")
            continue
        conv_id_map[conv["source_id"]] = db_conv_id

        # Match turns by (conversation_id, turn_index)
        db_turns = conn.execute(
            "SELECT id, turn_index FROM turns WHERE conversation_id = ? ORDER BY turn_index",
            (db_conv_id,),
        ).fetchall()
        idx_to_db_turn: dict[int, int] = {row[1]: row[0] for row in db_turns}

        for turn in conv.get("turns", []):
            ti = turn["turn_index"]
            db_turn_id = idx_to_db_turn.get(ti)
            if db_turn_id is None:
                errors.append(f"Turn index {ti} in conversation '{ext_id}' "
                              f"not found in DB conversation #{db_conv_id}")
                continue
            turn_id_map[turn["source_id"]] = db_turn_id

    return conv_id_map, turn_id_map, errors


# ---------------------------------------------------------------------------
# Import logic
# ---------------------------------------------------------------------------

def import_run(conn: sqlite3.Connection, data: dict,
               dataset_id: int, taxonomy_id: int | None,
               conv_id_map: dict[int, int], turn_id_map: dict[int, int],
               experiment_name: str | None = None,
               dry_run: bool = False) -> dict:
    """Import experiment + run + classifications. Returns summary dict."""

    cur = conn.cursor()

    # -----------------------------------------------------------------------
    # Taxonomy (create new or reuse existing)
    # -----------------------------------------------------------------------

    if taxonomy_id:
        # Verify it exists
        tax_check = cur.execute(
            "SELECT id, name FROM intent_taxonomies WHERE id = ?", (taxonomy_id,)
        ).fetchone()
        if not tax_check:
            raise ValueError(f"Taxonomy #{taxonomy_id} not found in target database")
        new_taxonomy_id = taxonomy_id
        cat_count = cur.execute(
            "SELECT COUNT(*) FROM intent_categories WHERE taxonomy_id = ?",
            (taxonomy_id,),
        ).fetchone()[0]
    else:
        # Create new taxonomy from export
        tax = data["taxonomy"]
        cur.execute(
            """INSERT INTO intent_taxonomies
               (name, description, tags, metadata_json, priority, version, created_at)
               VALUES (?, ?, ?, ?, ?, ?, datetime('now'))""",
            (
                tax["name"],
                tax.get("description"),
                json.dumps(tax["tags"]) if tax.get("tags") else None,
                json.dumps(tax["metadata_json"]) if tax.get("metadata_json") else None,
                tax.get("priority", 0),
                tax.get("version", 1),
            ),
        )
        new_taxonomy_id = cur.lastrowid

        def insert_categories(categories, parent_new_id):
            count = 0
            for cat in (categories or []):
                examples_raw = cat.get("examples")
                examples_str = json.dumps(examples_raw) if examples_raw else None
                cur.execute(
                    """INSERT INTO intent_categories
                       (taxonomy_id, name, description, color, parent_id, priority, examples)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (
                        new_taxonomy_id, cat["name"], cat.get("description"),
                        cat.get("color"), parent_new_id, cat.get("priority", 0),
                        examples_str,
                    ),
                )
                count += 1
                count += insert_categories(cat.get("children", []), cur.lastrowid)
            return count

        cat_count = insert_categories(tax.get("categories", []), None)

    # -----------------------------------------------------------------------
    # Experiment
    # -----------------------------------------------------------------------

    exp = data["experiment"]
    classifier_params = exp.get("classifier_parameters")
    cur.execute(
        """INSERT INTO experiments
           (name, description, dataset_id, taxonomy_id, classification_method,
            classifier_parameters, created_by, is_favorite, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            experiment_name or exp["name"],
            exp.get("description"),
            dataset_id,
            new_taxonomy_id,
            exp["classification_method"],
            json.dumps(classifier_params) if classifier_params else None,
            exp.get("created_by"),
            int(exp.get("is_favorite", False)),
        ),
    )
    new_experiment_id = cur.lastrowid

    # Label mappings
    for lm in data.get("label_mappings", []):
        cur.execute(
            "INSERT INTO label_mappings (experiment_id, classifier_label, taxonomy_label) "
            "VALUES (?, ?, ?)",
            (new_experiment_id, lm["classifier_label"], lm["taxonomy_label"]),
        )

    # -----------------------------------------------------------------------
    # Run + Classifications
    # -----------------------------------------------------------------------

    # Build configuration_snapshot with target IDs
    config_snapshot = data["run"].get("configuration_snapshot") or {}
    config_snapshot["dataset_id"] = dataset_id
    config_snapshot["taxonomy_id"] = new_taxonomy_id

    # Compute results_summary from actual classifications
    n_cls = len(data["run_classifications"])
    intent_counter: Counter = Counter()
    total_confidence = 0.0
    conv_ids_in_cls = set()
    for rc in data["run_classifications"]:
        intent_counter[rc["intent_label"]] += 1
        total_confidence += rc["confidence"]
        conv_ids_in_cls.add(rc["source_conversation_id"])

    results_summary = {
        "total_turns": n_cls,
        "total_conversations": len(conv_ids_in_cls),
        "unique_intents": len(intent_counter),
        "avg_confidence": round(total_confidence / max(n_cls, 1), 4),
        "intent_distribution": dict(intent_counter.most_common()),
    }

    run_src = data["run"]
    cur.execute(
        """INSERT INTO runs
           (experiment_id, status, execution_date, runtime_duration,
            configuration_snapshot, results_summary,
            progress_current, progress_total, is_favorite, created_at)
           VALUES (?, 'completed', ?, ?, ?, ?, ?, ?, ?, datetime('now'))""",
        (
            new_experiment_id,
            run_src.get("execution_date"),
            run_src.get("runtime_duration"),
            json.dumps(config_snapshot),
            json.dumps(results_summary),
            n_cls,
            n_cls,
            int(run_src.get("is_favorite", False)),
        ),
    )
    new_run_id = cur.lastrowid

    # Insert classifications in batches
    batch = []
    for rc in data["run_classifications"]:
        new_conv_id = conv_id_map[rc["source_conversation_id"]]
        new_turn_id = turn_id_map[rc["source_turn_id"]]
        batch.append((
            new_run_id, new_conv_id, new_turn_id,
            rc["speaker"], rc["text"], rc["intent_label"], rc["confidence"],
        ))
        if len(batch) >= 1000:
            cur.executemany(
                """INSERT INTO run_classifications
                   (run_id, conversation_id, turn_id, speaker, text, intent_label, confidence)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                batch,
            )
            batch = []
    if batch:
        cur.executemany(
            """INSERT INTO run_classifications
               (run_id, conversation_id, turn_id, speaker, text, intent_label, confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            batch,
        )

    # -----------------------------------------------------------------------
    # Post-import verification
    # -----------------------------------------------------------------------

    verification_errors = []

    actual_cls = cur.execute(
        "SELECT COUNT(*) FROM run_classifications WHERE run_id = ?", (new_run_id,)
    ).fetchone()[0]
    if actual_cls != n_cls:
        verification_errors.append(
            f"Classification count mismatch: expected {n_cls}, got {actual_cls}")

    orphan_convs = cur.execute(
        """SELECT COUNT(*) FROM run_classifications rc
           LEFT JOIN conversations c ON c.id = rc.conversation_id
           WHERE rc.run_id = ? AND c.id IS NULL""",
        (new_run_id,),
    ).fetchone()[0]
    if orphan_convs:
        verification_errors.append(f"{orphan_convs} classifications with orphan conversation_id")

    orphan_turns = cur.execute(
        """SELECT COUNT(*) FROM run_classifications rc
           LEFT JOIN turns t ON t.id = rc.turn_id
           WHERE rc.run_id = ? AND t.id IS NULL""",
        (new_run_id,),
    ).fetchone()[0]
    if orphan_turns:
        verification_errors.append(f"{orphan_turns} classifications with orphan turn_id")

    orphan_cats = cur.execute(
        """SELECT COUNT(*) FROM intent_categories ic
           WHERE ic.taxonomy_id = ? AND ic.parent_id IS NOT NULL
             AND ic.parent_id NOT IN (SELECT id FROM intent_categories WHERE taxonomy_id = ?)""",
        (new_taxonomy_id, new_taxonomy_id),
    ).fetchone()[0]
    if orphan_cats:
        verification_errors.append(f"{orphan_cats} categories with orphan parent_id")

    if verification_errors:
        print("\nVERIFICATION FAILED — rolling back:", file=sys.stderr)
        for err in verification_errors:
            print(f"  - {err}", file=sys.stderr)
        conn.rollback()
        sys.exit(1)

    if dry_run:
        conn.rollback()
        print("Dry-run: all validations passed. No data written.")
    else:
        conn.commit()

    return {
        "dataset_id": dataset_id,
        "taxonomy_id": new_taxonomy_id,
        "taxonomy_created": taxonomy_id is None,
        "experiment_id": new_experiment_id,
        "run_id": new_run_id,
        "conversations_matched": len(conv_id_map),
        "turns_matched": len(turn_id_map),
        "categories": cat_count,
        "classifications": actual_cls,
        "label_mappings": len(data.get("label_mappings", [])),
        "dry_run": dry_run,
    }


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Import experiment run classifications into intellintents"
    )
    parser.add_argument("db_path", help="Path to target intellintents.db")
    parser.add_argument("export_file", help="Path to the export JSON (from export_run.py)")
    parser.add_argument("--dataset-id", type=int, required=True,
                        help="Existing dataset ID in the target DB (from app upload)")
    parser.add_argument("--taxonomy-id", type=int, default=None,
                        help="Reuse existing taxonomy ID (otherwise creates new)")
    parser.add_argument("--experiment-name", default=None, help="Override experiment name")
    parser.add_argument("--dry-run", action="store_true",
                        help="Validate and simulate without writing")
    args = parser.parse_args()

    db_path = Path(args.db_path).resolve()
    export_path = Path(args.export_file).resolve()

    if not db_path.exists():
        print(f"ERROR: {db_path} not found", file=sys.stderr)
        sys.exit(1)
    if not export_path.exists():
        print(f"ERROR: {export_path} not found", file=sys.stderr)
        sys.exit(1)

    # Load and validate JSON
    print(f"Loading {export_path.name} ...")
    with open(export_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    print("Validating export structure ...")
    errors = validate_export(data)
    if errors:
        print(f"\nVALIDATION FAILED ({len(errors)} errors):", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        sys.exit(1)
    print("  Structure OK.")

    # Open DB and match conversations
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")

    try:
        print(f"Matching conversations against dataset #{args.dataset_id} ...")
        conv_id_map, turn_id_map, match_errors = validate_dataset_match(
            conn, args.dataset_id, data
        )
        if match_errors:
            print(f"\nDATASET MATCHING FAILED ({len(match_errors)} errors):", file=sys.stderr)
            for err in match_errors[:20]:
                print(f"  - {err}", file=sys.stderr)
            if len(match_errors) > 20:
                print(f"  ... and {len(match_errors) - 20} more", file=sys.stderr)
            sys.exit(1)
        print(f"  Matched {len(conv_id_map)} conversations, {len(turn_id_map)} turns.")

        conn.execute("BEGIN")
        summary = import_run(
            conn, data,
            dataset_id=args.dataset_id,
            taxonomy_id=args.taxonomy_id,
            conv_id_map=conv_id_map,
            turn_id_map=turn_id_map,
            experiment_name=args.experiment_name,
            dry_run=args.dry_run,
        )
    except Exception as e:
        conn.rollback()
        print(f"\nIMPORT FAILED: {e}", file=sys.stderr)
        raise
    finally:
        conn.close()

    # Print summary
    prefix = "[DRY-RUN] " if summary["dry_run"] else ""
    print(f"\n{prefix}Import complete!")
    print(f"  Dataset        : #{summary['dataset_id']} (existing)")
    tax_label = "new" if summary["taxonomy_created"] else "existing"
    print(f"  Taxonomy       : #{summary['taxonomy_id']} ({tax_label}, {summary['categories']} categories)")
    print(f"  Experiment     : #{summary['experiment_id']}")
    print(f"  Run            : #{summary['run_id']} (status: completed)")
    print(f"  Conversations  : {summary['conversations_matched']} matched")
    print(f"  Turns          : {summary['turns_matched']} matched")
    print(f"  Classifications: {summary['classifications']}")
    if summary["label_mappings"]:
        print(f"  Label Mappings : {summary['label_mappings']}")


if __name__ == "__main__":
    main()
