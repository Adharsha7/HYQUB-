/**
 * HYQUB frontend — config EXAMPLE / TEMPLATE
 *
 * Copy this to config.local.js and fill in real values.
 * config.local.js is GITIGNORED and must never be committed.
 *
 * To discover sender wallet addresses:
 *   - Check backend/.env (HYQUB_WALLET_ADDRESS)
 *   - Check blockchain/.last_deployment.json (HYQUBWallet)
 *   - Verify each via GET /wallet/{address}/state (chain_id must be 31337)
 *
 * To discover Anvil recipient addresses:
 *   curl -s http://127.0.0.1:8545 \
 *     -d '{"jsonrpc":"2.0","method":"eth_accounts","params":[],"id":1}'
 *
 * NEVER include private keys here or anywhere in the frontend.
 */

export const API_BASE_URL = 'http://127.0.0.1:8000';

export const CHAIN_ID = 31337;

/**
 * Configured HYQUB sender wallets.
 * Each must be a deployed HYQUBWallet contract verified by GET /wallet/{addr}/state.
 */
export const SENDER_WALLETS = [
  { label: 'HYQUB Wallet A', address: '0xYOUR_WALLET_A_HERE' },
  { label: 'HYQUB Wallet B', address: '0xYOUR_WALLET_B_HERE' },
];

/**
 * Recipient presets — real Anvil public addresses only.
 * Exclude sender wallets from this list to avoid accidental self-transfer.
 * NO private keys.
 */
export const RECIPIENT_PRESETS = [
  { label: 'Anvil Account 0 (deployer)', address: '0xYOUR_ANVIL_0' },
  { label: 'Anvil Account 1',            address: '0xYOUR_ANVIL_1' },
];
