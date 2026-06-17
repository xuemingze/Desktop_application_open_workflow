# -*- coding: utf-8 -*-
import re
from pathlib import Path
txt = Path('context_tab.py').read_text(encoding='utf-8')
# Find Chinese in setText / setPlaceholderText / addItem calls
found = []
for m in re.finditer(r'(?:setText|setPlaceholderText|addItem)\s*\(\s*"([^"]+)"', txt):
    s = m.group(1)
    if any('\u4e00' <= c <= '\u9fff' for c in s):
        found.append(s)
# combo items
for m in re.finditer(r'addItems\s*\(\s*\[([^\]]+)\]', txt):
    items_str = m.group(1)
    for m2 in re.finditer(r'"([^"]+)"', items_str):
        s = m2.group(1)
        if any('\u4e00' <= c <= '\u9fff' for c in s):
            found.append(s)
# QComboBox items
for m in re.finditer(r'QComboBox\s*\([^)]*["\']([^"\']+?)["\']', txt):
    s = m.group(1)
    if any('\u4e00' <= c <= '\u9fff' for c in s):
        found.append(s)
# Sort unique
seen = []
for f in found:
    if f not in seen:
        seen.append(f)
# Write raw bytes
out = '\n'.join(seen)
Path('_vis3.txt').write_text(out, encoding='utf-8')
# Also write repr version for debugging
Path('_vis3_repr.txt').write_text('\n'.join(repr(s) for s in seen), encoding='utf-8')
print(f'Found {len(seen)}')
