# HYQUB — Post-Quantum Smart Account

HYQUB is an ERC-4337 smart wallet where every transaction is
authorised by an **ML-DSA-65 (CRYSTALS-Dilithium)** signature verified
off-chain by a verifier quorum, then wrapped in an ECDSA approval token
checked on-chain by `HYQUBWallet.validateUserOp()`.

> The PQ layer is an off-chain authorisation gate.  
> The on-chain check is classical ECDSA via `ecrecover`.  
> HYQUB is **not** described as "fully quantum-proof".

---

## Repository layout

```
HYQUB/
├── backend/          FastAPI PQ Verification Engine
│   ├── app/          Application source (api, services, crypto, utils)
│   ├── tests/        Automated pytest suite (unit + integration)
│   ├── scripts/      Manual diagnostic/operational scripts
│   ├── .env.example  Configuration template — copy to .env and fill in
│   └── requirements.txt  Pinned Python dependencies
├── blockchain/       Foundry smart contracts
│   ├── src/          HYQUBRegistry.sol · HYQUBWallet.sol · TestTarget.sol
│   ├── test/         Forge test suite (51 tests)
│   ├── script/       Deployment scripts
│   ├── lib/          Forge dependencies (managed by foundry.lock)
│   └── foundry.lock  Pinned dependency commits
├── hyqub-console.html  Standalone browser console (vanilla JS, no build)
├── start_anvil.sh    Start Anvil with persistent state
└── start_hyqub.sh    Start Anvil + backend together
```

---

## Prerequisites

| Dependency | Version tested | Install |
|---|---|---|
| Python | 3.14 | system / pyenv |
| Foundry (forge, cast, anvil) | latest stable | https://getfoundry.sh |
| liboqs | system package | see below |
| Git | any | system |

### liboqs (required for ML-DSA-65)

`liboqs-python` (the `oqs` Python module) requires the **liboqs C library**
installed at the system level. It cannot be installed via pip alone.

**Ubuntu / Debian / Kali:**
```bash
sudo apt-get update
sudo apt-get install -y cmake ninja-build libssl-dev
# Build and install liboqs from source
git clone --depth 1 https://github.com/open-quantum-safe/liboqs
cd liboqs && mkdir build && cd build
cmake -GNinja -DBUILD_SHARED_LIBS=ON ..
ninja && sudo ninja install
sudo ldconfig
```

Or if your distro ships a package:
```bash
sudo apt-get install -y liboqs-dev   # Kali / newer Debian
```

---

## Quick start

### 1. Clone and initialise blockchain dependencies

```bash
git clone <repo-url> HYQUB
cd HYQUB/blockchain
git submodule update --init --recursive
```

If submodules are not initialised, `forge test` will fail with
"Source not found" errors for `forge-std`, `account-abstraction`, and
`openzeppelin-contracts`. Run the command above to fix this.

Dependency versions are pinned in `blockchain/foundry.lock`:

| Library | Tag | Commit |
|---|---|---|
| forge-std | v1.16.2 | `bf647bd6` |
| account-abstraction | v0.9.0 | `b36a1ed5` |
| openzeppelin-contracts | v5.7.0 | `cab19933` |

To install dependencies without git submodule history (faster, for CI):
```bash
cd blockchain
forge install foundry-rs/forge-std --no-git
forge install eth-infinitism/account-abstraction --no-git
forge install OpenZeppelin/openzeppelin-contracts --no-git
```

### 2. Set up the backend

```bash
cd backend
python3 -m venv venv
source venv/bin/activate          # Windows WSL: same command
pip install -r requirements.txt
```

> `liboqs-python` will fail to install if the liboqs C library is not
> present. Install it first (see Prerequisites above).

### 3. Configure environment

```bash
cp backend/.env.example backend/.env
# Edit backend/.env and fill in:
#   HYQUB_REGISTRAR_PRIVATE_KEY
#   HYQUB_APPROVAL_SIGNER_PRIVATE_KEY
#   HYQUB_ENTRYPOINT_ADDRESS
#   HYQUB_REGISTRY_ADDRESS
#   HYQUB_WALLET_ADDRESS
#   HYQUB_TEST_TARGET_ADDRESS
```

For local development the remaining defaults are correct as-is.

### 4. Start Anvil (local chain)

```bash
# From repo root (WSL / Linux):
./start_anvil.sh
```

This starts Anvil on `http://127.0.0.1:8545` with `--load-state` from
`blockchain/anvil-state/anvil-state.json` so contract deployments
persist across restarts.

### 5. Start the backend

```bash
cd backend
source venv/bin/activate
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Health check: `curl http://127.0.0.1:8000/health`

---

## Running tests

### Blockchain (Forge)

```bash
cd blockchain
forge test              # all 51 tests
forge test --summary    # with per-suite counts
forge test -vvv         # verbose (shows logs on failure)
```

### Backend (pytest)

```bash
cd backend
source venv/bin/activate

# Unit tests only (no Anvil required):
pytest -m "not integration" -q

# Integration tests (requires Anvil + backend running):
pytest -m integration -q

# All tests:
pytest -q
```

See `backend/tests/` for the full test suite.  
See `backend/scripts/` for manual diagnostic scripts.

---

## Transaction flow (overview)

```
1. Generate ML-DSA-65 keypair  (client-side; secret key never leaves device)
2. POST /register              → SHA-256(pubkey) stored in HYQUBRegistry
3. GET  /transaction-intent    → canonical message_hash
4. Client signs message_hash.encode("utf-8") with ML-DSA secret key
5. POST /submit-transaction    → 2-of-2 quorum → ApprovalToken → EntryPoint
6. HYQUBWallet.validateUserOp  → on-chain ECDSA + intent hash check
```

See `backend/README.md` for the full API reference.  
See `blockchain/README.md` for contract architecture details.

---

## Security notes

- `HYQUB_ENVIRONMENT` defaults to `production`. Dev routes (`/dev/sign`,
  `/dev/generate-keypair`) require **both** `HYQUB_ENABLE_DEV_TOOLS=true`
  **and** `chain_id == 31337`. The application refuses to start if dev
  tools are enabled on a non-local chain.
- Never commit `.env`. It is excluded by `.gitignore`.
- The two in-process verifiers share the same Python process. Independent
  trust boundaries require splitting them into separate services (Phase 2+).
