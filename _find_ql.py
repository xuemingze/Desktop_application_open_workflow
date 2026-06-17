# -*- coding: utf-8 -*-
import re
from pathlib import Path
txt = Path('desktop_auto.py').read_text(encoding='utf-8')
found = set()
# Simple pattern: find strings with Chinese in UI calls
for m in re.finditer(r'"[^"]{2,200}"', txt):
    s = m.group(0)[1:-1]  # strip quotes
    if any('\u4e00' <= c <= '\u9fff' for c in s):
        # Check if it's near a UI method call
        start = max(0, m.start() - 50)
        prefix = txt[start:m.start()]
        ui_methods = ('setText', 'setPlaceholderText', 'QCheckBox', 'QGroupBox',
                      'QPushButton', 'QLabel', 'addTab', 'addItem', 'setToolTip',
                      'setSuffix', 'setCurrentText', 'itemText', 'setStatusTip')
        if any(ui in prefix for ui in ui_methods):
            found.add(s)
Path('_ql_rem.txt').write_text('\n'.join(sorted(found, key=lambda x: -len(x))), encoding='utf-8')
print(f'Found {len(found)}')
for f in sorted(found, key=lambda x: -len(x)):
    Path('_ql_rem.txt').write_text('\n'.join(sorted(found, key=lambda x: -len(x))), encoding='utf-8')
print(f'Written {len(found)} items')
