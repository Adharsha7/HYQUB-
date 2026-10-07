# Tasks — HYQUB End-to-End Transaction Flow

Ordered checklist. Execute sequentially. Show real command output at each step.
Do not mark a task complete until its expected output is confirmed.

---

## PHASE 0 — Infrastructure

### Task 0.1 — Check what is actually running right now
- Check listening processes (Python/uvicorn, Anvil).
- Probe port 8545 (Anvil) via JSON-RPC `eth_blockNumber`.
- Probe port 8000 (backend) via `GET /health`.
- **Pass:** Both respond without connection errors.
- **Fail/action:** If either is down, note it — do not assume; check logs.

### Task 0.2 — Start missing services (if needed)
- If Anvil is down: note that it must be started from WSL using `./start_anvil.sh`.
- If backend is down: note the WSL command to start it.
- Re-probe both ports after any start attempt to confirm they're up.

---

## PHASE 1 — Backend Health & Dev Tools

### Task 1.1 — GET /health
- Run: `Invoke-RestMethod http://127.0.0.1:8000/health`
- **Pass:** HTTP 200, `status: "healthy"`, `environment: "development"`.

### Task 1.2 — Confirm dev endpoints are live
- Run: `Invoke-RestMethod http://127.0.0.1:8000/dev/generate-keypair`
- **Pass:** HTTP 200, `{ public_key, secret_key }`.
- **Fail:** HTTP 404 → `HYQUB_ENVIRONMENT` is not `development`.

---

## PHASE 2 — Fix Known Issues

### Task 2.1 — Fix CORS origins in backend/.env
- Current value: `HYQUB_CORS_ORIGINS=["http://localhost:3000"]`
- Change to: `HYQUB_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:5500","http://localhost:5500"]`
- Note: backend must be restarted for this to take effect (`lru_cache`).

### Task 2.2 — Fix GET /wallet/{address}/state (TypeError in api/wallet.py)
- Problem: `get_registry_contract()` called without required `web3` arg.
- Fix: change `registry = get_registry_contract()` to `registry = get_registry_contract(web3)`.
- File: `backend/app/api/wallet.py`.

### Task 2.3 — Verify required packages are installed in the venv
- Run `pip list` inside the WSL venv.
- Confirm these are present: `web3`, `eth-abi`, `eth-account`, `oqs` (liboqs Python), `pydantic-settings`.
- Install any that are absent.

---

## PHASE 3 — Full API Flow (raw, no browser)

### Task 3.1 — Generate ML-DSA-65 keypair
- Run: `GET /dev/generate-keypair`
- Capture: `public_key`, `secret_key` (base64 strings).
- **Pass:** Both fields present and non-empty.

### Task 3.2 — Register wallet
- Run: `POST /register` with wallet `0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0` and `public_key` from Task 3.1.
- **Pass:** HTTP 201, `key_version >= 1`.
- If HTTP 409 (already registered in memory): note the existing `key_version` and continue.

### Task 3.3 — Read wallet state
- Run: `GET /wallet/0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0/state`
- **Pass:** HTTP 200, `registered: true`, `key_version` matches Task 3.2.
- If HTTP 502: apply Task 2.2 fix first, restart backend, retry.

### Task 3.4 — Get transaction intent hash
- Run: `GET /transaction-intent?wallet_address=0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0&target=0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9&value_wei=0&data=0x`
- Capture: `message_hash` (64 lowercase hex chars), `chain_id`, `key_version`.
- **Pass:** `message_hash` is exactly 64 hex chars.

### Task 3.5 — Sign the hash
- Run: `POST /dev/sign` with `secret_key` from Task 3.1 and `message` = `message_hash` from Task 3.4.
- Capture: `signature` (base64).
- **Pass:** HTTP 200, `signature` present and non-empty.

### Task 3.6 — Verify signature (sanity check)
- Run: `POST /verify` with wallet, `message` = `message_hash`, `signature` from Task 3.5.
- **Pass:** HTTP 200, `verified: true`.
- **Fail:** `verified: false` → key mismatch (signed with wrong key, or public key registered in Task 3.2 doesn't match secret key from Task 3.1). Re-run from Task 3.1 with a consistent keypair.

### Task 3.7 — Submit transaction
- Run: `POST /submit-transaction` with:
  - `wallet_address`: `0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0`
  - `target`: `0xcf7ed3acca5a467e9e704c703e8d87f634fb0fc9`
  - `value_wei`: `0`
  - `data`: `0x`
  - `ml_dsa_signature`: from Task 3.5
- **Pass:** HTTP 200, `success: true`, `transaction_hash` is a non-null 0x-prefixed hex string.
- Print the full response. The `transaction_hash` is the primary proof of success.

---

## PHASE 4 — On-chain Confirmation

### Task 4.1 — Verify tx receipt on Anvil
- Run: `eth_getTransactionReceipt` with the `transaction_hash` from Task 3.7.
- **Pass:** `result.status = "0x1"`.
- **Fail:** `result = null` → tx not found (wrong hash or Anvil not mining). Check Anvil logs.

---

## PHASE 5 — Browser Console

### Task 5.1 — Confirm CORS config is live
- After Task 2.1 edit and backend restart, run:
  `Invoke-RestMethod http://127.0.0.1:8000/health` and confirm the response
  includes the updated environment (confirms backend reloaded `.env`).

### Task 5.2 — Open console and check health
- Open `http://127.0.0.1:5500/hyqub-console.html` in a browser.
- Click "Check Health".
- **Pass:** Health dot turns green, text shows `development · v0.1.0`.
- **Fail:** Browser devtools shows a CORS error → CORS origins not updated or backend not restarted.

### Task 5.3 — Run full 6-step flow in browser
- Step 1: Generate Keypair → confirm `public_key` appears in carry box.
- Step 2: Register → confirm HTTP 201 and `key_version`.
- Step 3: Wallet State → confirm `registered: true`.
- Step 4: Transaction Intent → confirm `message_hash` 64 chars.
- Step 5: Sign → confirm `signature` in carry box.
- Step 6: Submit → confirm HTTP 200 and `transaction_hash` in result box.
- **Pass:** Real `transaction_hash` visible in Step 6 result box.

---

## PHASE 6 — Final Proof

### Task 6.1 — Print the transaction hash
- State the `transaction_hash` returned from Task 3.7 (or Task 5.3 if
  browser-driven) as explicit proof that the full pipeline executed
  successfully end-to-end.
