#!/usr/bin/env bash

set -euo pipefail


# --------------------------------------------------
# HYQUB Persistent Anvil
# --------------------------------------------------

HYQUB_ROOT="$HOME/HYQUB"

STATE_DIR="$HYQUB_ROOT/blockchain/anvil-state"

STATE_FILE="$STATE_DIR/anvil-state.json"


# --------------------------------------------------
# Create state directory
# --------------------------------------------------

mkdir -p "$STATE_DIR"


# --------------------------------------------------
# Check existing Anvil
# --------------------------------------------------

EXISTING_PIDS=$(pgrep -x "anvil" || true)


if [ -n "$EXISTING_PIDS" ]; then

    echo
    echo "WARNING: Anvil is already running:"
    echo

    echo "$EXISTING_PIDS" | while read -r pid; do
        ps -p "$pid" -o pid,args= 2>/dev/null || true
    done

    echo

    read -p "Kill existing Anvil and restart? [y/N] " -n 1 -r

    echo

    if [[ $REPLY =~ ^[Yy]$ ]]; then

        echo "$EXISTING_PIDS" | xargs -r kill -9

        sleep 2

        echo "Existing Anvil stopped."

    else

        echo "Keeping existing Anvil."

        exit 0

    fi

fi


# --------------------------------------------------
# Start Anvil
# --------------------------------------------------

echo
echo "=========================================="
echo "Starting HYQUB Persistent Anvil"
echo "=========================================="

echo
echo "State file:"
echo "$STATE_FILE"

echo


if [ -f "$STATE_FILE" ]; then

    echo "Previous blockchain state found."

    echo
    echo "Restoring contracts and blockchain state..."
    echo

else

    echo "No previous blockchain state found."

    echo
    echo "Starting a new HYQUB blockchain."
    echo

fi


# --------------------------------------------------
# Start Anvil with persistence
# --------------------------------------------------

exec anvil \
    --code-size-limit 40000 \
    --state "$STATE_FILE"
