# HYQUB Blockchain â€” Foundry Smart Contracts

Solidity contracts for the HYQUB post-quantum smart account system,
built with [Foundry](https://getfoundry.sh).

---

## Contracts

| Contract | Purpose |
|---|---|
| `src/HYQUBRegistry.sol` | On-chain registry: maps wallet â†’ `{ SHA-256(pubkey), keyVersion }`. `registrar = msg.sender` (no-arg constructor). Only the registrar can write. |
| `src/HYQUBWallet.sol` | ERC-4337 `IAccount`. Validates HYQUB approval tokens in `validateUserOp`. Constructor args: `registry`, `approvalSigner`, `entryPoint`. |
| `src/TestTarget.sol` | Minimal `setValue(uint256)` contract used in integration tests. |
| `script/DeployHYQUB.s.sol` | Deploys Registry + EntryPoint + Wallet together. |

---

## Setup

### Install Foundry

```bash
curl -L https://foundry.paradigm.xyz | bash
foundryup
```

### Install dependencies

Dependencies are pinned in `foundry.lock`. Three options:

**Option A â€” git submodules (recommended for development):**
```bash
cd blockchain
git submodule update --init --recursive
```

**Option B â€” forge install without git history (faster, good for CI):**
```bash
cd blockchain
forge install foundry-rs/forge-std --no-git
forge install eth-infinitism/account-abstraction --no-git
forge install OpenZeppelin/openzeppelin-contracts --no-git
```

**Option C â€” if you already have the repo and lib/ is missing:**
```bash
cd blockchain
forge install
```

Pinned dependency versions (`foundry.lock`):

| Library | Tag | Commit |
|---|---|---|
| `lib/forge-std` | v1.16.2 | `bf647bd6046f2f7da30d0c2bf435e5c76a780c1b` |
| `lib/account-abstraction` | v0.9.0 | `b36a1ed52ae00da6f8a4c8d50181e2877e4fa410` |
| `lib/openzeppelin-contracts` | v5.7.0 | `cab19933c33c2ad1d4c7a84864a3601dddfd16f3` |

Do not change these versions without updating `foundry.lock` and
re-running the full test suite.

---

## Build

```bash
forge build
```

---

## Test

```bash
forge test              # run all 51 tests
forge test --summary    # per-suite pass/fail table
forge test -vvv         # verbose output (logs on failure)
forge test --match-test test_ValidApproval  # run specific test
```

### Test suite overview

| Suite | Tests | What it covers |
|---|---|---|
| `HYQUBRegistryTest` | 13 | Register, rotate, access control, key version increments |
| `HYQUBWalletTest` | 14 | Constructor, deposit/withdraw, owner execute, access control |
| `ValidateUserOpSuccessTest` | 4 | Full validateUserOp pass, nonce replay, tampered target, wrong signer |
| `ValidateUserOpTest` | 4 | EntryPoint-only access, malformed sig, prefund |
| `TransactionIntentReconstructionTest` | 5 | Hash reconstruction, selector check, field sensitivity |
| `EntryPointIntegrationTest` | 1 | Full `handleOps` end-to-end with real EntryPoint |
| `EntryPointCalldataIntegrationTest` | 2 | Contract call via UserOp, tampered calldata |
| `ApprovalPayloadTest` | 1 | Pythonâ†”Solidity ABI encoding compatibility vector |
| `ApprovalSignatureTest` | 3 | EIP-191 sign/recover, tampered hash, wrong signer |
| `TransactionIntentTest` | 1 | Pythonâ†”Solidity hash compatibility vector |
| `PythonSignatureCompatibilityTest` | 1 | Cross-language signature recovery |
| `CounterTest` | 2 | Foundry scaffold (unrelated) |

The `*CompatibilityVector` tests pin known inputs/outputs and fail if
the ABI encoding ever drifts between Python and Solidity.
**Do not change these tests without also changing the backend crypto.**

---

## Deploy (local Anvil)

```bash
# Start Anvil first (from repo root):
./start_anvil.sh

# Deploy contracts:
forge script script/DeployHYQUB.s.sol \
  --rpc-url http://127.0.0.1:8545 \
  --private-key <DEPLOYER_KEY> \
  --broadcast
```

Record deployed addresses in `backend/.env`:
- `HYQUB_ENTRYPOINT_ADDRESS`
- `HYQUB_REGISTRY_ADDRESS`
- `HYQUB_WALLET_ADDRESS`

---

## Remappings

```
account-abstraction/ â†’ lib/account-abstraction/contracts/
forge-std/           â†’ lib/forge-std/src/
@openzeppelin/contracts/ â†’ lib/openzeppelin-contracts/contracts/
```

Defined in `remappings.txt`. Do not move `lib/` without updating this.

---

## Security notes

- `HYQUBRegistry.registrar` is set to `msg.sender` at deploy time and
  is immutable. If the registrar key is compromised, an attacker can
  rotate any wallet's key hash. There is no multi-sig or timelock in
  Phase 1.
- `HYQUBWallet.validateUserOp` ignores the ERC-4337 `userOpHash`
  parameter intentionally â€” HYQUB binds to the TransactionIntent hash
  instead, which encodes `block.chainid` to prevent cross-chain replay.
- `expires_at` is present in the Python `ApprovalTokenPayload` model but
  is intentionally **excluded** from the on-chain ABI encoding (Solidity
  parity). On-chain replay protection is the `usedApprovalNonces` mapping.