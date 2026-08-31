#!/bin/sh
# jobradar — scheduled-run entry point (e.g. a cron / Task Scheduler job).
# Point the job at this file: sh /path/to/jobradar/run.sh

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR" || exit 1

# Look for python3 in the usual locations.
if [ -x /usr/local/bin/python3 ]; then
    PYTHON=/usr/local/bin/python3
elif [ -x /usr/bin/python3 ]; then
    PYTHON=/usr/bin/python3
else
    PYTHON=$(command -v python3)
fi

if [ -z "$PYTHON" ]; then
    echo "jobradar: python3 not found. Install Python 3." >&2
    exit 1
fi

# Guard against parallel runs: if the previous run hung on IMAP, a second one
# must not start and spawn duplicates.
LOCK_DIR="$SCRIPT_DIR/.lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    LOCK_AGE=$(( $(date +%s) - $(date -r "$LOCK_DIR" +%s 2>/dev/null || date +%s) ))
    if [ "$LOCK_AGE" -gt 3600 ]; then
        echo "jobradar: found a stale lock (${LOCK_AGE}s), removing it." >&2
        rm -rf "$LOCK_DIR"
        mkdir "$LOCK_DIR" 2>/dev/null || exit 1
    else
        echo "jobradar: the previous run is still working, exiting." >&2
        exit 0
    fi
fi
trap 'rm -rf "$LOCK_DIR"' EXIT INT TERM

"$PYTHON" -m jobradar run
EXIT_CODE=$?

if [ "$EXIT_CODE" -ne 0 ]; then
    echo "jobradar: the run finished with code $EXIT_CODE, see jobradar.log" >&2
fi

exit "$EXIT_CODE"
