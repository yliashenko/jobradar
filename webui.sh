#!/bin/sh
# jobradar webui — entry point for a boot-up / startup job.
# Point the job at: sh /path/to/jobradar/webui.sh

SCRIPT_DIR=$(cd "$(dirname "$0")" && pwd)
cd "$SCRIPT_DIR" || exit 1

if [ -x /usr/local/bin/python3 ]; then
    PYTHON=/usr/local/bin/python3
elif [ -x /usr/bin/python3 ]; then
    PYTHON=/usr/bin/python3
else
    PYTHON=$(command -v python3)
fi

if [ -z "$PYTHON" ]; then
    echo "jobradar webui: python3 not found. Install Python 3." >&2
    exit 1
fi

# If the server is already up — a second one isn't needed.
if pgrep -f "jobradar serve" > /dev/null 2>&1; then
    echo "jobradar webui: already running." >&2
    exit 0
fi

exec "$PYTHON" -m jobradar serve >> "$SCRIPT_DIR/webui.log" 2>&1
