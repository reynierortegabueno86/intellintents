#!/usr/bin/env python3
"""
Read-only analysis of intellintents.db and llm_cache.db.

Produces a report summarizing experiments, runs, classified conversations,
and LLM cache entries — useful for assessing what data can be recovered
from failed or interrupted runs.

Usage:
    python analyze_databases.py <input_folder> [output_file]

    input_folder  – directory containing intellintents.db and llm_cache.db
    output_file   – path for the report (default: <input_folder>/recovery_report.txt)
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def connect_readonly(db_path: str) -> sqlite3.Connection:
    """Open a SQLite database in read-only mode."""
    uri = f"file:{db_path}?mode=ro"
    conn = sqlite3.connect(uri, uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def fmt_duration(seconds: float | None) -> str:
    if seconds is None:
        return "N/A"
    h, rem = divmod(int(seconds), 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


def fmt_date(dt_str: str | None) -> str:
    if not dt_str:
        return "N/A"
    return dt_str[:19].replace("T", " ")


def pct(part: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{part / total * 100:.1f}%"


def safe_json(raw: str | None) -> dict | list | None:
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return None


SEPARATOR = "=" * 80
THIN_SEP = "-" * 80


# ---------------------------------------------------------------------------
# Main database report
# ---------------------------------------------------------------------------

def analyze_main_db(conn: sqlite3.Connection, lines: list[str]) -> None:
    lines.append(SEPARATOR)
    lines.append("  MAIN DATABASE: intellintents.db")
    lines.append(SEPARATOR)

    # --- Overview counts ---
    counts = {}
    for table in ("datasets", "conversations", "turns", "experiments", "runs",
                   "run_classifications", "classifications", "intent_taxonomies",
                   "intent_categories", "label_mappings"):
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM [{table}]").fetchone()
            counts[table] = row[0]
        except sqlite3.OperationalError:
            counts[table] = -1  # table missing

    lines.append("")
    lines.append("TABLE ROW COUNTS")
    lines.append(THIN_SEP)
    max_name = max(len(t) for t in counts)
    for table, cnt in counts.items():
        val = str(cnt) if cnt >= 0 else "(table not found)"
        lines.append(f"  {table:<{max_name + 2}} {val:>10}")

    # --- Datasets ---
    lines.append("")
    lines.append(SEPARATOR)
    lines.append("  DATASETS")
    lines.append(SEPARATOR)

    datasets = conn.execute(
        """
        SELECT d.id, d.name, d.file_type, d.row_count, d.status,
               COUNT(DISTINCT c.id) AS conv_count,
               COUNT(t.id)          AS turn_count
        FROM datasets d
        LEFT JOIN conversations c ON c.dataset_id = d.id
        LEFT JOIN turns t         ON t.conversation_id = c.id
        GROUP BY d.id
        ORDER BY d.id
        """
    ).fetchall()

    for ds in datasets:
        lines.append(f"\n  Dataset #{ds['id']}: {ds['name']}")
        lines.append(f"    File type: {ds['file_type']}  |  Status: {ds['status']}")
        lines.append(f"    Rows (reported): {ds['row_count']}  |  "
                      f"Conversations: {ds['conv_count']}  |  Turns: {ds['turn_count']}")

    # --- Experiments & Runs ---
    lines.append("")
    lines.append(SEPARATOR)
    lines.append("  EXPERIMENTS & RUNS")
    lines.append(SEPARATOR)

    experiments = conn.execute(
        """
        SELECT e.id, e.name, e.description, e.classification_method,
               e.classifier_parameters, e.created_at,
               d.name AS dataset_name, d.id AS dataset_id,
               it.name AS taxonomy_name, it.id AS taxonomy_id
        FROM experiments e
        LEFT JOIN datasets d          ON d.id = e.dataset_id
        LEFT JOIN intent_taxonomies it ON it.id = e.taxonomy_id
        ORDER BY e.id
        """
    ).fetchall()

    if not experiments:
        lines.append("\n  (no experiments found)")

    for exp in experiments:
        params = safe_json(exp["classifier_parameters"]) or {}
        model = params.get("model", "N/A")

        lines.append(f"\n{'=' * 70}")
        lines.append(f"  Experiment #{exp['id']}: {exp['name']}")
        lines.append(f"{'=' * 70}")
        if exp["description"]:
            lines.append(f"    Description : {exp['description']}")
        lines.append(f"    Created     : {fmt_date(exp['created_at'])}")
        lines.append(f"    Dataset     : #{exp['dataset_id']} {exp['dataset_name']}")
        lines.append(f"    Taxonomy    : #{exp['taxonomy_id']} {exp['taxonomy_name']}")
        lines.append(f"    Method      : {exp['classification_method']}")
        lines.append(f"    Model       : {model}")

        # Runs for this experiment
        runs = conn.execute(
            """
            SELECT r.id, r.status, r.execution_date, r.runtime_duration,
                   r.progress_current, r.progress_total,
                   r.results_summary, r.configuration_snapshot, r.created_at
            FROM runs r
            WHERE r.experiment_id = ?
            ORDER BY r.id
            """,
            (exp["id"],),
        ).fetchall()

        if not runs:
            lines.append("    Runs        : (none)")
            continue

        lines.append(f"    Runs        : {len(runs)}")

        for run in runs:
            prog_cur = run["progress_current"] or 0
            prog_tot = run["progress_total"] or 0
            progress_str = f"{prog_cur}/{prog_tot} ({pct(prog_cur, prog_tot)})"

            lines.append(f"\n    {'-' * 60}")
            lines.append(f"    Run #{run['id']}  |  Status: {run['status'].upper()}")
            lines.append(f"    {'-' * 60}")
            lines.append(f"      Execution date : {fmt_date(run['execution_date'])}")
            lines.append(f"      Duration       : {fmt_duration(run['runtime_duration'])}")
            lines.append(f"      Progress       : {progress_str}")

            # Classification counts for this run
            cls_stats = conn.execute(
                """
                SELECT COUNT(*)              AS total_classifications,
                       COUNT(DISTINCT conversation_id) AS distinct_conversations,
                       COUNT(DISTINCT turn_id)         AS distinct_turns
                FROM run_classifications
                WHERE run_id = ?
                """,
                (run["id"],),
            ).fetchone()

            # Total conversations in the dataset for this experiment
            dataset_conv_count = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM conversations
                WHERE dataset_id = ?
                """,
                (exp["dataset_id"],),
            ).fetchone()["cnt"]

            lines.append(f"      Classifications: {cls_stats['total_classifications']}")
            lines.append(f"      Turns classified: {cls_stats['distinct_turns']} (distinct)")

            # Fully vs partially classified conversations
            conv_completeness = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN classified = total THEN 1 ELSE 0 END) AS fully_classified,
                    SUM(CASE WHEN classified < total THEN 1 ELSE 0 END) AS partially_classified
                FROM (
                    SELECT rc.conversation_id,
                           COUNT(DISTINCT rc.turn_id) AS classified,
                           c.turn_count               AS total
                    FROM run_classifications rc
                    JOIN conversations c ON c.id = rc.conversation_id
                    WHERE rc.run_id = ?
                    GROUP BY rc.conversation_id
                )
                """,
                (run["id"],),
            ).fetchone()

            fully = conv_completeness["fully_classified"] or 0
            partially = conv_completeness["partially_classified"] or 0
            not_started = dataset_conv_count - fully - partially

            lines.append(f"      Conversations in dataset       : {dataset_conv_count}")
            lines.append(f"      Fully classified conversations : {fully} ({pct(fully, dataset_conv_count)})")
            if partially > 0:
                lines.append(f"      Partially classified convs     : {partially} ({pct(partially, dataset_conv_count)})")
            lines.append(f"      Not yet classified convs       : {not_started} ({pct(not_started, dataset_conv_count)})")

            # Intent distribution for this run
            intent_dist = conn.execute(
                """
                SELECT intent_label, COUNT(*) AS cnt,
                       ROUND(AVG(confidence), 4) AS avg_conf,
                       ROUND(MIN(confidence), 4) AS min_conf,
                       ROUND(MAX(confidence), 4) AS max_conf
                FROM run_classifications
                WHERE run_id = ?
                GROUP BY intent_label
                ORDER BY cnt DESC
                """,
                (run["id"],),
            ).fetchall()

            if intent_dist:
                lines.append("")
                lines.append(f"      Intent Distribution ({len(intent_dist)} labels):")
                max_label = min(max((len(r["intent_label"]) for r in intent_dist), default=0), 50)
                lines.append(f"        {'Intent':<{max_label}}  {'Count':>7}  {'Avg Conf':>9}  "
                              f"{'Min':>6}  {'Max':>6}")
                lines.append(f"        {'-' * max_label}  {'-' * 7}  {'-' * 9}  "
                              f"{'-' * 6}  {'-' * 6}")
                for row in intent_dist:
                    label = row["intent_label"][:50]
                    lines.append(
                        f"        {label:<{max_label}}  {row['cnt']:>7}  "
                        f"{row['avg_conf']:>9.4f}  {row['min_conf']:>6.4f}  "
                        f"{row['max_conf']:>6.4f}"
                    )

            # Speaker breakdown
            speaker_dist = conn.execute(
                """
                SELECT speaker, COUNT(*) AS cnt
                FROM run_classifications
                WHERE run_id = ?
                GROUP BY speaker
                ORDER BY cnt DESC
                """,
                (run["id"],),
            ).fetchall()

            if speaker_dist:
                lines.append("")
                lines.append("      By Speaker:")
                for sp in speaker_dist:
                    lines.append(f"        {sp['speaker']:<20} {sp['cnt']:>7} turns")

            # Results summary (error info for failed runs)
            summary = safe_json(run["results_summary"])
            if summary and run["status"] == "failed":
                error = summary.get("error", "")
                if error:
                    lines.append("")
                    lines.append(f"      ERROR: {error[:200]}")

    # --- Runs summary table ---
    lines.append("")
    lines.append(SEPARATOR)
    lines.append("  RUNS SUMMARY TABLE")
    lines.append(SEPARATOR)

    all_runs = conn.execute(
        """
        SELECT r.id AS run_id, r.status, r.progress_current, r.progress_total,
               r.runtime_duration, r.execution_date,
               e.id AS exp_id, e.name AS exp_name,
               COUNT(rc.id) AS cls_count,
               COUNT(DISTINCT rc.conversation_id) AS conv_count
        FROM runs r
        JOIN experiments e ON e.id = r.experiment_id
        LEFT JOIN run_classifications rc ON rc.run_id = r.id
        GROUP BY r.id
        ORDER BY r.id
        """
    ).fetchall()

    if all_runs:
        lines.append("")
        lines.append(f"  {'Run':>5}  {'Experiment':<30}  {'Status':<10}  {'Progress':>12}  "
                      f"{'Classif.':>9}  {'Convs':>7}  {'Duration':>10}")
        lines.append(f"  {'-' * 5}  {'-' * 30}  {'-' * 10}  {'-' * 12}  "
                      f"{'-' * 9}  {'-' * 7}  {'-' * 10}")
        for r in all_runs:
            prog = f"{r['progress_current'] or 0}/{r['progress_total'] or 0}"
            name = r["exp_name"][:30]
            lines.append(
                f"  {r['run_id']:>5}  {name:<30}  {r['status']:<10}  {prog:>12}  "
                f"{r['cls_count']:>9}  {r['conv_count']:>7}  "
                f"{fmt_duration(r['runtime_duration']):>10}"
            )

    # --- Failed / incomplete runs recovery summary ---
    failed_runs = [r for r in all_runs if r["status"] in ("failed", "running", "pending")]
    if failed_runs:
        lines.append("")
        lines.append(SEPARATOR)
        lines.append("  RECOVERY SUMMARY (failed / interrupted runs)")
        lines.append(SEPARATOR)

        for r in failed_runs:
            prog_cur = r["progress_current"] or 0
            prog_tot = r["progress_total"] or 0
            remaining = prog_tot - prog_cur
            lines.append(
                f"\n  Run #{r['run_id']} (Experiment: {r['exp_name'][:40]})"
            )
            lines.append(f"    Status            : {r['status'].upper()}")
            lines.append(f"    Turns processed   : {prog_cur} / {prog_tot}")
            lines.append(f"    Turns remaining   : {remaining}")
            lines.append(f"    Classifications   : {r['cls_count']} stored in DB")

            # Fully vs partially classified for this run
            rc_comp = conn.execute(
                """
                SELECT
                    SUM(CASE WHEN classified = total THEN 1 ELSE 0 END) AS fully,
                    SUM(CASE WHEN classified < total THEN 1 ELSE 0 END) AS partially
                FROM (
                    SELECT rc.conversation_id,
                           COUNT(DISTINCT rc.turn_id) AS classified,
                           c.turn_count               AS total
                    FROM run_classifications rc
                    JOIN conversations c ON c.id = rc.conversation_id
                    WHERE rc.run_id = ?
                    GROUP BY rc.conversation_id
                )
                """,
                (r["run_id"],),
            ).fetchone()
            rc_fully = rc_comp["fully"] or 0
            rc_partially = rc_comp["partially"] or 0

            # Total conversations in the dataset
            ds_total = conn.execute(
                """
                SELECT COUNT(*) AS cnt
                FROM conversations c
                JOIN datasets d ON d.id = c.dataset_id
                JOIN experiments e ON e.dataset_id = d.id
                WHERE e.id = ?
                """,
                (r["exp_id"],),
            ).fetchone()["cnt"]
            rc_not_started = ds_total - rc_fully - rc_partially

            lines.append(f"    Conversations     : {ds_total} total in dataset")
            lines.append(f"      Fully classified  : {rc_fully} ({pct(rc_fully, ds_total)})")
            if rc_partially > 0:
                lines.append(f"      Partially classif.: {rc_partially} ({pct(rc_partially, ds_total)})")
            lines.append(f"      Not yet started   : {rc_not_started} ({pct(rc_not_started, ds_total)})")

            lines.append(f"    Recoverable       : YES - all {r['cls_count']} classifications "
                          "are queryable")
            if remaining > 0:
                lines.append(f"    Resumable         : YES - can resume from offset {prog_cur}")
            else:
                lines.append(f"    Resumable         : N/A - all turns were processed")


# ---------------------------------------------------------------------------
# LLM cache report
# ---------------------------------------------------------------------------

def analyze_cache_db(conn: sqlite3.Connection, lines: list[str]) -> None:
    lines.append("")
    lines.append(SEPARATOR)
    lines.append("  LLM CACHE DATABASE: llm_cache.db")
    lines.append(SEPARATOR)

    total = conn.execute("SELECT COUNT(*) FROM llm_cache").fetchone()[0]
    lines.append(f"\n  Total cached entries: {total}")

    if total == 0:
        lines.append("  (cache is empty)")
        return

    # By provider + model
    by_model = conn.execute(
        """
        SELECT provider, model, COUNT(*) AS cnt,
               MIN(created_at) AS earliest,
               MAX(created_at) AS latest
        FROM llm_cache
        GROUP BY provider, model
        ORDER BY cnt DESC
        """
    ).fetchall()

    lines.append("")
    lines.append("  ENTRIES BY PROVIDER / MODEL")
    lines.append(THIN_SEP)
    max_prov = max((len(r["provider"]) for r in by_model), default=8)
    max_mod = max((len(r["model"]) for r in by_model), default=5)
    lines.append(f"    {'Provider':<{max_prov}}  {'Model':<{max_mod}}  {'Count':>8}  "
                  f"{'Earliest':>20}  {'Latest':>20}")
    lines.append(f"    {'-' * max_prov}  {'-' * max_mod}  {'-' * 8}  "
                  f"{'-' * 20}  {'-' * 20}")

    for r in by_model:
        earliest = datetime.fromtimestamp(r["earliest"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        ) if r["earliest"] else "N/A"
        latest = datetime.fromtimestamp(r["latest"], tz=timezone.utc).strftime(
            "%Y-%m-%d %H:%M:%S"
        ) if r["latest"] else "N/A"
        lines.append(
            f"    {r['provider']:<{max_prov}}  {r['model']:<{max_mod}}  "
            f"{r['cnt']:>8}  {earliest:>20}  {latest:>20}"
        )

    # Cache size on disk
    lines.append("")
    db_size_query = conn.execute("PRAGMA page_count").fetchone()[0]
    page_size = conn.execute("PRAGMA page_size").fetchone()[0]
    db_size_bytes = db_size_query * page_size
    if db_size_bytes > 1024 * 1024:
        size_str = f"{db_size_bytes / (1024 * 1024):.1f} MB"
    else:
        size_str = f"{db_size_bytes / 1024:.1f} KB"
    lines.append(f"  Cache database size: {size_str}")

    # Average response length per model
    avg_resp = conn.execute(
        """
        SELECT provider, model,
               CAST(AVG(LENGTH(response)) AS INTEGER) AS avg_len,
               CAST(MIN(LENGTH(response)) AS INTEGER) AS min_len,
               CAST(MAX(LENGTH(response)) AS INTEGER) AS max_len
        FROM llm_cache
        GROUP BY provider, model
        ORDER BY avg_len DESC
        """
    ).fetchall()

    if avg_resp:
        lines.append("")
        lines.append("  RESPONSE SIZE BY MODEL (characters)")
        lines.append(THIN_SEP)
        lines.append(f"    {'Provider':<{max_prov}}  {'Model':<{max_mod}}  "
                      f"{'Avg Len':>9}  {'Min Len':>9}  {'Max Len':>9}")
        lines.append(f"    {'-' * max_prov}  {'-' * max_mod}  "
                      f"{'-' * 9}  {'-' * 9}  {'-' * 9}")
        for r in avg_resp:
            lines.append(
                f"    {r['provider']:<{max_prov}}  {r['model']:<{max_mod}}  "
                f"{r['avg_len']:>9}  {r['min_len']:>9}  {r['max_len']:>9}"
            )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Read-only analysis of intellintents.db and llm_cache.db"
    )
    parser.add_argument(
        "input_folder",
        help="Directory containing intellintents.db and llm_cache.db",
    )
    parser.add_argument(
        "output_file",
        nargs="?",
        default=None,
        help="Output report path (default: <input_folder>/recovery_report.txt)",
    )
    parser.add_argument(
        "--cache-db",
        default=None,
        help="Explicit path to llm_cache.db (if not in input_folder)",
    )
    args = parser.parse_args()

    input_folder = Path(args.input_folder).resolve()
    main_db_path = input_folder / "intellintents.db"
    cache_db_path = (
        Path(args.cache_db).resolve() if args.cache_db
        else input_folder / "llm_cache.db"
    )

    if not main_db_path.exists():
        print(f"ERROR: {main_db_path} not found", file=sys.stderr)
        sys.exit(1)

    output_file = Path(args.output_file) if args.output_file else input_folder / "recovery_report.txt"

    lines: list[str] = []
    lines.append(SEPARATOR)
    lines.append(f"  INTELLINTENTS DATABASE RECOVERY REPORT")
    lines.append(f"  Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    lines.append(f"  Input    : {input_folder}")
    lines.append(SEPARATOR)

    # Main database
    conn_main = connect_readonly(str(main_db_path))
    try:
        analyze_main_db(conn_main, lines)
    finally:
        conn_main.close()

    # Cache database (optional)
    if cache_db_path.exists():
        conn_cache = connect_readonly(str(cache_db_path))
        try:
            analyze_cache_db(conn_cache, lines)
        finally:
            conn_cache.close()
    else:
        lines.append("")
        lines.append(SEPARATOR)
        lines.append("  LLM CACHE DATABASE: llm_cache.db")
        lines.append(SEPARATOR)
        lines.append(f"  (not found at {cache_db_path})")

    # Footer
    lines.append("")
    lines.append(SEPARATOR)
    lines.append("  END OF REPORT")
    lines.append(SEPARATOR)

    report = "\n".join(lines) + "\n"

    # Write report
    output_file.parent.mkdir(parents=True, exist_ok=True)
    output_file.write_text(report, encoding="utf-8")
    print(f"Report written to: {output_file}")

    # Also print to stdout
    print()
    print(report)


if __name__ == "__main__":
    main()
