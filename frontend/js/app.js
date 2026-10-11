/** HYQUB UI controller. textContent only, no wallet addresses, token kept in api.js memory. */
import * as api from './api.js';
import { parseEthToWei } from './wei.js';

const $ = (id) => document.getElementById(id);
const SCREENS = ['auth', 'home', 'pay', 'status'];
let signup = false, user = null, to = null, amount = '', timer = null, hidden = false, balance = '0';

const show = (n) => SCREENS.forEach((s) => ($(`screen-${s}`).hidden = s !== n));
const txt = (id, t) => ($(id).textContent = t);
const clear = (el) => { while (el.firstChild) el.removeChild(el.firstChild); };
function el(tag, cls, text) { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; }

function toast(msg) {
  const t = $('toast'); t.textContent = msg; t.classList.add('on');
  setTimeout(() => t.classList.remove('on'), 2200);
}
function paintAvatar(node, name) {
  let h = 0; for (const c of name) h = (h * 31 + c.charCodeAt(0)) % 360;
  node.style.background = `hsl(${h} 70% 75%)`;
  node.textContent = (name[0] || '?').toUpperCase();
}
function avatar(name, lg) { const a = el('div', lg ? 'av lg' : 'av'); paintAvatar(a, name); return a; }

// ---------- Auth ----------
function setMode(s) {
  signup = s;
  $('tab-login').classList.toggle('on', !s); $('tab-signup').classList.toggle('on', s);
  txt('auth-submit', s ? 'Create account' : 'Log in'); txt('auth-error', '');
  $('auth-password').autocomplete = s ? 'new-password' : 'current-password';
}
$('tab-login').onclick = () => setMode(false);
$('tab-signup').onclick = () => setMode(true);

$('auth-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const u = $('auth-username').value.trim(), p = $('auth-password').value;
  txt('auth-error', '');
  if (signup && p.length < 8) return txt('auth-error', 'Use at least 8 characters for your password.');
  const btn = $('auth-submit'); btn.disabled = true; $('auth-hint').hidden = false;
  try {
    const d = signup ? await api.signup(u, p) : await api.login(u, p);
    user = { id: d.user_id, name: d.name }; $('auth-password').value = '';
    await goHome();
  } catch (err) {
    txt('auth-error', err.status === 409 ? 'That username is taken. Try another one.'
      : err.status === 401 ? 'Wrong username or password.'
      : err.status === 429 ? 'Too many attempts. Wait a minute and try again.' : err.message);
  } finally { btn.disabled = false; $('auth-hint').hidden = true; }
});

api.setUnauthorizedHandler(() => { user = null; setMode(false); show('auth'); txt('auth-error', 'Your session expired. Log in again.'); });
$('btn-logout').onclick = async () => { await api.logout(); user = null; setMode(false); show('auth'); };

// ---------- Home ----------
const when = (ts) => new Date(ts * 1000).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' });
function paintBalance() { txt('home-balance', hidden ? '••••' : balance); txt('btn-eye', hidden ? 'Show' : 'Hide'); }
$('btn-eye').onclick = () => { hidden = !hidden; paintBalance(); };

function histRow(h) {
  const sent = h.direction === 'sent', name = h.counterparty ?? 'Unknown';
  const row = el('div', 'item');
  const mid = el('div', 'mid');
  mid.append(el('div', 'name', `${sent ? 'To' : 'From'} ${name}`), el('div', 'dim', `${when(h.created_at)} · ${h.status}`),
    el('div', 'hash', h.tx_hash ? `Transaction ${h.tx_hash}` : ''));
  row.append(avatar(name), mid, el('div', sent ? '' : 'ok', `${sent ? '-' : '+'}${h.amount_eth}`));
  row.onclick = () => row.classList.toggle('open');
  return row;
}

async function goHome() {
  txt('home-name', user.name); paintAvatar($('home-av'), user.name);
  show('home'); await refreshHome();
}
async function refreshHome() {
  $('home-skel').hidden = false; $('home-empty').hidden = true;
  try {
    const [me, hist] = await Promise.all([api.getMe(), api.getHistory()]);
    const [w, f = ''] = me.balance_eth.split('.');
    const frac = f.slice(0, 6).replace(/0+$/, '');
    balance = frac ? `${w}.${frac}` : w;
    paintBalance();
    const list = $('home-history'); clear(list);
    hist.forEach((h) => list.append(histRow(h)));
    $('home-empty').hidden = hist.length > 0;
    const names = [...new Set(hist.filter((h) => h.direction === 'sent').map((h) => h.counterparty).filter(Boolean))].slice(0, 6);
    const box = $('contacts'); clear(box); $('contacts-wrap').hidden = names.length === 0;
    names.forEach((n) => { const b = el('button', 'contact'); b.append(avatar(n), el('span', '', n)); b.onclick = () => quickPick(n); box.append(b); });
  } catch (err) { if (err.status !== 401) toast('Could not load your account. Try Refresh.'); }
  $('home-skel').hidden = true;
}
$('btn-refresh').onclick = async () => { await refreshHome(); toast('Updated'); };

// ---------- Pay ----------
function step(n) {
  [1, 2, 3].forEach((i) => { $(`pay-step-${i}`).hidden = i !== n; $(`st${i}`).classList.toggle('on', i <= n); });
  txt('pay-error', '');
}
function openPay() { to = null; amount = ''; $('pay-search').value = ''; $('pay-amount').value = ''; $('pay-password').value = ''; clear($('pay-results')); step(1); show('pay'); $('pay-search').focus(); }
$('btn-go-pay').onclick = openPay;
$('btn-pay-back').onclick = () => { const s = [1, 2, 3].find((i) => !$(`pay-step-${i}`).hidden); s > 1 ? step(s - 1) : show('home'); };

function choose(u) {
  to = u; paintAvatar($('p2-av'), u.name); txt('p2-name', u.name); step(2); $('pay-amount').focus();
}
async function quickPick(name) {
  openPay();
  try { const m = (await api.searchUsers(name)).find((u) => u.name === name); if (m) choose(m); } catch { /* user can search */ }
}

$('pay-search').addEventListener('input', () => {
  clearTimeout(timer);
  const q = $('pay-search').value.trim(), box = $('pay-results');
  if (!q) return clear(box);
  timer = setTimeout(async () => {
    try {
      const users = await api.searchUsers(q); clear(box);
      if (!users.length) box.append(el('div', 'dim', 'No one found with that name.'));
      users.forEach((u) => {
        const r = el('div', 'item'); r.append(avatar(u.name), el('div', 'name', u.name)); r.onclick = () => choose(u); box.append(r);
      });
    } catch { /* ignore while typing */ }
  }, 250);
});

document.querySelectorAll('.chip').forEach((c) => (c.onclick = () => ($('pay-amount').value = c.dataset.amt)));

$('p2-next').onclick = () => {
  const a = $('pay-amount').value.trim();
  try { parseEthToWei(a); } catch { return txt('pay-error', 'Enter an amount like 0.01.'); }
  amount = a; txt('p3-amt', `${a} ETH`); txt('p3-name', to.name); paintAvatar($('p3-av'), to.name); step(3); $('pay-password').focus();
};

function status(kind, title, sub, done, retry) {
  const ring = $('status-ring'); ring.className = `ring ${kind}`;
  ring.textContent = kind === 'good' ? '✓' : kind === 'fail' ? '✕' : '';
  txt('status-title', title); txt('status-sub', sub);
  $('status-done').hidden = !done; $('status-retry').hidden = !retry; show('status');
}

$('pay-submit').onclick = async () => {
  const pw = $('pay-password').value;
  if (!pw) return txt('pay-error', 'Enter your password to confirm.');
  status('spin', 'Verifying...', 'Signing and checking your payment securely.');
  try {
    const r = await api.pay(to.id, amount, pw);
    status('good', 'Payment sent', `${r.amount_eth} ETH sent to ${r.to}.`, true, false);
  } catch (err) {
    if (err.status === 401 && err.code !== 'WRONG_PASSWORD') return;
    const m = { WRONG_PASSWORD: 'Wrong password. Nothing was sent.', INSUFFICIENT_BALANCE: 'Your balance is too low for this payment.',
      LIMIT_EXCEEDED: err.message, RATE_LIMITED: 'Too many payments. Wait a minute and try again.',
      SELF_PAYMENT: 'You cannot send money to yourself.', RECIPIENT_NOT_FOUND: 'That person was not found.', INVALID_AMOUNT: err.message }[err.code]
      || 'Payment failed. Nothing was sent. Please try again.';
    status('fail', 'Payment not sent', m, false, true);
  } finally { $('pay-password').value = ''; }
};
$('status-done').onclick = async () => { show('home'); await refreshHome(); };
$('status-retry').onclick = () => { show('pay'); step(3); $('pay-password').focus(); };

setMode(false); show('auth');
