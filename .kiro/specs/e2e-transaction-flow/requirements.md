# Requirements — HYQUB End-to-End Transaction Flow

## Goal

Prove that a complete HYQUB transaction executes successfully from keypair
generation through to an on-chain inclusion, and that the standalone
`hyqub-console.html` can drive the same flow from a browser without CORS
errors.

"Working end-to-end" is defined by these concrete acceptance criteria:

---

## REQ-1  Infrastructure reachability

- **REQ-1.1** Anvil is listening on `http://127.0.0.1:8545` and responds
  to `eth_blockNumber` with a non-zero result.
- **REQ-1.2** The FastAPI backend is listening on `http://127.0.0.1:8000`
  and `GET /health` returns HTTP 200 with `status: "healthy"` and
  `environment: "development"`.
- **REQ-1.3** The dev-only endpoints (`GET /dev/generate-keypair`,
  `POST /dev/sign`) exist and return HTTP 200 (confirming
  `HYQUB_ENVIRONMENT=development` is set).

---

## REQ-2  Wallet registration

- **REQ-2.1** `POST /register` with a valid ML-DSA-65 public key and the
  wallet address `0x9fe46736679d2d9a65f0992f2272de9f3c7fa6e0` returns HTTP
  201 with `success: true`, a numeric `key_version >= 1`, and either a
  real `transaction_hash` (0x-prefixed hex) or `null` if already on-chain.
- **REQ-2.2** If the backend has been restarted and the wallet is already
  on-chain, re-registration succeeds (no 409) and `key_version` matches
  what the chain reports.
- **REQ-2.3** `GET /wallet/{address}/state` returns `registered: true` and
  a `key_version` consistent with REQ-2.1.

---

## REQ-3  Transaction intent hash

- **REQ-3.1** `GET /transaction-intent` with valid query params returns HTTP
  200 with a 64-character lowercase hex `message_hash`.
- **REQ-3.2** The response includes the live `chain_id` and `key_version`
  that were used to compute the hash. The client must use these exact
  values in signing and submission.

---

## REQ-4  ML-DSA signing

- **REQ-4.1** `POST /dev/sign` with the secret key from REQ-2 and the
  `message_hash` from REQ-3 returns HTTP 200 with a base64-encoded
  `signature`.
- **REQ-4.2** `POST /verify` with the same wallet, the same `message_hash`
  as `message`, and the signature from REQ-4.1 returns `verified: true`.

---

## REQ-5  Full transaction submission

- **REQ-5.1** `POST /submit-transaction` with `wallet_address`, `target`,
  `value_wei`, `data`, and `ml_dsa_signature` (all matching what was used
  in REQ-3 and REQ-4) returns HTTP 200 with `success: true` and a non-null
  `transaction_hash`.
- **REQ-5.2** The `transaction_hash` from REQ-5.1 is retrievable from Anvil
  (i.e., `eth_getTransactionReceipt` returns a receipt with `status: 1`).
- **REQ-5.3** Submitting the same signature a second time is rejected (replay
  protection) — either HTTP 400 from the in-process nonce store or an
  on-chain revert surfaced as HTTP 502.

---

## REQ-6  Browser console CORS

- **REQ-6.1** `HYQUB_CORS_ORIGINS` in `backend/.env` includes the origin
  from which `hyqub-console.html` is served (currently
  `http://127.0.0.1:5500`).
- **REQ-6.2** A browser `fetch` from `http://127.0.0.1:5500` to
  `http://127.0.0.1:8000/health` succeeds with no CORS error (verified by
  completing the health-check step in the console UI).
- **REQ-6.3** The full six-step console flow (generate → register → state →
  intent → sign → submit) completes in the browser and displays a real
  `transaction_hash`.

---

## Out of scope for this spec

- Deploying contracts (already deployed; state persisted in Anvil).
- Key rotation (utility endpoint; separate concern).
- Production hardening (separate verifiers, persistent storage, DB nonces).
