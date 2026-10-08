/**
 * HYQUB — BigInt-safe ETH / wei helpers.
 *
 * RULES:
 *  - Never use Number or parseFloat anywhere in the payment path.
 *  - value_wei is held as a validated decimal STRING end-to-end.
 *  - Never JSON.stringify an object that contains a BigInt (throws).
 *  - /submit-transaction needs value_wei as a JSON INTEGER (raw digits
 *    inserted into the body string, not via JSON.stringify).
 */

// ─── parseEthToWei ────────────────────────────────────────────────────────────
/**
 * Convert a human ETH string to a wei string.
 *
 * Accepts: digits with up to 18 decimal places, e.g. "1", "0.5", "0.000000000000000001"
 * Rejects: "0", negative, scientific notation, leading/trailing dots, >18 decimals.
 *
 * @param {string} input
 * @returns {string}  decimal wei string, e.g. "1000000000000000000"
 * @throws {Error}
 */
export function parseEthToWei(input) {
  const trimmed = (input ?? '').trim();

  if (!/^\d+(\.\d{1,18})?$/.test(trimmed)) {
    throw new Error(
      `Invalid ETH amount: ${JSON.stringify(trimmed)}. ` +
      'Use a positive decimal number with at most 18 decimal places (e.g. "0.01").'
    );
  }

  const [whole, fraction = ''] = trimmed.split('.');
  // Pad or truncate fraction to exactly 18 digits
  const paddedFraction = (fraction + '0'.repeat(18)).slice(0, 18);

  const wei = BigInt(whole) * (10n ** 18n) + BigInt(paddedFraction);

  if (wei === 0n) {
    throw new Error('Amount must be greater than zero.');
  }

  return wei.toString();
}

// ─── weiToEthString ───────────────────────────────────────────────────────────
/**
 * Convert a wei string to a human-readable ETH string.
 * Trims trailing zeros after the decimal point.
 *
 * @param {string} weiStr  decimal wei string
 * @returns {string}       e.g. "1.5", "0.001"
 */
export function weiToEthString(weiStr) {
  const wei = BigInt(weiStr);
  const whole = wei / (10n ** 18n);
  const remainder = wei % (10n ** 18n);

  if (remainder === 0n) {
    return whole.toString();
  }

  // Pad remainder to 18 digits, then trim trailing zeros
  const fracStr = remainder.toString().padStart(18, '0').replace(/0+$/, '');
  return `${whole}.${fracStr}`;
}

// ─── isValidWeiString ─────────────────────────────────────────────────────────
/**
 * Return true if s is a valid non-negative integer decimal string with no
 * leading zeros (unless the value is exactly "0").
 *
 * @param {string} s
 * @returns {boolean}
 */
export function isValidWeiString(s) {
  if (typeof s !== 'string') return false;
  // Must be all digits, no sign, no decimal, no exponent
  if (!/^\d+$/.test(s)) return false;
  // No leading zeros unless the entire string is "0"
  if (s.length > 1 && s[0] === '0') return false;
  return true;
}

// ─── compareWei ───────────────────────────────────────────────────────────────
/**
 * Compare two wei strings using BigInt.
 *
 * @param {string} a
 * @param {string} b
 * @returns {number}  -1, 0, or 1
 */
export function compareWei(a, b) {
  const ba = BigInt(a);
  const bb = BigInt(b);
  if (ba < bb) return -1;
  if (ba > bb) return 1;
  return 0;
}

// ─── buildSubmitBody ──────────────────────────────────────────────────────────
/**
 * Build the JSON body string for POST /submit-transaction manually.
 *
 * WHY MANUAL: value_wei must be a JSON integer (not a quoted string) per
 * the backend's Pydantic model. JSON.stringify({value_wei: someNumber})
 * would use lossy JS Number for large wei values (> 2^53). Using BigInt
 * would throw. So we validate the wei string and inject raw digits.
 *
 * @param {{walletAddress: string, target: string, valueWei: string, data: string, signature: string}} params
 * @returns {string}  JSON body string
 * @throws {Error}    if valueWei fails validation
 */
export function buildSubmitBody({ walletAddress, target, valueWei, data, signature }) {
  if (!isValidWeiString(valueWei)) {
    throw new Error(`buildSubmitBody: invalid wei string: ${JSON.stringify(valueWei)}`);
  }
  // valueWei is inserted as raw validated digits — not quoted, not Number-converted
  return (
    '{"wallet_address":' + JSON.stringify(walletAddress) +
    ',"target":' + JSON.stringify(target) +
    ',"value_wei":' + valueWei +          // raw validated decimal digits
    ',"data":' + JSON.stringify(data) +
    ',"ml_dsa_signature":' + JSON.stringify(signature) + '}'
  );
}
