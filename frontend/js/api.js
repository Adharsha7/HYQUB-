/**
 * HYQUB API client — wrappers for REAL backend endpoints only.
 *
 * Endpoints (from backend source, confirmed):
 *   GET  /health
 *   POST /register
 *   GET  /transaction-intent
 *   POST /submit-transaction
 *   GET  /wallet/{wallet_address}/state
 *   GET  /dev/generate-keypair    (DEV ONLY)
 *   POST /dev/sign                (DEV ONLY)
 *
 * NO invented endpoints. NEVER logs request bodies (may contain key material).
 */

import { API_BASE_URL } from './config.js';

async function apiFetch(endpoint, options = {}) {
  const url = API_BASE_URL + endpoint;
  let response;
  try {
    response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...(options.headers ?? {}) },
      ...options,
    });
  } catch {
    throw new Error('Unable to reach HYQUB backend. Check that the backend is running.');
  }

  let data = null;
  try { data = await response.json(); } catch { data = null; }

  if (!response.ok) {
    const detail = data?.detail ?? data?.message ?? `HTTP ${response.status}`;
    const err = new Error(detail);
    err.status = response.status;
    err.data = data;
    throw err;
  }
  return data;
}

// Health
export const getHealth = () => apiFetch('/health');

// Wallet state — balance_wei is a STRING in the response
export const getWalletState = (addr) =>
  apiFetch(`/wallet/${encodeURIComponent(addr)}/state`);

// Registration — 201 success, 409 already in memory
export const registerWallet = (walletAddress, mlDsaPublicKey) =>
  apiFetch('/register', {
    method: 'POST',
    body: JSON.stringify({ wallet_address: walletAddress, ml_dsa_public_key: mlDsaPublicKey }),
  });

// Transaction intent
// TRAP: response.value_wei is lossy Number — callers must only use message_hash,
// chain_id, key_version from this response; not value_wei.
export const getTransactionIntent = ({ walletAddress, target, valueWei, data }) => {
  const params = new URLSearchParams({
    wallet_address: walletAddress,
    target,
    value_wei: valueWei,   // string — URLSearchParams serialises correctly
    data,
  });
  return apiFetch(`/transaction-intent?${params}`);
};

// Submit — body MUST be pre-built with buildSubmitBody() from wei.js
export const submitTransactionRaw = (bodyString) =>
  apiFetch('/submit-transaction', { method: 'POST', body: bodyString });

// DEV ONLY — keypair generation
export const devGenerateKeypair = () => apiFetch('/dev/generate-keypair');

// DEV ONLY — signing; secret_key passed from devSigner only, never logged
export const devSign = (secretKey, message) =>
  apiFetch('/dev/sign', {
    method: 'POST',
    body: JSON.stringify({ secret_key: secretKey, message }),
  });
