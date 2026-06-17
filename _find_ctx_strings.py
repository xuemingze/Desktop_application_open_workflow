# -*- coding: utf-8 -*-
import re
from pathlib import Path

txt = Path('context_tab.py').read_text(encoding='utf-8')
strings = set()
for m in re.finditer(r'"[^"]*[\u4e00-\u9fff][^"]*"', txt):
    s = m.group()
    if len(s) > 200:
        continue
    strings.add(s)

Path('_ctx_strings.txt').write_text('\n'.join(sorted(strings, key=lambda x: (-len(x), x))), encoding='utf-8')
print(f'Found {len(strings)} unique strings')
for s in sorted(strings):
    print(repr(s))
