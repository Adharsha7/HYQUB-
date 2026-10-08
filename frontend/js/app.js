/**
 * HYQUB Payment App — UI wiring (v4 multi-wallet).
 *
 * This module contains NO fetch() calls. All API interactions go through
 * paymentFlow.js. Strings from backend/users rendered with textContent (not innerHTML).
 *
 * Multi-wallet model:
 *  - SENDER_WALLETS list is populated in config.local.js
 *  - Each sender has its own session key in devSigner.js
 *  - Switching senders updates the displayed wallet state
 */

import { SENDER_WALLETS, RECIPIENT_PRESETS, CHAIN_ID } from './config.js';
import { getWalletState }  from './api.js';
import { sessionStatus, anySessionActive } from './devSigner.js';
import { runPayment, STEPS, PaymentError } from './paymentFlow.js';
import { parseEthToWei, weiToEthString, compareWei } from './wei.js';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const $ = (s) => document.querySelector(s);
const $$ = (s) => document.querySelectorAll(s);

const shortenAddr = (a) => (!a || a.length < 12) ? a : `${a.slice(0,8)}…${a.slice(-6)}`;

const setText = (sel, val) => { const e = $(sel); if (e) e.textContent = val ?? ''; };
const setHidden = (sel, h) => { const e = $(sel); if (e) e.hidden = h; };

function makeCopyBtn(text) {
  const b = document.createElement('button');
  b.className = 'copy-btn';
  b.textContent = 'Copy';
  b.addEventListener('click', () => {
    navigator.clipboard.writeText(text).catch(() => {});
    b.textContent = 'Copied'; b.classList.add('copied');
    setTimeout(() => { b.textContent = 'Copy'; b.classList.remove('copied'); }, 1800);
  });
  return b;
}

// ─── State ────────────────────────────────────────────────────────────────────

let selectedSenderIdx = 0;       // index into SENDER_WALLETS
let sendTarget       = '';
let sendValueWei     = '';
let sendAmountEth    = '';

// Cache of wallet states { address → state }
const walletStateCache = new Map();

const sessionHistory = [];

// ─── Session badge ────────────────────────────────────────────────────────────

function updateSessionBadge() {
  const badge = $('#session-badge');
  if (!badge) return;
  if (anySessionActive()) {
    badge.textContent = 'Session: active';
    badge.className = 'session-pill active';
  } else {
    badge.textContent = 'Session: not started';
    badge.className = 'session-pill';
  }
}
setInterval(updateSessionBadge, 2000);

// ─── Screen router ────────────────────────────────────────────────────────────

function showScreen(id) {
  $$('.screen').forEach(s => s.classList.remove('active'));
  $$('.nav-btn').forEach(b => b.classList.remove('active'));
  const s = document.getElementById('screen-' + id);
  if (s) s.classList.add('active');
  const nb = document.querySelector(`.nav-btn[data-screen="${id}"]`);
  if (nb) nb.classList.add('active');
}

// ─── Wallet state loader ──────────────────────────────────────────────────────

async function loadWalletState(address) {
  try {
    const state = await getWalletState(address);
    walletStateCache.set(address.toLowerCase(), state);
    return state;
  } catch { return null; }
}

// ─── Dashboard sender dropdown ────────────────────────────────────────────────

function initDashboardSenderDropdown() {
  const sel = $('#dashboard-sender-sel');
  if (!sel) return;
  sel.innerHTML = '';
  SENDER_WALLETS.forEach((w, i) => {
    const o = document.createElement('option');
    o.value = i;
    o.textContent = `${w.label} — ${shortenAddr(w.address)}`;
    sel.appendChild(o);
  });
  sel.value = selectedSenderIdx;
  sel.addEventListener('change', () => {
    selectedSenderIdx = parseInt(sel.value, 10);
    loadDashboard();
  });
}

async function loadDashboard() {
  const wallet = SENDER_WALLETS[selectedSenderIdx];
  if (!wallet) return;

  // Sync dropdown
  const sel = $('#dashboard-sender-sel');
  if (sel) sel.value = selectedSenderIdx;

  setText('#wallet-addr-short', shortenAddr(wallet.address));
  setText('#wallet-label', wallet.label);
  setText('#dashboard-status', 'Loading…');

  // Copy button
  const copyBtn = $('#wallet-copy-btn');
  if (copyBtn) copyBtn.onclick = () => { navigator.clipboard.writeText(wallet.address).catch(() => {}); copyBtn.textContent = 'Copied'; setTimeout(() => { copyBtn.textContent = 'Copy'; }, 1800); };

  // Session status for this wallet
  const sess = sessionStatus(wallet.address);
  const sessEl = $('#wallet-session-status');
  if (sessEl) {
    sessEl.textContent = 'Session key: ' + sess;
    sessEl.className = 'pill ' + (sess === 'active' ? 'green' : 'amber');
  }

  const state = await loadWalletState(wallet.address);
  if (!state) {
    setText('#dashboard-status', 'Could not load wallet state. Check Anvil and backend.');
    setText('#balance-eth', '—');
    setText('#balance-wei-detail', '');
    return;
  }

  setText('#balance-eth',        weiToEthString(state.balance_wei));
  setText('#balance-wei-detail', state.balance_wei + ' wei');
  setText('#stat-network',       'Anvil Local');
  setText('#stat-chain',         state.chain_id);
  setText('#stat-block',         state.block_number);
  setText('#stat-nonce',         state.nonce);
  setText('#stat-keyver',        state.key_version);
  setText('#stat-owner',         shortenAddr(state.owner));
  setText('#dashboard-status',   '');

  const regEl = $('#stat-registered');
  if (regEl) {
    regEl.innerHTML = '';
    const p = document.createElement('span');
    p.className = 'pill ' + (state.registered ? 'green' : 'red');
    p.textContent = state.registered ? 'Registered' : 'Not registered';
    regEl.appendChild(p);
  }

  renderHistory();
}

// ─── Send screen ──────────────────────────────────────────────────────────────

function initSendScreen() {
  // Sender dropdown
  const fromSel = $('#from-sel');
  if (fromSel) {
    fromSel.innerHTML = '';
    SENDER_WALLETS.forEach((w, i) => {
      const o = document.createElement('option');
      o.value = i;
      o.textContent = `${w.label} — ${shortenAddr(w.address)}`;
      fromSel.appendChild(o);
    });
    fromSel.value = selectedSenderIdx;
    fromSel.addEventListener('change', () => {
      selectedSenderIdx = parseInt(fromSel.value, 10);
      refreshSenderDetail();
    });
  }

  // Recipient dropdown
  const toSel = $('#to-sel');
  if (toSel) {
    toSel.innerHTML = '';
    const ph = document.createElement('option');
    ph.value = ''; ph.textContent = 'Select a recipient…'; ph.disabled = true; ph.selected = true;
    toSel.appendChild(ph);
    RECIPIENT_PRESETS.forEach(p => {
      const o = document.createElement('option');
      o.value = p.address;
      o.textContent = `${p.label} — ${shortenAddr(p.address)}`;
      toSel.appendChild(o);
    });
    const custom = document.createElement('option');
    custom.value = '__custom__'; custom.textContent = 'Custom address…';
    toSel.appendChild(custom);

    toSel.addEventListener('change', () => {
      if (toSel.value === '__custom__') {
        setHidden('#manual-group', false);
        sendTarget = '';
        $('#recipient-manual')?.focus();
      } else {
        setHidden('#manual-group', true);
        sendTarget = toSel.value;
      }
      clearSendError();
    });
  }

  $('#recipient-manual')?.addEventListener('input', e => {
    sendTarget = e.target.value.trim();
    clearSendError();
  });

  refreshSenderDetail();
}

async function refreshSenderDetail() {
  const wallet = SENDER_WALLETS[selectedSenderIdx];
  if (!wallet) return;

  const fromSel = $('#from-sel');
  if (fromSel) fromSel.value = selectedSenderIdx;

  const detailEl = $('#sender-detail');
  if (detailEl) {
    const addrSpan = detailEl.querySelector('.sender-addr');
    const balSpan  = detailEl.querySelector('.sender-bal');
    if (addrSpan) addrSpan.textContent = wallet.address;
    if (balSpan)  balSpan.textContent = 'Loading balance…';
  }

  const state = await loadWalletState(wallet.address);
  if (state && detailEl) {
    const balSpan = detailEl.querySelector('.sender-bal');
    if (balSpan) balSpan.textContent = `Balance: ${weiToEthString(state.balance_wei)} ETH`;
  }
}

function clearSendError() { setText('#send-error', ''); }

$('#send-form')?.addEventListener('submit', e => { e.preventDefault(); handleSendReview(); });

function handleSendReview() {
  const amountRaw = ($('#amount-input')?.value ?? '').trim();
  const sender = SENDER_WALLETS[selectedSenderIdx];

  if (!sender) { setText('#send-error', 'No sender wallet selected.'); return; }

  if (!/^0x[a-fA-F0-9]{40}$/.test(sendTarget)) {
    setText('#send-error', 'Enter a valid recipient address (0x + 40 hex characters).');
    return;
  }

  if (sender.address.toLowerCase() === sendTarget.toLowerCase()) {
    setText('#send-error', 'Sender and recipient cannot be the same wallet.');
    return;
  }

  let weiStr;
  try { weiStr = parseEthToWei(amountRaw); }
  catch (err) { setText('#send-error', err.message); return; }

  const cachedState = walletStateCache.get(sender.address.toLowerCase());
  if (cachedState && compareWei(weiStr, cachedState.balance_wei) > 0) {
    setText('#send-error', `Insufficient balance. Available: ${weiToEthString(cachedState.balance_wei)} ETH`);
    return;
  }

  sendValueWei  = weiStr;
  sendAmountEth = amountRaw;

  // Populate review
  setText('#review-from',    `${sender.label} (${shortenAddr(sender.address)})`);
  setText('#review-to',      sendTarget);
  setText('#review-to-short', shortenAddr(sendTarget));
  setText('#review-amount',  amountRaw + ' ETH');
  setText('#review-network', `Anvil Local (chain ${CHAIN_ID})`);

  clearSendError();
  showScreen('review');
}

// ─── Review ───────────────────────────────────────────────────────────────────

$('#btn-back-to-send')?.addEventListener('click', () => showScreen('send'));
$('#btn-confirm-pay')?.addEventListener('click', handleConfirmPay);

let paymentRunning = false;

async function handleConfirmPay() {
  if (paymentRunning) return;
  paymentRunning = true;
  const btn = $('#btn-confirm-pay');
  if (btn) btn.disabled = true;

  const sender = SENDER_WALLETS[selectedSenderIdx];
  const startTime = new Date().toLocaleTimeString();

  resetProgress();
  showScreen('progress');

  try {
    const result = await runPayment(
      { senderAddress: sender.address, target: sendTarget, valueWei: sendValueWei },
      (stepIdx, label) => updateProgress(stepIdx, label)
    );

    addHistory({ status: 'success', time: startTime, sender: sender.address, target: result.target, amountEth: weiToEthString(result.valueWei), txHash: result.transactionHash });
    showSuccessScreen(result, sender);
    loadDashboard().catch(() => {});
    walletStateCache.delete(sender.address.toLowerCase()); // invalidate
  } catch (err) {
    addHistory({ status: 'failed', time: startTime, sender: sender.address, target: sendTarget, amountEth: weiToEthString(sendValueWei), txHash: null });
    showFailureScreen(err);
  } finally {
    paymentRunning = false;
    if (btn) btn.disabled = false;
  }
}

// ─── Progress ─────────────────────────────────────────────────────────────────

function resetProgress() {
  const list = $('#step-list');
  if (!list) return;
  list.innerHTML = '';
  STEPS.forEach((label, i) => {
    const item = document.createElement('div');
    item.className = 'step-item'; item.id = 'step-' + i;
    const dot = document.createElement('div'); dot.className = 'step-dot'; dot.textContent = String(i + 1);
    const txt = document.createElement('div'); txt.className = 'step-text'; txt.textContent = label;
    item.append(dot, txt); list.appendChild(item);
  });
}

function updateProgress(stepIdx) {
  for (let i = 0; i < stepIdx; i++) {
    const item = document.getElementById('step-' + i);
    if (item) { item.classList.remove('active'); item.classList.add('done'); item.querySelector('.step-dot').textContent = '✓'; }
  }
  const cur = document.getElementById('step-' + stepIdx);
  if (cur) { cur.classList.add('active'); cur.classList.remove('done'); }
}

// ─── Success ──────────────────────────────────────────────────────────────────

function showSuccessScreen(result, sender) {
  setText('#success-amount',  weiToEthString(result.valueWei) + ' ETH');
  setText('#success-from',    `${sender.label} (${shortenAddr(sender.address)})`);
  setText('#success-to',      result.target);
  setText('#success-network', `Anvil Local (chain ${CHAIN_ID})`);
  const hashEl = $('#success-tx-hash');
  if (hashEl) hashEl.textContent = result.transactionHash;
  const copyWrap = $('#success-hash-copy');
  if (copyWrap) { copyWrap.innerHTML = ''; copyWrap.appendChild(makeCopyBtn(result.transactionHash)); }
  showScreen('success');
}

$('#btn-success-done')?.addEventListener('click', () => { showScreen('dashboard'); loadDashboard().catch(() => {}); });
$('#btn-success-another')?.addEventListener('click', () => showScreen('send'));

// ─── Failure ──────────────────────────────────────────────────────────────────

function showFailureScreen(err) {
  const msgEl = $('#failure-message');
  if (msgEl) {
    msgEl.innerHTML = '';
    const s = document.createElement('strong'); s.textContent = 'Payment Failed'; msgEl.appendChild(s);
    const p = document.createElement('p');
    p.textContent = err instanceof PaymentError ? err.message : 'An unexpected error occurred.';
    msgEl.appendChild(p);
  }
  showScreen('failure');
}

$('#btn-try-again')?.addEventListener('click', () => showScreen('send'));
$('#btn-failure-home')?.addEventListener('click', () => { showScreen('dashboard'); loadDashboard().catch(() => {}); });

// ─── History ──────────────────────────────────────────────────────────────────

function addHistory(entry) { sessionHistory.unshift(entry); renderHistory(); }

function renderHistory() {
  const tbody = $('#history-tbody');
  const empty = $('#history-empty');
  if (!tbody) return;
  tbody.innerHTML = '';
  if (!sessionHistory.length) { if (empty) empty.hidden = false; return; }
  if (empty) empty.hidden = true;
  for (const e of sessionHistory) {
    const tr = document.createElement('tr');
    const cells = [
      (() => { const td = document.createElement('td'); const p = document.createElement('span'); p.className = 'pill ' + (e.status === 'success' ? 'green' : 'red'); p.textContent = e.status === 'success' ? 'Success' : 'Failed'; td.appendChild(p); return td; })(),
      (() => { const td = document.createElement('td'); td.textContent = e.time; return td; })(),
      (() => { const td = document.createElement('td'); const s = document.createElement('span'); s.className = 'mono'; s.textContent = shortenAddr(e.sender); s.title = e.sender; td.appendChild(s); return td; })(),
      (() => { const td = document.createElement('td'); const s = document.createElement('span'); s.className = 'mono'; s.textContent = shortenAddr(e.target); s.title = e.target; td.appendChild(s); return td; })(),
      (() => { const td = document.createElement('td'); td.textContent = e.amountEth + ' ETH'; return td; })(),
      (() => { const td = document.createElement('td'); if (e.txHash) { const s = document.createElement('span'); s.className = 'mono'; s.textContent = shortenAddr(e.txHash); s.title = e.txHash; td.appendChild(s); } else td.textContent = '—'; return td; })(),
    ];
    cells.forEach(c => tr.appendChild(c));
    tbody.appendChild(tr);
  }
}

// ─── Nav ──────────────────────────────────────────────────────────────────────

$$('.nav-btn').forEach(btn => btn.addEventListener('click', () => {
  const t = btn.dataset.screen;
  if (!t) return;
  showScreen(t);
  if (t === 'dashboard') loadDashboard().catch(() => {});
  if (t === 'send') refreshSenderDetail().catch(() => {});
}));

$('#btn-refresh')?.addEventListener('click', () => loadDashboard().catch(() => {}));
$('#btn-go-send')?.addEventListener('click', () => showScreen('send'));

// ─── Boot ─────────────────────────────────────────────────────────────────────

initDashboardSenderDropdown();
initSendScreen();
showScreen('dashboard');
loadDashboard().catch(err => setText('#dashboard-status', 'Error: ' + err.message));
updateSessionBadge();
