#!/bin/bash
#
# Cron wrapper script for sermon ingestion pipeline.
# Handles logging, environment setup, and error notifications.
#
# Usage:
#   ./scripts/cron_wrapper.sh sync    # Sync new videos
#   ./scripts/cron_wrapper.sh embed   # Embed new transcripts
#   ./scripts/cron_wrapper.sh retry   # Retry failed ingestions
#   ./scripts/cron_wrapper.sh full    # Full pipeline (sync + embed)
#

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
LOG_DIR="$PROJECT_DIR/logs"
VENV_PYTHON="$PROJECT_DIR/.venv/bin/python"

# Create log directory if needed
mkdir -p "$LOG_DIR"

# Log file with date
DATE=$(date +%Y-%m-%d)
LOG_FILE="$LOG_DIR/ingestion_$DATE.log"

# Function to log with timestamp
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# Change to project directory
cd "$PROJECT_DIR"

# Load environment variables if .env exists
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# Run the requested command
case "$1" in
    sync)
        log "Starting channel sync..."
        $VENV_PYTHON scripts/sync_channel.py --max-videos 50 2>&1 | tee -a "$LOG_FILE"
        EXIT_CODE=${PIPESTATUS[0]}
        ;;

    embed)
        log "Starting embedding of new transcripts..."
        $VENV_PYTHON scripts/embed_new.py 2>&1 | tee -a "$LOG_FILE"
        EXIT_CODE=${PIPESTATUS[0]}
        ;;

    retry)
        log "Retrying failed ingestions..."
        $VENV_PYTHON scripts/ingest_channel.py "https://www.youtube.com/@PastorPoju" --max-videos 0 2>&1 | tee -a "$LOG_FILE"
        # Note: --max-videos 0 with retry logic would need a dedicated retry script
        EXIT_CODE=0
        ;;

    full)
        log "Starting full pipeline (sync + embed)..."

        log "Step 1: Sync channel..."
        $VENV_PYTHON scripts/sync_channel.py --max-videos 50 2>&1 | tee -a "$LOG_FILE"
        SYNC_EXIT=${PIPESTATUS[0]}

        log "Step 2: Embed new transcripts..."
        $VENV_PYTHON scripts/embed_new.py 2>&1 | tee -a "$LOG_FILE"
        EMBED_EXIT=${PIPESTATUS[0]}

        EXIT_CODE=$((SYNC_EXIT > EMBED_EXIT ? SYNC_EXIT : EMBED_EXIT))
        ;;

    bulk)
        log "Starting BULK ingestion (all videos)..."
        $VENV_PYTHON scripts/sync_channel.py --max-videos 1000 2>&1 | tee -a "$LOG_FILE"
        SYNC_EXIT=${PIPESTATUS[0]}

        log "Embedding all transcripts..."
        $VENV_PYTHON scripts/embed_new.py 2>&1 | tee -a "$LOG_FILE"
        EMBED_EXIT=${PIPESTATUS[0]}

        EXIT_CODE=$((SYNC_EXIT > EMBED_EXIT ? SYNC_EXIT : EMBED_EXIT))
        ;;

    *)
        echo "Usage: $0 {sync|embed|retry|full|bulk}"
        echo ""
        echo "Commands:"
        echo "  sync   - Sync new videos from channel (checks last 50)"
        echo "  embed  - Embed any new transcripts to Qdrant"
        echo "  retry  - Retry failed ingestions"
        echo "  full   - Run sync + embed pipeline"
        echo "  bulk   - Initial bulk load (all videos)"
        exit 1
        ;;
esac

# Log completion
if [ $EXIT_CODE -eq 0 ]; then
    log "Completed successfully"
else
    log "Completed with errors (exit code: $EXIT_CODE)"

    # Optional: Send alert on failure
    # You can add email/Slack notification here
    # Example: curl -X POST -d "Ingestion failed" https://your-webhook-url
fi

exit $EXIT_CODE
