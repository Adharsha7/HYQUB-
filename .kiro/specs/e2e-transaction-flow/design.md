# Design — HYQUB End-to-End Transaction Flow

## Verification Strategy

We verify each layer independently before moving to the next. This lets us
locate failures precisely: backend bug vs. CORS vs. on-chain revert.

```
Layer 0: Infrastructure (ports, processes)
    ↓
Layer 1: Backend API  (curl / PowerShell Invoke-RestMethod, no browser)
    ↓
Layer 2: On-chain confirmation (Anvil JSON-RPC calls)
    ↓
Layer 3: Browser console (hyqub-console.html, confirms CORS is resolved)
```

---

## Layer 0 — Infrastructure Check

**How:** PowerShell process inspection + direct JSON-RPC probe.

```powershell
# Check listening processes
Get-Process | Where-Object { $_.ProcessName -match 'python|uvicorn' }

# Probe Anvil (JSON-RPC eth_blockNumber)
Invoke-RestMethod -Uri http://127.0.0.1:8545 `
  -Method POST -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","method":"eth_blockNumber","params":[],"id":1}'

# Probe backend health
Invoke-RestMethod -Uri http://127.0.0.1:8000/health
```

**Distinguishing failures:**
- No process + connection refused on 8545 → Anvil not running; must be
  started from WSL with `./start_anvil.sh`.
- No process + connection refused on 8000 → backend not running; start with
  `uvicorn app.main:app --reload` in WSL from `backend/` with venv active.
- Process exists but 8000 returns 500 → app started but crashed during
  import (likely missing `.env` var or missing package); read the stack
  trace in `backend.log`.

---

## Layer 1 — Backend API Smoke Test (curl/PowerShell)

We drive the full client flow against the raw API. No browser, no CORS.
Variables are captured from each response and fed into the next call.

### Step 1.1 — Confirm dev endpoints exist
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/dev/generate-keypair
```
Expected: HTTP 200, `{ public_key, secret_key }`.
If 404: `HYQUB_ENVIRONMENT` is not `development`.

### Step 1.2 — Generate keypair
Capture `public_key` and `secret_key` from the response.

### Step 1.3 — Register wallet
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/register -Method POST `
  -ContentType application/json `
  -Body '{"wallet_address":"0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0","ml_dsa_public_key":"<public_key>"}'
```
Expected: HTTP 201, `key_version >= 1`.
- HTTP 409: already registered in memory (only possible if backend wasn't restarted). Fine to proceed — key_version is already set.
- HTTP 500: read `backend.log` — likely a blockchain RPC call failed.

### Step 1.4 — Read wallet state
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/wallet/0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0/state
```
Expected: `registered: true`, matching `key_version`.
- HTTP 502: known bug — `get_registry_contract()` called without `web3` arg. Fix: pass `web3` arg in `api/wallet.py`. This step is diagnostic only; failure here does not block the transaction flow.

### Step 1.5 — Get transaction intent
```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/transaction-intent?wallet_address=0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0&target=0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9&value_wei=0&data=0x"
```
Expected: HTTP 200, `message_hash` = 64 lowercase hex chars, `chain_id`, `key_version`.

### Step 1.6 — Sign the hash
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/dev/sign -Method POST `
  -ContentType application/json `
  -Body '{"secret_key":"<secret_key>","message":"<message_hash>"}'
```
Expected: HTTP 200, `{ signature }` (base64).
- HTTP 400: secret key is malformed or wrong length.

### Step 1.7 — Verify signature (optional sanity check)
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/verify -Method POST `
  -ContentType application/json `
  -Body '{"wallet_address":"0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0","message":"<message_hash>","signature":"<signature>"}'
```
Expected: `verified: true`.

### Step 1.8 — Submit transaction
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8000/submit-transaction -Method POST `
  -ContentType application/json `
  -Body '{
    "wallet_address": "0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0",
    "target": "0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9",
    "value_wei": 0,
    "data": "0x",
    "ml_dsa_signature": "<signature>"
  }'
```
Expected: HTTP 200, `success: true`, `transaction_hash` = non-null 0x-prefixed hex.

**Distinguishing failures on this call:**
- HTTP 404: wallet not in memory — backend was restarted; re-register first.
- HTTP 400 "Quorum not reached": signature doesn't verify — `message_hash`
  drifted (target/value/data mismatch between steps 1.5 and 1.8), or key
  mismatch (signed with a different secret key than what was registered).
- HTTP 502: approval token or on-chain submission failed — read the `detail`
  field; if it's an on-chain revert the revert reason will be in the message.
- HTTP 500: unexpected Python exception — read `backend.log` for full
  traceback.

---

## Layer 2 — On-chain Confirmation

After a successful submit, confirm the tx landed on Anvil:
```powershell
Invoke-RestMethod -Uri http://127.0.0.1:8545 `
  -Method POST -ContentType "application/json" `
  -Body '{"jsonrpc":"2.0","method":"eth_getTransactionReceipt","params":["<transaction_hash>"],"id":1}'
```
Expected: `result.status = "0x1"` (success). `null` result means the tx
isn't mined yet (Anvil auto-mines, so this means the hash was wrong).

---

## Layer 3 — Browser CORS Verification

1. Confirm `HYQUB_CORS_ORIGINS` in `backend/.env` includes
   `http://127.0.0.1:5500`.
2. Restart backend (so the updated config is loaded — `get_settings()` is
   cached via `@lru_cache`).
3. Open `http://127.0.0.1:5500/hyqub-console.html`.
4. Click "Check Health" — the health-dot must turn green.
5. Run the full 6-step flow in the console and confirm a `transaction_hash`
   appears in Step 6's result box.

---

## Known Issues to Fix During Execution

### Fix A — CORS origins
`HYQUB_CORS_ORIGINS` currently only includes `http://localhost:3000`.
Add `http://127.0.0.1:5500` and `http://localhost:5500`.
**File:** `backend/.env`, line `HYQUB_CORS_ORIGINS`.

### Fix B — `GET /wallet/{address}/state` TypeError
`api/wallet.py` calls `get_registry_contract()` with no arguments, but
`blockchain.py`'s `get_registry_contract` requires a `web3: Web3` argument.
**Fix:** pass the already-obtained `web3` object: `get_registry_contract(web3)`.

### Fix C — Missing packages in venv
`requirements.txt` is missing `web3`, `eth_abi`, `eth_account`, `oqs`,
`pydantic_settings`. Verify what's actually installed with `pip list` and
install any that are absent before starting the backend.
