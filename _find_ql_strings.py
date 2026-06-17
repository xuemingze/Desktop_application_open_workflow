# -*- coding: utf-8 -*-
from pathlib import Path
lines = Path('desktop_auto.py').read_text(encoding='utf-8').split('\n')
results = []
for i, line in enumerate(lines, 1):
    has_cn = False
    for c in line:
        if '\u4e00' <= c <= '\u9fff':
            has_cn = True
            break
    if has_cn:
        stripped = line.strip()
        if not stripped.startswith('#') and not stripped.startswith('"""') and not stripped.startswith('*'):
            results.append(f'L{i}: {line.rstrip()}')
Path('_ql_strings.txt').write_text('\n'.join(results), encoding='utf-8')
print(f'Found {len(results)} lines')
