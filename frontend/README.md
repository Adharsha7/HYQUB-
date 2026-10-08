# HYQUB Payment Frontend

Plain HTML + CSS + vanilla JavaScript (ES modules). No framework, no bundler, no npm build step.

## Prerequisites

- Anvil running on `http://127.0.0.1:8545` (chain ID 31337)
- HYQUB backend running on `http://127.0.0.1:8000` (with `HYQUB_ENABLE_DEV_TOOLS=true`)
- Python 3 (for the static file server)

## Setup

```bash
cp js/config.example.js js/config.local.js
# Edit js/config.local.js with real values if needed
# (defaults already contain the correct deployed wallet and Anvil addresses)
```

## Running

**IMPORTANT**: ES modules require HTTP — they do NOT work from `file://`.

Serve on **port 3000** because that is the only port in `HYQUB_CORS_ORIGINS`:

```bash
cd ~/HYQUB/frontend
python3 -m http.server 3000
```

Then open **http://localhost:3000** in your browser.

⚠️ **Never open `http://127.0.0.1:3000`** — CORS is configured for `localhost:3000` only, so `127.0.0.1` will fail with a CORS error.

## File structure

```
frontend/
├── index.html           Single-page app shell
├── css/styles.css       All styles (CSS variables, no framework)
├── js/
│   ├── config.js        Re-exports from config.local.js (only place env vars appear)
│   ├── config.local.js  GITIGNORED — real values (wallet address, API URL)
│   ├── config.example.js  Committed template with placeholder values
│   ├── api.js           Fetch wrappers for real backend endpoints only
│   ├── wei.js           BigInt-safe ETH/wei conversion helpers
│   ├── devSigner.js     LOCAL DEV ONLY — session keypair management
│   ├── paymentFlow.js   Full payment orchestration (all API calls)
│   └── app.js           UI wiring (no fetch calls)
├── tests/
│   └── wei.test.js      node --test unit tests for wei.js
└── README.md
```

## Running tests

```bash
cd ~/HYQUB/frontend
node --test tests/wei.test.js
```

## Payment flow

1. Dashboard loads live wallet state from `GET /wallet/{address}/state`
2. User selects a recipient and enters an ETH amount
3. Review screen shows the payment details
4. On confirm, the frontend runs automatically:
   - `GET /dev/generate-keypair` (first payment only — stores in memory)
   - `POST /register` (first payment only — marks as registered in memory)
   - `GET /transaction-intent` → canonical `message_hash`
   - `POST /dev/sign` → ML-DSA signature
   - `POST /submit-transaction` → real Anvil transaction hash
5. Result screen shows the transaction hash

The backend waits for the Anvil receipt before returning, so the frontend does NOT poll.

## Session key model

The ML-DSA keypair is generated **once per browser session** (not per payment).
Page refresh clears the key from memory. The secret key is **never** stored in
localStorage, sessionStorage, cookies, URL, DOM, or console output.

If the page is refreshed while the backend still has the old key registered,
the app shows: *"Session key lost. Restart the backend and reload."*

## Security

- No private keys in the frontend
- No direct blockchain submission from the browser
- The backend is the only transaction submitter
- All backend-returned strings are rendered with `textContent`, not `innerHTML`

## CORS

The backend `HYQUB_CORS_ORIGINS` must include `http://localhost:3000`.
Check `backend/.env` — it should contain:
```
HYQUB_CORS_ORIGINS=["http://localhost:3000","http://127.0.0.1:5500","http://localhost:5500"]
```
