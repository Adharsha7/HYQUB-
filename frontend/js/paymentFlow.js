/**
 * HYQUB paymentFlow — payment orchestration.
 *
 * All API calls live here. app.js contains NO fetch() calls.
 * Progress is reported via a callback.
 *
 * Flow per payment:
 *  1. Preflight: GET /wallet/{sender}/state — chain_id check, balance check
 *  2. ensureSessionKey(sender)              — first payment from this wallet
 *  3. Register sender if not yet in this session — first payment only
 *  4. GET /transaction-intent               — get message_hash
 *  5. POST /dev/sign (sender's key)         — sign message_hash
 *  6. POST /submit-transaction              — submit, waits for receipt
 *  7. Return { transactionHash }
 *
 * Per-wallet registration (from register_service.py):
 *  - 201: wallet not in memory → stored. Works for fresh OR restarted backend.
 *  - 409: wallet already in memory with ANOTHER key →
 *         if this session hasn't registered this wallet yet: show "Session key lost".
 *  - /submit-transaction 404: backend memory lost → "Backend session lost".
 */

import { getWalletState, registerWallet, getTransactionIntent, submitTransactionRaw } from './api.js';
import { ensureSessionKey, signMessage, getPublicKey, isRegistered, markRegistered } from './devSigner.js';
import { buildSubmitBody, compareWei } from './wei.js';
import { CHAIN_ID } from './config.js';

// ─── Step labels ──────────────────────────────────────────────────────────────

export const STEPS = [
  'Preparing payment',
  'Checking sender wallet',
  'Preparing security key',
  'Registering security key',
  'Creating transaction intent',
  'Signing',
  'Security verification',
  'Submitting transaction',
  'Confirming on chain',
  'Payment successful',
];

// ─── Error types ──────────────────────────────────────────────────────────────

export class PaymentError extends Error {
  constructor(code, message) { super(message); this.code = code; }
}

export const ERR = {
  SESSION_KEY_LOST:     'SESSION_KEY_LOST',
  BACKEND_SESSION_LOST: 'BACKEND_SESSION_LOST',
  SIGNATURE_FAILED:     'SIGNATURE_FAILED',
  VALIDATION_ERROR:     'VALIDATION_ERROR',
  UNREACHABLE:          'UNREACHABLE',
  PREFLIGHT_CHAIN:      'PREFLIGHT_CHAIN',
  PREFLIGHT_BALANCE:    'PREFLIGHT_BALANCE',
  PREFLIGHT_FAILED:     'PREFLIGHT_FAILED',
  SELF_TRANSFER:        'SELF_TRANSFER',
};

function mapApiError(err, context) {
  const s = err.status;
  if (!s) throw new PaymentError(ERR.UNREACHABLE, 'Unable to reach HYQUB backend. Check that the backend is running.');
  if (context === 'register' && s === 409)
    throw new PaymentError(ERR.SESSION_KEY_LOST,
      'Session key lost. The backend still holds the previous session key for this wallet. ' +
      'Restart the backend (clears in-memory registration) and reload this page to start a new session.');
  if (context === 'submit' && s === 404)
    throw new PaymentError(ERR.BACKEND_SESSION_LOST,
      'Backend session lost. The backend no longer holds this wallet\'s security profile ' +
      '(it was probably restarted). Restart the backend and reload this page.');
  if (context === 'submit' && s === 400)
    throw new PaymentError(ERR.SIGNATURE_FAILED, 'Signature or security verification failed. The session key may be mismatched.');
  if (s === 422) {
    const d = err.data?.detail ?? err.message;
    const safe = typeof d === 'string' ? d.slice(0, 200) : 'Invalid payment request.';
    throw new PaymentError(ERR.VALIDATION_ERROR, `Invalid payment request: ${safe}`);
  }
  if (s >= 500) throw new PaymentError(ERR.UNREACHABLE, 'Backend or blockchain unavailable.');
  throw new PaymentError(ERR.UNREACHABLE, `Unexpected error (HTTP ${s}).`);
}

// ─── runPayment ───────────────────────────────────────────────────────────────

/**
 * @param {{
 *   senderAddress: string,   // sender wallet address (from SENDER_WALLETS)
 *   target:        string,   // recipient address
 *   valueWei:      string,   // validated wei string
 *   data?:         string,   // calldata, default "0x"
 * }} params
 * @param {(stepIndex: number, label: string) => void} onStep
 * @returns {Promise<{transactionHash: string, valueWei: string, target: string, senderAddress: string}>}
 * @throws {PaymentError}
 */
export async function runPayment({ senderAddress, target, valueWei, data = '0x' }, onStep) {

  // ── Validate no self-transfer ────────────────────────────────────────────
  if (senderAddress.toLowerCase() === target.toLowerCase()) {
    throw new PaymentError(ERR.SELF_TRANSFER, 'Sender and recipient cannot be the same wallet.');
  }

  // ── Step 0: Preflight ────────────────────────────────────────────────────
  onStep(0, STEPS[0]);
  onStep(1, STEPS[1]);

  let walletState;
  try { walletState = await getWalletState(senderAddress); }
  catch { throw new PaymentError(ERR.PREFLIGHT_FAILED, 'Could not read sender wallet state. Check Anvil and backend are running.'); }

  if (walletState.chain_id !== CHAIN_ID)
    throw new PaymentError(ERR.PREFLIGHT_CHAIN, `Chain mismatch: expected ${CHAIN_ID}, got ${walletState.chain_id}.`);

  if (compareWei(valueWei, walletState.balance_wei) > 0)
    throw new PaymentError(ERR.PREFLIGHT_BALANCE, `Insufficient balance. Requested ${valueWei} wei, available ${walletState.balance_wei} wei.`);

  // ── Step 2: Ensure session key for THIS sender wallet ────────────────────
  onStep(2, STEPS[2]);
  try { await ensureSessionKey(senderAddress); }
  catch (err) { throw new PaymentError(ERR.UNREACHABLE, 'Failed to generate session key: ' + err.message); }

  // ── Step 3: Register THIS sender wallet (first payment only) ────────────
  if (!isRegistered(senderAddress)) {
    onStep(3, STEPS[3]);
    try {
      await registerWallet(senderAddress, getPublicKey(senderAddress));
      markRegistered(senderAddress);
    } catch (err) { mapApiError(err, 'register'); }
  }

  // ── Step 4: Transaction intent ───────────────────────────────────────────
  onStep(4, STEPS[4]);

  let intentResponse;
  try {
    intentResponse = await getTransactionIntent({ walletAddress: senderAddress, target, valueWei, data });
  } catch (err) { mapApiError(err, 'intent'); }

  // ONE immutable transaction object from VALIDATED USER INPUT.
  // Only message_hash, chain_id, key_version come from the response.
  // valueWei comes from the caller's validated string — never from response.value_wei
  // (which is a lossy Number via JSON.parse).
  const txObject = Object.freeze({
    walletAddress: senderAddress,
    target,
    valueWei,
    data,
    messageHash: intentResponse.message_hash,
    chainId:     intentResponse.chain_id,
    keyVersion:  intentResponse.key_version,
  });

  // ── Step 5: Sign (using THIS sender's session key) ───────────────────────
  onStep(5, STEPS[5]);

  let signature;
  try { signature = await signMessage(senderAddress, txObject.messageHash); }
  catch (err) { throw new PaymentError(ERR.UNREACHABLE, 'Signing failed: ' + err.message); }

  // ── Step 6+7: Security verification / Submit ────────────────────────────
  onStep(6, STEPS[6]);
  onStep(7, STEPS[7]);

  let submitResult;
  try {
    const body = buildSubmitBody({
      walletAddress: txObject.walletAddress,
      target:        txObject.target,
      valueWei:      txObject.valueWei,
      data:          txObject.data,
      signature,
    });
    submitResult = await submitTransactionRaw(body);
  } catch (err) {
    if (err instanceof PaymentError) throw err;
    mapApiError(err, 'submit');
  }

  // ── Step 8: Confirm on chain ─────────────────────────────────────────────
  // /submit-transaction waits for receipt internally — no polling needed.
  onStep(8, STEPS[8]);

  if (!submitResult.success)
    throw new PaymentError(ERR.UNREACHABLE, submitResult.message ?? 'Transaction not successful.');
  if (!submitResult.transaction_hash)
    throw new PaymentError(ERR.UNREACHABLE, 'Backend reported success but returned no transaction hash.');

  // ── Step 9: Done ─────────────────────────────────────────────────────────
  onStep(9, STEPS[9]);

  return {
    transactionHash: submitResult.transaction_hash,
    approvalNonce:   submitResult.approval_nonce ?? null,
    valueWei,
    target,
    senderAddress,
  };
}
