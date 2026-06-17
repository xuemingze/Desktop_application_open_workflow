# -*- coding: utf-8 -*-
"""Find visible Chinese strings in source files."""
import re
from pathlib import Path

def visible_strings(txt):
    results = []
    lines = txt.split('\n')
    # Match string literals containing Chinese
    # Skip comment-only lines
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if stripped.startswith('#') or stripped.startswith('"""') or stripped.startswith("'''"):
            continue
        # Find string literals
        for m in re.finditer(r'''(['"])(?=.*[\u4e00-\u9fff])\1''', line):
            s = line[m.start():m.end()]
            if len(s) > 100:
                s = s[:100] + '...'
            results.append(f'L{i}: {s}')
    return results

for fname in ['context_tab.py', 'desktop_auto.py']:
    txt = Path(fname).read_text(encoding='utf-8')
    visible = visible_strings(txt)
    Path(f'_vis_{fname}.txt').write_text('\n'.join(visible), encoding='utf-8')
    print(f'{fname}: {len(visible)} visible strings')
