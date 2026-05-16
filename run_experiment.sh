#!/usr/bin/env bash
# ============================================================================
# run_experiment.sh — Run an IntellIntents experiment from the command line
#
# Usage:
#   ./run_experiment.sh <experiment_id>              # run existing experiment
#   ./run_experiment.sh --create \
#       --name "My Exp" \
#       --dataset-id 1 \
#       --taxonomy-id 1 \
#       --method rule_based                          # create + run
#
# Options:
#   --base-url URL    Base API URL (default: http://localhost:8001/intellintents/api)
#   --poll-interval N Seconds between status checks (default: 5)
#
# Examples:
#   # Run experiment #3 on the VM
#   ./run_experiment.sh 3 --base-url http://52.157.244.76/intellintents/api
#
#   # Create and run a new experiment locally
#   ./run_experiment.sh --create --name "Rule test" --dataset-id 1 \
#       --taxonomy-id 1 --method rule_based
# ============================================================================
set -euo pipefail

# Defaults
BASE_URL="${INTELLINTENTS_API_URL:-http://localhost:8001/intellintents/api}"
POLL_INTERVAL=5
MODE="run"  # "run" or "create"
EXP_ID=""
EXP_NAME=""
DATASET_ID=""
TAXONOMY_ID=""
METHOD=""

# Parse arguments
while [[ $# -gt 0 ]]; do
    case "$1" in
        --create)       MODE="create"; shift ;;
        --name)         EXP_NAME="$2"; shift 2 ;;
        --dataset-id)   DATASET_ID="$2"; shift 2 ;;
        --taxonomy-id)  TAXONOMY_ID="$2"; shift 2 ;;
        --method)       METHOD="$2"; shift 2 ;;
        --base-url)     BASE_URL="$2"; shift 2 ;;
        --poll-interval) POLL_INTERVAL="$2"; shift 2 ;;
        --help|-h)
            head -25 "$0" | tail -22
            exit 0
            ;;
        *)
            if [[ -z "$EXP_ID" && "$1" =~ ^[0-9]+$ ]]; then
                EXP_ID="$1"; shift
            else
                echo "Unknown argument: $1" >&2; exit 1
            fi
            ;;
    esac
done

# Remove trailing slash from base URL
BASE_URL="${BASE_URL%/}"

echo "=== IntellIntents Experiment Runner ==="
echo "API: $BASE_URL"
echo ""

# --- Create experiment if requested ---
if [[ "$MODE" == "create" ]]; then
    if [[ -z "$EXP_NAME" || -z "$DATASET_ID" || -z "$TAXONOMY_ID" || -z "$METHOD" ]]; then
        echo "Error: --create requires --name, --dataset-id, --taxonomy-id, and --method" >&2
        exit 1
    fi

    echo "Creating experiment: $EXP_NAME"
    echo "  Dataset: $DATASET_ID | Taxonomy: $TAXONOMY_ID | Method: $METHOD"

    RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/experiments" \
        -H "Content-Type: application/json" \
        -d "{\"name\": \"$EXP_NAME\", \"dataset_id\": $DATASET_ID, \"taxonomy_id\": $TAXONOMY_ID, \"classification_method\": \"$METHOD\"}")

    HTTP_CODE=$(echo "$RESPONSE" | tail -1)
    BODY=$(echo "$RESPONSE" | sed '$d')

    if [[ "$HTTP_CODE" != "200" ]]; then
        echo "Error creating experiment (HTTP $HTTP_CODE): $BODY" >&2
        exit 1
    fi

    EXP_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
    echo "Created experiment #$EXP_ID"
    echo ""
fi

# --- Validate experiment ID ---
if [[ -z "$EXP_ID" ]]; then
    echo "Error: provide an experiment ID or use --create" >&2
    echo "Usage: $0 <experiment_id> or $0 --create ..." >&2
    exit 1
fi

# --- Trigger the run ---
echo "Starting run for experiment #$EXP_ID ..."

RESPONSE=$(curl -s -w "\n%{http_code}" -X POST "$BASE_URL/experiments/$EXP_ID/run")
HTTP_CODE=$(echo "$RESPONSE" | tail -1)
BODY=$(echo "$RESPONSE" | sed '$d')

if [[ "$HTTP_CODE" != "200" ]]; then
    echo "Error starting run (HTTP $HTTP_CODE): $BODY" >&2
    exit 1
fi

RUN_ID=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['id'])")
STATUS=$(echo "$BODY" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

echo "Run #$RUN_ID started (status: $STATUS)"
echo ""

# --- Poll until complete ---
echo "Polling every ${POLL_INTERVAL}s ..."
while true; do
    sleep "$POLL_INTERVAL"

    RESPONSE=$(curl -s "$BASE_URL/experiments/runs/$RUN_ID")
    STATUS=$(echo "$RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin)['status'])")

    TIMESTAMP=$(date '+%H:%M:%S')
    echo "  [$TIMESTAMP] Status: $STATUS"

    if [[ "$STATUS" == "completed" ]]; then
        echo ""
        echo "=== Run #$RUN_ID completed ==="

        # Print summary
        SUMMARY=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
s = data.get('results_summary')
if s:
    if isinstance(s, str):
        s = json.loads(s)
    for k, v in s.items():
        print(f'  {k}: {v}')
else:
    print('  No summary available')
")
        echo "$SUMMARY"
        echo ""
        echo "Refresh the browser to see results in the UI."
        exit 0
    fi

    if [[ "$STATUS" == "failed" ]]; then
        echo ""
        echo "=== Run #$RUN_ID FAILED ==="
        SUMMARY=$(echo "$RESPONSE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
s = data.get('results_summary')
if s:
    if isinstance(s, str):
        s = json.loads(s)
    print(json.dumps(s, indent=2))
")
        echo "$SUMMARY"
        exit 1
    fi
done
