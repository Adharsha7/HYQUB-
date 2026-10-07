---
inclusion: always
---

# HYQUB — Architecture Ground Truth

This steering doc captures verified facts about the HYQUB project.
Treat these as ground truth in every session; do not re-derive them from folder names.

## Project Layout

```
HYQUB/
├── backend/          FastAPI PQ Verification Engine
│   ├── app/
│   │   ├── api/      Route files (one per endpoint group)
│   │   ├── models/   Pydantic request/response models
│   │   ├── services/ Business logic (register, verify, rotate, submit, quorum, approval)
│   │   ├── crypto/   ML-DSA-65 (liboqs), ABI encoding, ECDSA approval signing
│   │   └── utils/    blockchain.py (web3/contract calls), storage.py (in-memory wallet store)
│   ├── .env          Live config (NEVER commit secrets)
│   └── venv/         Python virtualenv (activated via source venv/bin/activate in WSL)
├── blockchain/       Foundry/Solidity contracts
│   ├── src/          HYQUBRegistry.sol, HYQUBWallet.sol, EntryPoint (ERC-4337)
│   ├── out/          Compiled Foundry artifacts (ABI JSON files loaded by blockchain.py)
│   └── anvil-state/  Persisted Anvil chain state
├── hyqub-console.html  Standalone frontend console (vanilla JS, no build step)
├── anvil.log         Anvil process log
├── backend.log       Uvicorn process log
├── start_anvil.sh    Starts Anvil with --load-state from anvil-state/anvil-state.json
└── start_hyqub.sh    Checks/starts Anvil → contracts → backend in order
```

## Real API Endpoints

| Method | Path | Notes |
|--------|------|-------|
| GET | /health | Liveness check. Returns environment, version, verifier_id. |
| GET | / | Welcome message. |
| POST | /register | Register wallet + ML-DSA public key. Returns key_version + tx_hash. HTTP 201. |
| POST | /verify | Standalone ML-DSA signature check. HTTP 200. |
| POST | /rotate | Replace registered public key. Increments key_version. HTTP 200. |
| GET | /transaction-intent | Compute canonical message_hash (query params). HTTP 200. |
| POST | /submit-transaction | Full quorum verify → approval token → ERC-4337 UserOp submission. HTTP 200. |
| GET | /wallet/{address}/state | Live on-chain wallet state. HTTP 200. |
| GET | /dev/generate-keypair | **DEV ONLY** — generate ML-DSA-65 keypair. 404 in production. |
| POST | /dev/sign | **DEV ONLY** — sign a message with supplied secret key. 404 in production. |

Dev-only routes are only registered when `HYQUB_ENVIRONMENT=development` (hard structural gate in main.py — not a feature flag).

## Client Flow (strict order)

```
1. GET /dev/generate-keypair       → { public_key, secret_key } (base64)
2. POST /register                  → { key_version, transaction_hash }
3. GET /wallet/{addr}/state        → confirm registered=true, key_version
4. GET /transaction-intent         → { message_hash (64-char hex), chain_id, key_version }
5. POST /dev/sign                  → { signature } (base64, signs message_hash as UTF-8 bytes)
6. POST /submit-transaction        → { transaction_hash, approval_nonce }
```

**Critical constraints across steps:**
- `target`, `value_wei`, `data` used in step 4 MUST be identical in step 6. The backend recomputes the hash itself and never trusts a client-supplied hash.
- `key_version` is embedded in the hash. After `POST /rotate`, steps 4–6 must be re-run with the new key.
- `ml_dsa_public_key` registered in step 2 must be the keypair used to sign in step 5.
- All ML-DSA keys and signatures are **standard base64** (RFC 4648), not hex, not URL-safe base64.
- `message_hash` is a 64-char lowercase hex string (SHA-256, no `0x` prefix).
- `value_wei` must be a non-negative integer (no decimals).
- Addresses must match `^0x[a-fA-F0-9]{40}$`; normalized to lowercase internally.

## Crypto Layer

- **ML-DSA-65** (NIST post-quantum standard) via `liboqs` Python binding (`oqs` package).
- Transaction intent: `SHA-256(ABI-encode("HYQUB_TX_V1", chain_id, wallet, target, value, data, key_version))`
- Approval payload: `SHA-256(ABI-encode("HYQUB_APPROVAL_V1", wallet, message_hash_bytes32, key_version, nonce, issued_at, verifier_ids))` — note `expires_at` intentionally excluded (Solidity parity).
- Approval token signature: **Ethereum personal-sign (EIP-191)** via `eth_account`, with `approval_signer_private_key`.
- On-chain UserOp signature: `abi.encode(bytes approvalPayload, bytes approvalSignature)`.

## State & Persistence

| Store | Survives restart? | Notes |
|-------|------------------|-------|
| `InMemoryWalletStorage` | ❌ No | Resets on backend restart. Re-register to resync. |
| `UsedNonceStore` | ❌ No | In-memory replay protection. On-chain `usedApprovalNonces` is the real guard. |
| Anvil chain state | ✅ Yes | Loaded from `blockchain/anvil-state/anvil-state.json` on each restart. |
| `.last_deployment.json` | ✅ Yes | Contract addresses, written by deploy script. |

Re-registering an already-on-chain wallet produces HTTP 201 with message "already on-chain; local record synced" — this is expected after a backend restart, not an error.

## Config (.env)

All env vars use prefix `HYQUB_`. File lives at `backend/.env`.

| Var | Default | Required |
|-----|---------|----------|
| HYQUB_ENVIRONMENT | development | No |
| HYQUB_VERIFIER_ID | verifier-a | No |
| HYQUB_REQUIRED_QUORUM | 2 | No |
| HYQUB_CORS_ORIGINS | ["http://localhost:3000"] | No |
| HYQUB_RPC_URL | http://127.0.0.1:8545 | No |
| HYQUB_REGISTRAR_PRIVATE_KEY | — | **Yes** |
| HYQUB_APPROVAL_SIGNER_PRIVATE_KEY | — | **Yes** |
| HYQUB_ENTRYPOINT_ADDRESS | — | **Yes** |
| HYQUB_REGISTRY_ADDRESS | — | **Yes** |
| HYQUB_WALLET_ADDRESS | — | **Yes** |
| HYQUB_TEST_TARGET_ADDRESS | — | **Yes** |

CORS: `allow_credentials=True` is set, so `["*"]` cannot be used. List origins explicitly.

## Known Issues / Gotchas

1. **`requirements.txt` is stale** — missing `web3`, `eth_abi`, `eth_account`, `oqs`, `pydantic_settings`. Always check `pip list` inside the venv rather than trusting requirements.txt.
2. **`GET /wallet/{address}/state`** calls `get_registry_contract()` with no argument but the function signature requires a `web3` arg. Returns 502 TypeError in current code.
3. **Verifiers are in-process** — `verifier-a` and `verifier-b` in `submit_transaction_service.py` are two `PQVerifier` instances in the same process, checking the same key. Not independent trust boundaries; acknowledged as a future split.
4. **Approval nonce is `int(time.time() * 1000)`** — millisecond timestamp, not collision-safe under concurrent load.
5. **`settings = get_settings()` runs at module import in `blockchain.py`** — if `.env` is missing required vars the entire app fails to start, not just the blockchain routes.
6. **All scripts are WSL bash** — `start_hyqub.sh`, `start_anvil.sh`, `setup_hyqub_env.sh` target `$HOME/HYQUB` in WSL. Run them from WSL, not PowerShell.
7. **`hyqub-console.html` is served by `python -m http.server 5500`** from `HYQUB/` root in a background process (terminalId: term_1790407406111_8io0atp9pq5).
8. **`TestTarget` has no fallback/receive function.** Calling it with `data=0x` (empty calldata) reverts inside `HYQUBWallet.execute()` with `"HYQUBWallet: execution failed"`. Always use ABI-encoded calldata: `setValue(42)` = `0x55241077000000000000000000000000000000000000000000000000000000000000002a`. The outer `handleOps` tx still gets `status: 0x1` (ERC-4337 bundler is paid regardless), but the UserOperation itself is marked as reverted via a `UserOperationRevertReason` log.

## Deployed Contract Addresses (local Anvil)

From `blockchain/.last_deployment.json`:
```json
{
  "HYQUBRegistry": "0x5fbdb2315678afecb367f032d93f642f64180aa3",
  "EntryPoint":    "0xe7f1725e7734ce288f8367e1bb143e90bb3f0512",
  "HYQUBWallet":   "0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0"
}
```

Anvil default accounts (10 000 ETH each):
- Account 0: `0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266` (registrar/bundler — matches `HYQUB_REGISTRAR_PRIVATE_KEY`)
- Account 1: `0x70997970C51812dc3A010C7d01b50e0d17dc79C8`
- Account 2: `0x3C44CdDdB6a900fa2b585dd299e03d12FA4293BC`
