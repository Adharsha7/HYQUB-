/**
 * HYQUB frontend — configuration entry point.
 *
 * The ONLY module that imports from config.local.js.
 * All other modules import from here, never from config.local.js directly.
 *
 * If config.local.js is missing, copy config.example.js to config.local.js
 * and fill in real values.
 */

export { API_BASE_URL, CHAIN_ID, SENDER_WALLETS, RECIPIENT_PRESETS }
  from './config.local.js';
