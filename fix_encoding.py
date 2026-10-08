#!/usr/bin/env python3
"""
Fix 1: Add charset meta tag explicitly and replace multi-byte Unicode with
       safe HTML entities so python3 -m http.server renders them correctly.

Fix 2: The balance display in index.html shows a raw en-dash "—" which
       the browser misreads without a declared charset. Replace all such
       characters with safe ASCII/HTML entity equivalents.
"""

import re

PATH = '/home/adharshaST/HYQUB/frontend/index.html'

with open(PATH, 'r', encoding='utf-8') as f:
    src = f.read()

# ── Fix 1: ensure charset is the very first meta tag ─────────────────────────
# It already exists — just confirm it and add Content-Type hint via http-equiv
if 'http-equiv="Content-Type"' not in src:
    src = src.replace(
        '<meta charset="UTF-8">',
        '<meta charset="UTF-8">\n  <meta http-equiv="Content-Type" content="text/html; charset=UTF-8">'
    )
    print('Added http-equiv Content-Type meta tag')

# ── Fix 2: replace Unicode characters with HTML entities / ASCII ──────────────
replacements = [
    ('\u2014', '&mdash;'),    # em dash  —
    ('\u2013', '&ndash;'),    # en dash  –
    ('\u2026', '...'),         # ellipsis …
    ('\u2192', '&rarr;'),     # →
    ('\u2190', '&larr;'),     # ←
    ('\u21bb', '&#8635;'),    # ↻ clockwise arrow
    ('\u2500', '-'),           # ─ box drawing
    ('\u2550', '='),           # ═ double box
    ('\u2554', '+'),           # ╔
    ('\u2557', '+'),           # ╗
    ('\u255a', '+'),           # ╚
    ('\u255d', '+'),           # ╝
    ('\u2551', '|'),           # ║
    ('\u2705', '&#10003;'),   # ✅ → ✓
    ('\u274c', '&times;'),    # ❌ → ×
    ('\u00a0', ' '),           # non-breaking space
    ('&amp;', '&'),            # undo double-encoding if any
]

count = 0
for uni, html in replacements:
    if uni in src:
        src = src.replace(uni, html)
        count += 1
        print(f'  Replaced U+{ord(uni):04X} ({repr(uni)}) -> {html}')

# Re-encode &amp; properly (we may have introduced plain & above from &amp;)
# but only for the Confirm & Pay button which uses &amp; correctly
# Leave HTML entities as-is

print(f'Total replacements: {count}')

with open(PATH, 'w', encoding='utf-8') as f:
    f.write(src)
print('index.html saved.')

# ── Fix 3: Also fix app.js emoji/unicode in result screen text ────────────────
APP_PATH = '/home/adharshaST/HYQUB/frontend/js/app.js'
with open(APP_PATH, 'r', encoding='utf-8') as f:
    app_src = f.read()

app_replacements = [
    ("'\\u2705'",  "'[OK]'"),      # in case emoji in JS string
    ("'\\u274c'",  "'[FAIL]'"),
    ('\u2026',     '...'),          # ellipsis in JS
    ('\u2014',     '--'),           # em dash in JS
    ('\u2013',     '-'),            # en dash in JS
    ('\u2192',     '->'),           # arrow in JS
    ('\u21bb',     'Refresh'),      # refresh arrow label
]

app_count = 0
for uni, repl in app_replacements:
    if uni in app_src:
        app_src = app_src.replace(uni, repl)
        app_count += 1
        print(f'  app.js: Replaced {repr(uni)} -> {repr(repl)}')

if app_count:
    with open(APP_PATH, 'w', encoding='utf-8') as f:
        f.write(app_src)
    print(f'app.js saved ({app_count} replacements).')
else:
    print('app.js: no changes needed.')

print('Done.')
