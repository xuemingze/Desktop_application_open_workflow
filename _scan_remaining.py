# -*- coding: utf-8 -*-
import sys, re, os
sys.stdout.reconfigure(encoding='utf-8')

GUI_FILES = ['desktop_auto.py', 'tools_tab.py', 'workflow_panel.py', 'context_tab.py', 'search_panel.py']
SKIP_FILES = {'tools_tab.py', 'workflow_panel.py'}
SKIP_PATTERNS = ['#', '"""', "'''", 'log.', 'log_signal', 'print(',
                  'from i18n', 't("', 't (', '_t ', '.setText(t', 'QMessageBox',
                  'getLogger', 'except Exception', 'signal.emit']

for fname in GUI_FILES:
    if not os.path.exists(fname):
        continue
    if fname in SKIP_FILES:
        print(f'\n=== {fname} === (SKIPPED)')
        continue
    print(f'\n=== {fname} ===')
    with open(fname, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    found = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if any(p in s for p in SKIP_PATTERNS):
            continue
        if re.search(r'[\u4e00-\u9fff]', line):
            if len(s) > 150:
                continue
            found.append(f'  {i}: {s[:120]}')
    if found:
        for f in found[:50]:
            print(f)
        if len(found) > 50:
            print(f'  ... and {len(found)-50} more')
    else:
        print('  (clean)')
