# -*- coding: utf-8 -*-
from pathlib import Path
txt = Path('i18n.py').read_text(encoding='utf-8')
zh = '    "ql_mode_unbound": "(\u672a\u7ed1\u5b9a,\u8ddf\u968f UI)",\n'
en = '    "ql_mode_unbound": "(unbound, follows UI)",\n'
if '"ql_mode_unbound":' in txt:
    print('Already exists')
else:
    zh_start = txt.find('_STRINGS_ZH: dict[str, str] = {')
    en_start = txt.find('_STRINGS_EN: dict[str, str] = {')
    zh_section = txt[zh_start:en_start]
    zh_end = zh_start + zh_section.rfind('}')
    txt = txt[:zh_end] + zh + txt[zh_end:]
    en_section = txt[en_start:]
    en_end = en_start + en_section.rfind('}')
    txt = txt[:en_end] + en + txt[en_end:]
    Path('i18n.py').write_text(txt, encoding='utf-8')
    print('Added ql_mode_unbound')
