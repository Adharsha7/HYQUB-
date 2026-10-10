/**
 * HYQUB UI controller.
 * Rules: no innerHTML (textContent only), no wallet addresses shown,
 * token stays in api.js memory, amounts stay strings (never floats).
 */
import * as api from './api.js';
import { parseEthToWei } from './wei.js';

const $ = (id) => document.getElementById(id);
const screens = ['auth', 'home', 'pay', 'status'];

let signupMode = false;
let currentUser = null;      // { id, name }
let recipient = null;        // { id, name }
let searchTimer = null;

function show(name) {
  for (const s of screens) $(`screen-${s}`).hidden = s !== name;
}
function setText(id, text) { $(id).textContent = text; }
function clear(el) { while (el.firstChild) el.removeChild(el.firstChild); }

// ---------- Auth ----------
function setMode(signup) {
  signupMode = signup;
  setText('auth-title', signup ? 'Create account' : 'Log in');
  setText('auth-submit', signup ? 'Create account' : 'Log in');
  setText('auth-toggle-text', signup ? 'Already registered?' : 'New here?');
  setText('auth-toggle', signup ? 'Log in' : 'Create an account');
  $('auth-password').autocomplete = signup ? 'new-password' : 'current-password';
  $('auth-hint').hidden = true;
  setText('auth-error', '');
}

$('auth-toggle').addEventListener('click', () => setMode(!signupMode));

$('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const username = $('auth-username').value.trim();
  const password = $('auth-password').value;
  setText('auth-error', '');

  if (signupMode && password.length < 8) {
    setText('auth-error', 'Use at least 8 characters for your password.');
    return;
  }

  const btn = $('auth-submit');
  btn.disabled = true;
  $('auth-hint').hidden = false;           // wallet setup can take a while
  try {
    const data = signupMode ? await api.signup(username, password)
                            : await api.login(username, password);
    currentUser = { id: data.user_id, name: data.name };
    $('auth-password').value = '';
    await goHome();
  } catch (err) {
    const msg = err.status === 409 ? 'That username is taken. Choose another one.'
              : err.status === 429 ? 'Too many attempts. Wait a minute and try again.'
              : err.message;
    setText('auth-error', msg);
  } finally {
    btn.disabled = false;
    $('auth-hint').hidden = true;
  }
});

// Session expiry: go back to login with a clear message.
api.setUnauthorizedHandler(() => {
  currentUser = null;
  setMode(false);
  show('auth');
  setText('auth-error', 'Your session expired. Log in again.');
});

$('btn-logout').addEventListener('click', async () => {
  await api.logout();
  currentUser = null;
  setMode(false);
  show('auth');
});

// ---------- Home ----------
function fmtTime(ts) {
  return new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
}

function historyItem(h) {
  const item = document.createElement('details');
  item.className = 'hist-item';

  const sum = document.createElement('summary');
  const left = document.createElement('span');
  const sent = h.direction === 'sent';
  left.textContent = `${sent ? 'Sent to' : 'Received from'} ${h.counterparty ?? 'unknown'}`;
  const right = document.createElement('span');
  right.textContent = `${sent ? '-' : '+'}${h.amount_eth} ETH`;
  right.className = sent ? '' : 'ok';
  sum.append(left, right);

  const meta = document.createElement('div');
  meta.className = 'muted';
  meta.textContent = `${fmtTime(h.created_at)} · ${h.status}`;

  const hash = document.createElement('div');
  hash.className = 'hash mono';
  hash.textContent = h.tx_hash ? `Transaction: ${h.tx_hash}` : '';

  item.append(sum, meta, hash);
  return item;
}

async function goHome() {
  setText('home-greeting', `Hi, ${currentUser.name}`);
  show('home');
  await refreshHome();
}

async function refreshHome() {
  try {
    const [me, history] = await Promise.all([api.getMe(), api.getHistory()]);
    setText('home-balance', me.balance_eth);
    const list = $('home-history');
    clear(list);
    $('home-empty').hidden = history.length > 0;
    for (const h of history) list.appendChild(historyItem(h));
  } catch (err) {
    if (err.status !== 401) setText('home-balance', '—');
  }
}

$('btn-refresh').addEventListener('click', refreshHome);
$('btn-go-pay').addEventListener('click', () => {
  recipient = null;
  $('pay-form').reset();
  clear($('pay-results'));
  setText('pay-selected', '');
  setText('pay-error', '');
  show('pay');
});

// ---------- Pay ----------
$('btn-pay-back').addEventListener('click', () => show('home'));

$('pay-search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  const q = $('pay-search').value.trim();
  const box = $('pay-results');
  if (!q) { clear(box); return; }
  searchTimer = setTimeout(async () => {
    try {
      const users = await api.searchUsers(q);
      clear(box);
      if (users.length === 0) {
        const none = document.createElement('div');
        none.className = 'muted';
        none.textContent = 'No one found with that name.';
        box.appendChild(none);
      }
      for (const u of users) {
        const b = document.createElement('button');
        b.type = 'button';
        b.className = 'btn btn-secondary pick';
        b.textContent = u.name;
        b.addEventListener('click', () => {
          recipient = { id: u.id, name: u.name };
          setText('pay-selected', `Sending to ${u.name}`);
          clear(box);
          $('pay-search').value = '';
        });
        box.appendChild(b);
      }
    } catch { /* inline errors are shown on submit */ }
  }, 250);
});

function showStatus(title, sub, { done = false, retry = false } = {}) {
  setText('status-title', title);
  setText('status-sub', sub);
  $('status-done').hidden = !done;
  $('status-retry').hidden = !retry;
  show('status');
}

$('pay-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  setText('pay-error', '');

  const amount = $('pay-amount').value.trim();
  const password = $('pay-password').value;

  if (!recipient) { setText('pay-error', 'Choose who to send to.'); return; }
  try { parseEthToWei(amount); }                 // validation only; the string is what we send
  catch { setText('pay-error', 'Enter an amount like 0.01 (up to 18 decimals).'); return; }
  if (!password) { setText('pay-error', 'Enter your password to confirm.'); return; }

  showStatus('Verifying...', 'Signing and checking your payment securely.');
  try {
    const r = await api.pay(recipient.id, amount, password);
    $('pay-password').value = '';
    showStatus('Payment successful', `${r.amount_eth} ETH sent to ${r.to}.`, { done: true });
  } catch (err) {
    $('pay-password').value = '';
    const msg = {
      WRONG_PASSWORD: 'Wrong password. Nothing was sent.',
      INSUFFICIENT_BALANCE: 'Your balance is too low for this payment.',
      LIMIT_EXCEEDED: err.message,
      RATE_LIMITED: 'Too many payments. Wait a minute and try again.',
      SELF_PAYMENT: 'You cannot send money to yourself.',
      RECIPIENT_NOT_FOUND: 'That person was not found.',
      INVALID_AMOUNT: err.message,
    }[err.code] || 'Payment failed. Nothing was sent. Please try again.';
    if (err.status === 401 && err.code !== 'WRONG_PASSWORD') return;  // session handler took over
    showStatus('Payment not sent', msg, { retry: true });
  }
});

$('status-done').addEventListener('click', async () => { show('home'); await refreshHome(); });
$('status-retry').addEventListener('click', () => show('pay'));

// ---------- Boot ----------
setMode(false);
show('auth');
