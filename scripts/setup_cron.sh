#!/bin/bash
#
# Setup cron jobs for sermon ingestion pipeline.
#
# This script adds cron entries for:
# - Daily sync at 2:00 AM
# - Daily embed at 3:00 AM
# - Weekly retry on Sundays at 4:00 AM
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
WRAPPER="$SCRIPT_DIR/cron_wrapper.sh"

# Make wrapper executable
chmod +x "$WRAPPER"

echo "Setting up cron jobs for: $PROJECT_DIR"
echo ""

# Generate cron entries
CRON_ENTRIES="
# Sermon Ingestion Pipeline
# Sync new videos daily at 2:00 AM
0 2 * * * $WRAPPER sync >> /dev/null 2>&1

# Embed new transcripts daily at 3:00 AM
0 3 * * * $WRAPPER embed >> /dev/null 2>&1

# Retry failed ingestions weekly on Sunday at 4:00 AM
0 4 * * 0 $WRAPPER full >> /dev/null 2>&1
"

echo "The following cron entries will be added:"
echo "$CRON_ENTRIES"
echo ""

read -p "Add these cron entries? (y/n) " -n 1 -r
echo ""

if [[ $REPLY =~ ^[Yy]$ ]]; then
    # Backup existing crontab
    crontab -l > /tmp/crontab_backup_$(date +%Y%m%d_%H%M%S) 2>/dev/null || true

    # Add new entries
    (crontab -l 2>/dev/null | grep -v "$WRAPPER"; echo "$CRON_ENTRIES") | crontab -

    echo ""
    echo "Cron jobs added successfully!"
    echo ""
    echo "Current crontab:"
    crontab -l
else
    echo ""
    echo "Cron setup cancelled."
    echo ""
    echo "To manually add, run: crontab -e"
    echo "And add these lines:"
    echo "$CRON_ENTRIES"
fi

echo ""
echo "Logs will be written to: $PROJECT_DIR/logs/"
echo ""
echo "To run manually:"
echo "  $WRAPPER sync   # Sync new videos"
echo "  $WRAPPER embed  # Embed new transcripts"
echo "  $WRAPPER full   # Full pipeline"
echo "  $WRAPPER bulk   # Initial bulk load"
