# HYQUB Backend — Manual Scripts

These scripts are run directly with `python <script>.py`, not via
pytest. They require a live Anvil chain at `http://127.0.0.1:8545`.

```bash
cd backend
source venv/bin/activate
python scripts/<script>.py
```

| Script | Purpose |
|---|---|
| `test_blockchain.py` | Verify chain connectivity and registry contract address |
| `test_blockchain_register.py` | Register a fresh random wallet on-chain and print tx hash |
| `test_contract_read.py` | Read `isRegistered` state for a known address |
| `test_contract_write.py` | Submit a `registerWallet` transaction directly |
| `diagnose_pipeline.py` | Full diagnostic: chain state, quorum, approval token, handleOps |

> These scripts are intentionally excluded from the pytest suite.
> They execute blockchain calls at import time, which would cause
> collection errors when Anvil is not running.
> Use `pytest tests/integration/` for automated integration tests.
