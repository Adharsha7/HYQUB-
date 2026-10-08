/**
 * HYQUB devSigner — LOCAL DEVELOPMENT ONLY
 * =========================================
 * Per-wallet ML-DSA-65 session key manager.
 *
 * Each sender wallet has its own independent session key.
 * There is NO single global key shared across wallets.
 *
 * SECURITY RULES:
 *  - Secret keys live ONLY in the module-level Map (private closure).
 *  - Never exported, logged, placed in DOM, localStorage, sessionStorage,
 *    cookies, URL params, data attributes, or error messages.
 *  - Never log request bodies.
 *  - Page refresh clears all session keys. Memory-only is the rule.
 *
 * In production, this module would be replaced by client-side ML-DSA WASM.
 * The public API surface stays the same.
 */

import { devGenerateKeypair, devSign } from './api.js';

// ─── Private per-wallet state ─────────────────────────────────────────────────
// Map<normalizedAddress, { publicKey: string, secretKey: string, registered: boolean }>
const _walletKeys = new Map();

// Map<normalizedAddress, Promise<void>>  — single-flight guards
const _inflightMap = new Map();

function _normalizeAddr(addr) {
  return (addr ?? '').toLowerCase().trim();
}

// ─── Public API ───────────────────────────────────────────────────────────────

/**
 * Ensure a session keypair exists for the given wallet address.
 * If a key already exists for this wallet, returns immediately.
 * Per-wallet single-flight guard prevents concurrent double-generation.
 *
 * @param {string} walletAddress
 * @returns {Promise<void>}
 */
export async function ensureSessionKey(walletAddress) {
  const key = _normalizeAddr(walletAddress);

  if (_walletKeys.has(key)) return;     // already have a key for this wallet

  if (_inflightMap.has(key)) {
    await _inflightMap.get(key);        // join the in-flight generation
    return;
  }

  const p = (async () => {
    const keys = await devGenerateKeypair();
    // Store in module Map only — secret key never leaves this closure
    _walletKeys.set(key, {
      publicKey:  keys.public_key,
      secretKey:  keys.secret_key,   // memory-only, never exported
      registered: false,
    });
  })();

  _inflightMap.set(key, p);
  try {
    await p;
  } finally {
    _inflightMap.delete(key);
  }
}

/**
 * Sign a message hash for a specific wallet's session key.
 * Must be called after ensureSessionKey(walletAddress).
 *
 * @param {string} walletAddress
 * @param {string} messageHash  64-char hex from /transaction-intent
 * @returns {Promise<string>}   base64-encoded ML-DSA-65 signature
 */
export async function signMessage(walletAddress, messageHash) {
  const key = _normalizeAddr(walletAddress);
  const state = _walletKeys.get(key);
  if (!state) throw new Error(`No session key for wallet ${walletAddress}. Call ensureSessionKey() first.`);
  // secret key used inline — never returned or stored elsewhere
  const result = await devSign(state.secretKey, messageHash);
  return result.signature;
}

/**
 * Return the public key for a wallet (safe to use for /register).
 * @param {string} walletAddress
 * @returns {string|null}
 */
export function getPublicKey(walletAddress) {
  return _walletKeys.get(_normalizeAddr(walletAddress))?.publicKey ?? null;
}

/** @param {string} walletAddress @returns {boolean} */
export function isRegistered(walletAddress) {
  return _walletKeys.get(_normalizeAddr(walletAddress))?.registered ?? false;
}

/** Mark a wallet's session key as registered. */
export function markRegistered(walletAddress) {
  const key = _normalizeAddr(walletAddress);
  const state = _walletKeys.get(key);
  if (state) state.registered = true;
}

/** @param {string} walletAddress @returns {boolean} */
export function hasSessionKey(walletAddress) {
  return _walletKeys.has(_normalizeAddr(walletAddress));
}

/**
 * Session status for a wallet — safe for UI display, no key material.
 * @param {string} walletAddress
 * @returns {'active'|'not started'}
 */
export function sessionStatus(walletAddress) {
  return hasSessionKey(walletAddress) ? 'active' : 'not started';
}

/**
 * Overall session status label (any active wallet).
 * @returns {string}
 */
export function anySessionActive() {
  return _walletKeys.size > 0;
}
