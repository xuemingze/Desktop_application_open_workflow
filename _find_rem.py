# -*- coding: utf-8 -*-
"""Find remaining Chinese strings in context_tab.py."""
import re
from pathlib import Path

txt = Path('context_tab.py').read_text(encoding='utf-8')
# Find all string literals containing Chinese (between double or single quotes)
results = []
for m in re.finditer(r'"([^"\\n]*)"', txt):
    s = m.group(1)
    if any('\u4e00' <= c <= '\u9fff' for c in s) and len(s) > 1:
        results.append(s)

# Deduplicate and sort
seen = set()
unique = []
for r in results:
    if r not in seen:
        seen.add(r)
        unique.append(r)

unique.sort(key=lambda x: -len(x))
Path('_remaining_ctx.txt').write_text('\n'.join(repr(s) for s in unique), encoding='utf-8')
print(f'Found {len(unique)} unique strings')
for u in unique:
    print(repr(u))
