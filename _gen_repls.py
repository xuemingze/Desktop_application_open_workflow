# -*- coding: utf-8 -*-
"""Generate replacement mapping from actual file content."""
import sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('context_tab.py').read_text(encoding='utf-8')

# Find all Chinese strings in actual Python string literals
results = []
for m in re.finditer(r'''setText\s*\(\s*["\']([^"\']+?)["\']|QLabel\s*\(\s*["\']([^"\']+?)["\']|QCheckBox\s*\(\s*["\']([^"\']+?)["\']|QPushButton\s*\(\s*["\']([^"\']+?)["\']|QGroupBox\s*\(\s*["\']([^"\']+?)["\']|addTab\s*\(\s*[^,]+,\s*["\']([^"\']+?)["\']|setPlaceholderText\s*\(\s*["\']([^"\']+?)["\']|addItems\s*\(\s*\[([^\]]+)\]''', txt):
    for g in m.groups():
        if g and any('\u4e00' <= c <= '\u9fff' for c in g):
            if g not in results:
                results.append(g)

# Also find setSuffix
for m in re.finditer(r'''setSuffix\s*\(\s*["\']([^"\']+?)["\']''', txt):
    g = m.group(1)
    if g and any('\u4e00' <= c <= '\u9fff' for c in g):
        if g not in results:
            results.append(g)

# Sort by length descending (longer first to avoid partial matches)
results.sort(key=lambda x: -len(x))

# Write to file for inspection
Path('_ctx_repls_src.py').write_text('\n'.join(repr(s) for s in results), encoding='utf-8')
print(f'Found {len(results)} strings')
for r in results:
    print(repr(r))
