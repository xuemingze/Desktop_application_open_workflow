# -*- coding: utf-8 -*-
"""Find truly visible remaining Chinese strings in context_tab.py."""
import re
from pathlib import Path

txt = Path('context_tab.py').read_text(encoding='utf-8')

# Look for setText/setPlaceholderText/addItem/QComboBox items/QLabel in code (not comments)
VISIBLE_PATTERNS = [
    r'setText\s*\(\s*"([^"]+)"',
    r'setPlaceholderText\s*\(\s*"([^"]+)"',
    r'addItem\s*\(\s*"([^"]+)"',
    r'QComboBox.*?"([^"]+)"',
]

results = set()
for pat in VISIBLE_PATTERNS:
    for m in re.finditer(pat, txt):
        g = m.group(1)
        if any('\u4e00' <= c <= '\u9fff' for c in g):
            results.add(g)

# Also find log format strings in _append_log
for m in re.finditer(r'[\[^\]]+"?[\u4e00-\u9fff][^"]*"?\]\s*\{', txt):
    start = max(0, m.start()-2)
    snippet = txt[start:m.start()+50]
    if '{' in snippet and '}' in snippet:
        # Likely a format string with Chinese
        pass  # skip complex format strings for now

# Show results sorted by length
result_list = sorted(results, key=lambda x: (-len(x), x))
Path('_remaining_vis.txt').write_text('\n'.join(result_list), encoding='utf-8')
print(f'Found {len(result_list)} visible strings')
for r in result_list:
    print(repr(r))
