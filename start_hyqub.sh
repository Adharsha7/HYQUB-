#!/bin/bash

echo ""
echo "=========================================="
echo "       STARTING HYQUB ENVIRONMENT"
echo "=========================================="
echo ""

HYQUB_DIR="$HOME/HYQUB"
BACKEND_DIR="$HYQUB_DIR/backend"

# ==========================================
# 1. CHECK ANVIL
# ==========================================

echo "[1/3] Checking Anvil..."

if curl -s http://127.0.0.1:8545 > /dev/null; then
    echo "✅ Anvil is already running."
else
    echo "Starting Anvil..."

    "$HYQUB_DIR/start_anvil.sh" \
        > "$HYQUB_DIR/anvil.log" 2>&1 &

    sleep 5

    if curl -s http://127.0.0.1:8545 > /dev/null; then
        echo "✅ Anvil started successfully."
    else
        echo "❌ Failed to start Anvil."
        exit 1
    fi
fi


# ==========================================
# 2. CHECK HYQUB CONTRACTS
# ==========================================

echo ""
echo "[2/3] Checking HYQUB contracts..."

if [ -f "$HYQUB_DIR/blockchain/.last_deployment.json" ]; then
    echo "✅ HYQUB deployment configuration found."
else
    echo "⚠️ Contracts not configured."
    echo "Running HYQUB setup..."

    cd "$HYQUB_DIR"

    ./setup_hyqub_env.sh
fi


# ==========================================
# 3. CHECK BACKEND
# ==========================================

echo ""
echo "[3/3] Checking HYQUB Backend..."

if curl -s http://127.0.0.1:8000/health > /dev/null; then

    echo "✅ HYQUB Backend is already running."

else

    echo "Starting HYQUB Backend..."

    cd "$BACKEND_DIR"

    source venv/bin/activate

    nohup uvicorn app.main:app \
        --host 127.0.0.1 \
        --port 8000 \
        --reload \
        > "$HYQUB_DIR/backend.log" 2>&1 &

    sleep 3

    if curl -s http://127.0.0.1:8000/health > /dev/null; then
        echo "✅ HYQUB Backend started successfully."
    else
        echo "❌ Failed to start HYQUB Backend."
        exit 1
    fi

fi


# ==========================================
# READY
# ==========================================

echo ""
echo "=========================================="
echo "       HYQUB IS READY 🚀"
echo "=========================================="

echo ""
echo "Blockchain: http://127.0.0.1:8545"
echo "Backend:    http://127.0.0.1:8000"
echo "API Docs:   http://127.0.0.1:8000/docs"
echo ""
