# HYQUB Backend — PQ Verification Engine

FastAPI service that orchestrates ML-DSA-65 signature verification,
verifier quorum, approval token issuance, and ERC-4337 UserOperation
submission.

---

## Setup

```bash
# From repo root
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

cp .env.example .env
# Edit .env — fill in private keys and contract addresses
```

> **liboqs required:** `liboqs-python` needs the liboqs C library
> installed at the system level. See the root `README.md` for
> installation instructions.

---

## Running

```bash
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

- API docs: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/health`

---

## Configuration

All settings use the `HYQUB_` prefix and are loaded from `.env`
by `pydantic-settings`. See `.env.example` for every available
variable with descriptions.

Key settings:

| Variable | Default | Notes |
|---|---|---|
| `HYQUB_ENVIRONMENT` | `production` | Set to `development` for debug logging |
| `HYQUB_ENABLE_DEV_TOOLS` | `false` | Must be `true` to register `/dev/*` routes |
| `HYQUB_RPC_URL` | `http://127.0.0.1:8545` | Anvil local chain |
| `HYQUB_REQUIRED_QUORUM` | `2` | Minimum approving verifiers |

Dev routes (`/dev/sign`, `/dev/generate-keypair`) require **both**
`HYQUB_ENABLE_DEV_TOOLS=true` **and** a local chain (`chain_id == 31337`).
The application will refuse to start if dev tools are enabled on a
non-local chain.

---

## API endpoints

| Method | Path | Auth | Notes |
|---|---|---|---|
| GET | `/health` | — | Liveness check |
| GET | `/` | — | Welcome |
| POST | `/register` | — | Register wallet + ML-DSA public key |
| POST | `/verify` | — | Standalone ML-DSA signature check |
| POST | `/rotate` | — | Replace registered key (increments key_version) |
| GET | `/transaction-intent` | — | Compute canonical message_hash |
| POST | `/submit-transaction` | — | Full quorum → approval token → UserOp |
| GET | `/wallet/{address}/state` | — | Live on-chain wallet state |
| GET | `/dev/generate-keypair` | dev only | Generate ML-DSA-65 keypair |
| POST | `/dev/sign` | dev only | Sign message with supplied secret key |

---

## Project structure

```
backend/
├── app/
│   ├── api/        Route files (one per endpoint group)
│   ├── services/   Business logic
│   ├── crypto/     ML-DSA-65, ABI encoding, ECDSA signing
│   ├── models/     Pydantic request/response models
│   ├── utils/      blockchain.py (web3), storage.py (in-memory)
│   ├── config.py   Settings via pydantic-settings
│   └── main.py     App factory
├── tests/
│   ├── unit/       Pure unit tests (no Anvil required)
│   └── integration/ Tests requiring live Anvil + backend
├── scripts/        Manual diagnostic and operational scripts
├── .env.example    Configuration template
└── requirements.txt  Pinned dependencies
```

---

## Running tests

```bash
source venv/bin/activate

# Unit tests only (no Anvil required):
pytest tests/unit/ -q
# or equivalently:
pytest -m "not integration" -q

# Integration tests (Anvil + backend must be running):
pytest tests/integration/ -q
# or equivalently:
pytest -m integration -q
```

---

## Transaction flow

```
GET  /transaction-intent          ← canonical message_hash
     ↓
Client signs message_hash.encode("utf-8") with ML-DSA-65 secret key
     ↓
POST /submit-transaction
     ↓
  ① Re-derive message_hash (backend never trusts client-supplied hash)
  ② PQVerifier-A + PQVerifier-B verify ML-DSA signature
  ③ evaluate_quorum([A, B], required=2)
  ④ ApprovalService → SHA-256(ABI-encode payload) → EIP-191 ECDSA sign
  ⑤ PackedUserOperation → EntryPoint.handleOps()
  ⑥ HYQUBWallet.validateUserOp() → ecrecover → execute()
```

---

## Known limitations (Phase 1)

- Both verifiers run in the same process — no real trust isolation yet.
- `InMemoryWalletStorage` and `UsedNonceStore` reset on backend restart.
  Re-register the wallet after a restart to resync local state.
- Approval nonce is a millisecond timestamp — not collision-safe under
  concurrent load. Replace with a DB sequence in a future phase.
