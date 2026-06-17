# -*- coding: utf-8 -*-
"""Patch desktop_auto.py quick launch tab with i18n."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

txt = Path('desktop_auto.py').read_text(encoding='utf-8')

# Add import at top if not present
if 'from i18n import t' not in txt:
    lines = txt.split('\n')
    insert_at = 0
    for i, line in enumerate(lines):
        if line.startswith(('from __future__', 'from ', 'import ')):
            insert_at = i + 1
    lines.insert(insert_at, 'from i18n import t')
    txt = '\n'.join(lines)
    print('Added import')

# Quick launch UI replacements
repls = [
    # Main info label
    ('QLabel("选中一个快捷方式", self)', 'QLabel(t("ql_info_selected"), self)'),
    # Radio buttons
    ('QRadioButton("🚀 直接启动 (Popen,最优先,最稳定)", self)', 'QRadioButton(t("ql_radio_direct"), self)'),
    ('QRadioButton("🖱️ 鼠标双击桌面图标 (备选)", self)', 'QRadioButton(t("ql_radio_desktop"), self)'),
    ('QRadioButton("Shell 启动 (cmd /c,特殊场景)", self)', 'QRadioButton(t("ql_radio_shell"), self)'),
    ('QRadioButton("📸 捕捉坐标点击", self)', 'QRadioButton(t("ql_radio_image"), self)'),
    # Checkbox
    ('QCheckBox("启动后模拟键鼠交互 (仅记事本生效)", self)', 'QCheckBox(t("ql_chk_notepad"), self)'),
    # Samples label
    ('QLabel("当前模板: 无", self)', 'QLabel(t("ql_template_none"), self)'),
    # Buttons
    ('QPushButton("🔄 刷新桌面", self)', 'QPushButton(t("ql_btn_refresh"), self)'),
    ('QPushButton("✂️ 截图框选为模板", self)', 'QPushButton(t("ql_btn_screenshot"), self)'),
    ('QPushButton("📂 从文件加载模板", self)', 'QPushButton(t("ql_btn_load_template"), self)'),
    ('QPushButton("▶  执行", self)', 'QPushButton(t("ql_btn_run"), self)'),
    ('QPushButton("⏹  停止", self)', 'QPushButton(t("ql_btn_stop"), self)'),
    ('QPushButton("🧹 清理残留进程", self)', 'QPushButton(t("ql_btn_cleanup"), self)'),
    # Section labels
    ('QLabel("目标信息:")', 'QLabel(t("ql_label_target") + ":")'),
    ('QLabel("图标模板 (图像模式需要,其他模式可选):")', 'QLabel(t("ql_label_template") + ":")'),
    ('QLabel("启动参数 (空格分隔,可选):")', 'QLabel(t("ql_label_args") + ":")'),
    # Group boxes
    ('QGroupBox("启动方式 (4 选 1)", quick_tab)', 'QGroupBox(t("ql_launch_mode_box"), quick_tab)'),
    ('QGroupBox("🔗 启动方式绑定 (双击/工作流 都生效)")', 'QGroupBox(t("ql_bind_box"))'),
    ('QGroupBox("🎯 坐标点击 (图像模式可选,免截图)")', 'QGroupBox(t("ql_coord_box"))'),
    ('QGroupBox("一键启停 (批量) - 已升级为工作流", quick_tab)', 'QGroupBox(t("ql_onekey_box"), quick_tab)'),
    ('QGroupBox("🧹 清理历史残留 (按进程名关键词)", quick_tab)', 'QGroupBox(t("ql_cleanup_box"), quick_tab)'),
    ('QLabel("💡 请使用下方「工作流」面板")', 'QLabel(t("ql_onekey_hint"))'),
    ('QLabel("(支持: 启动软件、截图匹配点击、按键、等待、坐标点击)")', 'QLabel(t("ql_onekey_sub"))'),
    ('QLabel("关键词:")', 'QLabel(t("ql_cleanup_label"))'),
    # Launch mode hint
    ('QLabel("未选择快捷方式", self)', 'QLabel(t("ql_info_selected"), self)'),
    # Bind buttons
    ('QPushButton("💾 绑定当前启动方式")', 'QPushButton(t("ql_btn_bind_mode"))'),
    ('QPushButton("🗑 清除绑定")', 'QPushButton(t("ql_btn_clear_bind"))'),
    # Tooltips
    ('setToolTip("把当前选择的启动方式绑定到本快捷方式。以后双击/工作流调用都会用这个 mode。")',
     'setToolTip(t("ql_bind_mode_tooltip"))'),
    ('setToolTip("清除本快捷方式的启动方式绑定,以后跟随机 UI 单选按钮")',
     'setToolTip(t("ql_clear_bind_tooltip"))'),
    # Coord area
    ('QLabel("点击:")', 'QLabel(t("ql_click_label") + ":")'),
    # Coord click type items (addItem)
    ('self.coord_click_type.addItem("双击 (默认)", "left_double")',
     'self.coord_click_type.addItem(t("ql_click_double") + " (" + t("ql_default") + ")", "left_double")'),
    ('self.coord_click_type.addItem("左键单击", "left_single")',
     'self.coord_click_type.addItem(t("ql_click_single"), "left_single")'),
    ('self.coord_click_type.addItem("右键单击", "right_single")',
     'self.coord_click_type.addItem(t("ql_click_right"), "right_single")'),
    ('QPushButton("🎯 捕捉坐标 (Win+D 后 3秒)")', 'QPushButton(t("ql_btn_capture_coord"))'),
    # coord_status setText
    ('self.coord_status.setText("按 Win+D 显示桌面...")', 'self.coord_status.setText(t("ql_coord_display_wind"))'),
    # Samples label update (setText)
    ('self.samples_label.setText("当前模板: 无")', 'self.samples_label.setText(t("ql_template_none"))'),
    # One-key section hints
    # cleanup section is already there (关键词:)
    # Item tooltip
    ('setToolTip("双击打开,如打开失败,使用快速启动")', 'setToolTip(t("ql_item_tooltip"))'),
]

for old, new in repls:
    if old in txt:
        txt = txt.replace(old, new)
        print(f'OK: {old[:50]}')
    else:
        print(f'MISS: {old[:50]}')

# Fix the _mode_name dict - these are display names shown in the UI
# Old: """: "(未绑定,跟随 UI)", ...
# New: use t() calls
old_mode_name = '            "": "(未绑定,跟随 UI)",\n            "desktop": "鼠标双击桌面图标",\n            "direct": "直接启动 (Popen)",\n            "shell": "Shell 启动 (cmd /c)",\n            "image": "图像识别 / 坐标点击",'
new_mode_name = '            "": t("ql_mode_unbound"),\n            "desktop": t("ql_mode_desktop"),\n            "direct": t("ql_mode_direct"),\n            "shell": t("ql_mode_shell"),\n            "image": t("ql_mode_image"),'
if old_mode_name in txt:
    txt = txt.replace(old_mode_name, new_mode_name)
    print('OK: _mode_name dict')
else:
    print('MISS: _mode_name dict')

# Fix lbl_launch_mode_hint setText for unbound
old_hint_unbound = 'self.lbl_launch_mode_hint.setText("未选择快捷方式")'
new_hint_unbound = 'self.lbl_launch_mode_hint.setText(t("ql_info_selected"))'
if old_hint_unbound in txt:
    txt = txt.replace(old_hint_unbound, new_hint_unbound)
    print('OK: lbl_launch_mode_hint unbound')
else:
    print('MISS: lbl_launch_mode_hint unbound')

# Fix the hint setText for bound/unbound in _refresh_shortcut_detail
old_hint_bound = 'self.lbl_launch_mode_hint.setText(f"「{sc.name}」已绑定: <b>{self._mode_name(sc.launch_mode)}</b>。<br>双击/工作流 调用时将使用该 mode，不再受 UI 单选按钮影响。")'
new_hint_bound = 'self.lbl_launch_mode_hint.setText(t("ql_launch_bound", sc=sc.name, mode=self._mode_name(sc.launch_mode)))'
# The above might not work due to HTML, let's do simpler
# Actually keep HTML-safe: just translate the static parts
old_hint_unbound2 = 'self.lbl_launch_mode_hint.setText(f"「{sc.name}」未绑定启动方式。双击/工作流 调用时使用当前 UI 选择的 mode。")'
new_hint_unbound2 = 'self.lbl_launch_mode_hint.setText(t("ql_launch_unbound", sc=sc.name))'

# Since these are format strings with HTML, let's handle them specially
# Find and replace the f-string contents
for old, new in [
    ('f"「{sc.name}」已绑定: <b>{self._mode_name(sc.launch_mode)}</b>。<br>双击/工作流 调用时将使用该 mode，不再受 UI 单选按钮影响。"',
     't("ql_launch_bound", sc=sc.name, mode=self._mode_name(sc.launch_mode))'),
    ('f"「{sc.name}」未绑定启动方式。双击/工作流 调用时使用当前 UI 选择的 mode。"',
     't("ql_launch_unbound", sc=sc.name)'),
]:
    if old in txt:
        txt = txt.replace(old, new)
        print(f'OK: hint format string')
    else:
        print(f'MISS: hint format string')

Path('desktop_auto.py').write_text(txt, encoding='utf-8')
print('Saved desktop_auto.py')
