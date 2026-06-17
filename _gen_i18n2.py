# -*- coding: utf-8 -*-
"""Add new i18n keys + patch context_tab.py desktop_auto.py."""
import sys, re
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

NEW_KEYS = {
    # Context tab
    "ctx_sensor_box": ("传感器（多选）", "Sensors (multi-select)"),
    "ctx_chk_clipboard": ("📋 剪贴板监听（推荐开启，零开销）", "📋 Clipboard monitor (recommended, zero overhead)"),
    "ctx_chk_window": ("🪟 前台窗口切换监听", "🪟 Foreground window switch monitor"),
    "ctx_chk_file": ("📁 文件系统监视（手动添加目录）", "📁 File system monitor (add dirs manually)"),
    "ctx_chk_process": ("⚙️ 进程启动/退出监听（配合主动嗅探用户档案触发）", "⚙️ Process start/exit monitor (triggers proactive profile)"),
    "ctx_file_watch_path": ("文件监视路径", "File watch paths"),
    "ctx_btn_add_dir": ("➕ 添加目录", "➕ Add Directory"),
    "ctx_btn_rm_dir": ("➖ 移除选中", "➖ Remove Selected"),
    "ctx_btn_test_clipboard": ("🧪 测试剪贴板捕获", "🧪 Test Clipboard Capture"),
    "ctx_btn_test_toast": ("💬 测试气泡", "💬 Test Toast"),
    "ctx_btn_clear_toasts": ("🧹 清除所有气泡", "🧹 Clear All Toasts"),
    "ctx_clipboard_hint": ("💡 只有当剪贴板内容命中下方任一规则时，才会被发送到 AI 推理。\n取消勾选可禁用对应规则。", "💡 Only clipboard content matching a rule below will be sent to AI.\nUncheck to disable a rule."),
    "ctx_learning_settings": ("学习规则设置", "Learning Rules Settings"),
    "ctx_default_trans_lang": ("默认翻译语言:", "Default translation language:"),
    "ctx_rule_tip": ("勾选规则后：检测到英文 → 推送 AI 翻译；检测到学术词汇 → 推送 AI 解释。", "After enabling: English → AI translation; academic terms → AI explanation."),
    "ctx_rule_tip_label": ("说明:", "Note:"),
    "ctx_custom_rule": ("添加自定义规则", "Add Custom Rule"),
    "ctx_rule_name": ("名称:", "Name:"),
    "ctx_rule_pattern": ("正则:", "Pattern:"),
    "ctx_btn_add_rule": ("➕ 添加", "➕ Add"),
    "ctx_btn_rm_rule": ("➖ 删除选中", "➖ Remove Selected"),
    "ctx_blacklist_hint": ("🛡️ 黑名单中的进程绝对不会被感知（剪贴板内容不会进入 AI 链路）。\n密码管理器、SSH 私钥工具等建议加入。", "🛡️ Blacklisted processes are never sensed.\nPassword managers, SSH keys, etc. recommended."),
    "ctx_add_process": ("添加进程", "Add Process"),
    "ctx_backend_title": ("AI 后端", "AI Backend"),
    "ctx_btn_save_backend": ("💾 保存设置", "💾 Save Settings"),
    "ctx_btn_test_conn": ("🔌 测试连接", "🔌 Test Connection"),
    "ctx_log_box": ("📊 AI 感知活动日志", "📊 AI Awareness Activity Log"),
    "ctx_proactive_hint": ("💡 开启后，进程事件会按「主动嗅探档案」规则触发 AI 分析。\n需要同时开启上方「进程监听」复选框。", "💡 When enabled, process events trigger AI analysis per proactive rules.\nRequires enabling 'Process monitor' above."),
    "ctx_master_on": ("🟢 已启用", "🟢 Enabled"),
    "ctx_master_off": ("🔴 已停用", "🔴 Disabled"),

    # Quick launch (desktop_auto.py)
    "ql_info_selected": ("选中一个快捷方式", "Select a shortcut"),
    "ql_radio_direct": ("🚀 直接启动 (Popen,最优先,最稳定)", "🚀 Direct Launch (Popen, fastest, most stable)"),
    "ql_radio_desktop": ("🖱️ 鼠标双击桌面图标 (备选)", "🖱️ Double-click Desktop Icon (fallback)"),
    "ql_radio_shell": ("⚙️ Shell 启动 (cmd /c,特殊场景)", "⚙️ Shell Launch (cmd /c, special cases)"),
    "ql_radio_image": ("📸 捕捉坐标点击", "📸 Image Match / Coord Click"),
    "ql_chk_notepad": ("启动后模拟键鼠交互 (仅记事本生效)", "Simulate keyboard/mouse after launch (notepad only)"),
    "ql_chk_show_desktop": ("执行前先显示桌面 (Win+D)", "Show desktop before execution (Win+D)"),
    "ql_btn_bind_mode": ("💾 绑定当前启动方式", "💾 Bind Current Launch Mode"),
    "ql_btn_clear_bind": ("🗑 清除绑定", "🗑 Clear Binding"),
    "ql_coord_status": ("📍 坐标状态:"),
    "ql_coord_not_set": ("未设置", "Not set"),
    "ql_search_placeholder": ("🔍 搜索快捷方式...", "🔍 Search shortcuts..."),
    "ql_btn_refresh": ("🔄 刷新列表", "🔄 Refresh List"),
    "ql_btn_add_custom": ("➕ 添加自定义", "➕ Add Custom"),
    "ql_btn_show_desktop": ("🗄 Win+D", "🗄 Win+D"),
    "ql_label_log": ("📜 操作日志", "📜 Activity Log"),
    "ql_no_target": ("(未选中)", "(none selected)"),
    "ql_no_template": ("未设置", "Not set"),
    "ql_click_double": ("双击", "Double"),
    "ql_click_single": ("单击", "Single"),
    "ql_click_right": ("右击", "Right"),

    # Search panel
    "sp_title_settings": ("🔧 文件搜索 - 设置向导", "🔧 File Search - Settings Wizard"),
    "sp_btn_prev": ("← 上一步", "← Previous"),
    "sp_btn_next": ("下一步 →", "Next →"),
    "sp_btn_cancel": ("取消", "Cancel"),
    "sp_step_label": ("第 {n}/{total} 步", "Step {n}/{total}"),
    "sp_btn_test": ("🔌 测试连接", "🔌 Test Connection"),
    "sp_step1_title": ("第 1 步: 找到 Everything", "Step 1: Locate Everything"),
    "sp_step1_desc": ("Everything 是 Windows 上最快的文件搜索工具 (基于 NTFS MFT)。\n本程序需要 Everything 提供搜索能力。", "Everything is the fastest Windows file search tool (NTFS MFT-based).\nThis program needs Everything for search capability."),
    "sp_detect_scanning": ("🔍 正在自动扫描常见位置...", "🔍 Scanning common locations..."),
    "sp_detect_found": ("✅ 已找到: {exe}", "✅ Found: {exe}"),
    "sp_detect_selected": ("✅ 已选择: {path}", "✅ Selected: {path}"),
    "sp_detect_not_found": ("❌ 未找到", "❌ Not found"),
    "sp_exe_path_label": ("Everything.exe 路径:", "Everything.exe path:"),
    "sp_btn_browse": ("📂 浏览...", "📂 Browse..."),
    "sp_btn_rescan": ("🔄 重新扫描", "🔄 Rescan"),
    "sp_not_found_q": ("❓ 没找到 Everything?", "❓ Everything not found?"),
    "sp_btn_download": ("📥 下载 Everything 1.5+ (官方地址)", "📥 Download Everything 1.5+ (official site)"),
    "sp_btn_voidtools": ("🌐 打开 voidtools 官网", "🌐 Open voidtools website"),
    "sp_hint_install": ("💡 提示: 安装 Everything 时,建议勾选 \"安装为服务\" 以便后台常驻", "💡 Tip: During install, check 'Install as service' to keep Everything running"),
    "sp_step2_title": ("第 2 步: 启动 Everything 并启用 HTTP 服务", "Step 2: Start Everything and Enable HTTP Server"),
    "sp_proc_status": ("进程状态: 检测中...", "Process status: Detecting..."),
    "sp_proc_running": ("进程状态: ✅ 运行中 (PID={pid})", "Process status: ✅ Running (PID={pid})"),
    "sp_proc_stopped": ("进程状态: ❌ 未运行", "Process status: ❌ Not running"),
    "sp_btn_start_everything": ("▶️ 启动 Everything (服务模式)", "▶️ Start Everything (service mode)"),
    "sp_port_label": ("HTTP 端口 16259: 检测中...", "HTTP port 16259: Detecting..."),
    "sp_port_ready": ("HTTP 端口 16259: ✅ 已就绪", "HTTP port 16259: ✅ Ready"),
    "sp_manual_http": ("📋 手动启用 HTTP Server (如果上面按钮无效)", "📋 Manually Enable HTTP Server (if button above doesn't work)"),
    "sp_manual_steps": ("1. 双击 Everything.exe 打开主窗口\n2. 菜单 → 工具 → 选项 → 切到 [HTTP Server] 标签\n3. ✅ 勾选 \"启用 HTTP server\"\n4. 端口保持默认 16259\n5. 点 [确定] 保存\n6. 回到这里点 [下一步]", "1. Double-click Everything.exe\n2. Menu → Tools → Options → [HTTP Server]\n3. ✅ Check 'Enable HTTP server'\n4. Keep port 16259\n5. Click [OK]\n6. Come back and click [Next]"),
    "sp_btn_reecheck": ("🔄 重新检测", "🔄 Recheck"),
    "sp_step3_title": ("第 3 步: 选择鉴权模式", "Step 3: Choose Authentication Mode"),
    "sp_auth_none": ("无密码 (本地单机推荐)", "No password (local single user)"),
    "sp_auth_password": ("有密码 (多人共用电脑推荐)", "With password (shared computer)"),
    "sp_auth_box": ("🔐 HTTP 账号密码", "🔐 HTTP Account Password"),
    "sp_username": ("用户名:", "Username:"),
    "sp_password": ("密码:", "Password:"),
    "sp_credential_hint": ("💡 凭据会用 Windows DPAPI 加密保存,只有你的账户能解开", "💡 Credentials encrypted with Windows DPAPI, only your account can decrypt"),
    "sp_btn_save_cred": ("💾 保存凭据", "💾 Save Credentials"),
    "sp_btn_skip_auth": ("跳过 (无密码)", "Skip (no password)"),
    "sp_step4_title": ("第 4 步: 完成!", "Step 4: Done!"),
    "sp_all_set": ("🎉 所有设置完成!", "🎉 All settings complete!"),
    "sp_save_close": ("💾 保存并关闭", "💾 Save and Close"),
    "sp_connection_success": ("连接成功,索引内有 {n} 个文件", "Connection success, {n} files indexed"),
    "sp_connection_auth_fail": ("需要鉴权 (401)", "Authentication required (401)"),
    "sp_connection_fail": ("无法连接: {reason}", "Cannot connect: {reason}"),
    "sp_detecting": ("检测中...", "Detecting..."),
    "sp_not_installed": ("❌ 未安装", "❌ Not installed"),
    "sp_running": ("✅ 运行中", "✅ Running"),
    "sp_not_running": ("❌ 未运行", "❌ Not running"),
    "sp_port_open": ("✅ 端口开放", "✅ Port open"),
    "sp_port_closed": ("❌ 端口未开", "❌ Port closed"),
}


def add_keys_to_i18n(new_keys):
    txt = Path('i18n.py').read_text(encoding='utf-8')
    
    for key, (zh, en) in sorted(new_keys.items()):
        zh_line = f'    {key!r}: {zh!r},\n'
        en_line = f'    {key!r}: {en!r},\n'
        
        if f'{key!r}:' in txt:
            print(f'EXISTS: {key}')
            continue
        
        # Find end of _STRINGS_ZH dict (the line with "}")
        zh_end = txt.find('_STRINGS_ZH: dict[str, str] = {')
        if zh_end < 0:
            print(f'ERROR: _STRINGS_ZH not found')
            return
        # Find the closing } of this dict
        zh brace_start = txt.find('}', zh_end)
        if zh brace_start < 0:
            print(f'ERROR: ZH dict closing brace not found for {key}')
            continue
        
        # Insert ZH entry before the closing }
        txt = txt[:zh_brace_start] + zh_line + txt[zh_brace_start:]
        
        # Now find _STRINGS_EN and insert EN entry
        en_end = txt.find('_STRINGS_EN: dict[str, str] = {')
        if en_end < 0:
            print(f'ERROR: _STRINGS_EN not found')
            return
        en_brace_start = txt.find('}', en_end)
        if en_brace_start < 0:
            print(f'ERROR: EN dict closing brace not found for {key}')
            continue
        
        txt = txt[:en_brace_start] + en_line + txt[en_brace_start:]
        print(f'ADDED: {key}')
    
    Path('i18n.py').write_text(txt, encoding='utf-8')
    print(f'Done: {len(new_keys)} keys')


def patch_context_tab():
    txt = Path('context_tab.py').read_text(encoding='utf-8')
    changes = []
    
    def rep(old, new):
        nonlocal txt
        if old in txt:
            txt = txt.replace(old, new)
            changes.append(f'OK: {old[:50]!r}')
        else:
            changes.append(f'MISS: {old[:50]!r}')
    
    # Add global import if needed
    if 'from i18n import t' not in txt[:2000]:
        idx = txt.find('from PySide')
        if idx >= 0:
            end = txt.find('\n', idx)
            txt = txt[:end+1] + '\nfrom i18n import t\n' + txt[end+1:]
            changes.append('Added global i18n import')
    
    # Master switch
    rep('self.master_switch = QCheckBox("🟢 启用上下文感知")',
        'self.master_switch = QCheckBox(t("ai_chk_enabled"))')
    
    # Sensor panel
    rep('gb = QGroupBox("传感器（多选）")', 'gb = QGroupBox(t("ctx_sensor_box"))')
    rep('self.chk_clipboard = QCheckBox("📋 剪贴板监听（推荐开启，零开销）")',
        'self.chk_clipboard = QCheckBox(t("ctx_chk_clipboard"))')
    rep('self.chk_window = QCheckBox("🪟 前台窗口切换监听")',
        'self.chk_window = QCheckBox(t("ctx_chk_window"))')
    rep('self.chk_file = QCheckBox("📁 文件系统监视（手动添加目录）")',
        'self.chk_file = QCheckBox(t("ctx_chk_file"))')
    rep('self.chk_process = QCheckBox("⚙️ 进程启动/退出监听（配合主动嗅探用户档案触发）")',
        'self.chk_process = QCheckBox(t("ctx_chk_process"))')
    rep('path_gb = QGroupBox("文件监视路径")', 'path_gb = QGroupBox(t("ctx_file_watch_path"))')
    rep('btn_add = QPushButton("➕ 添加目录")', 'btn_add = QPushButton(t("ctx_btn_add_dir"))')
    rep('btn_rm = QPushButton("➖ 移除选中")', 'btn_rm = QPushButton(t("ctx_btn_rm_dir"))')
    rep('btn_test = QPushButton("🧪 测试剪贴板捕获")', 'btn_test = QPushButton(t("ctx_btn_test_clipboard"))')
    rep('btn_test_toast = QPushButton("💬 测试气泡")', 'btn_test_toast = QPushButton(t("ctx_btn_test_toast"))')
    rep('btn_clear_toasts = QPushButton("🧹 清除所有气泡")', 'btn_clear_toasts = QPushButton(t("ctx_btn_clear_toasts"))')
    rep('info = QLabel("💡 只有当剪贴板内容命中下方任一规则时，才会被发送到 AI 推理。\n取消勾选可禁用对应规则。")',
        'info = QLabel(t("ctx_clipboard_hint"))')
    
    # Learning rules
    rep('learning_gb = QGroupBox("学习规则设置")', 'learning_gb = QGroupBox(t("ctx_learning_settings"))')
    rep('lf.addRow("默认翻译语言:", self.default_translate_lang_input)',
        'lf.addRow(t("ctx_default_trans_lang"), self.default_translate_lang_input)')
    rep('tip = QLabel("勾选规则后：检测到英文 → 推送 AI 翻译；检测到学术词汇 → 推送 AI 解释。")',
        'tip = QLabel(t("ctx_rule_tip"))')
    rep('lf.addRow("说明:", tip)', 'lf.addRow(t("ctx_rule_tip_label"), tip)')
    rep('custom_gb = QGroupBox("添加自定义规则")', 'custom_gb = QGroupBox(t("ctx_custom_rule"))')
    rep('cv.addRow("名称:", self.rule_name_input)', 'cv.addRow(t("ctx_rule_name"), self.rule_name_input)')
    rep('cv.addRow("正则:", self.rule_pattern_input)', 'cv.addRow(t("ctx_rule_pattern"), self.rule_pattern_input)')
    rep('btn_add = QPushButton("➕ 添加")', 'btn_add = QPushButton(t("ctx_btn_add_rule"))')
    rep('btn_rm = QPushButton("➖ 删除选中")', 'btn_rm = QPushButton(t("ctx_btn_rm_rule"))')
    
    # Blacklist
    rep('warn = QLabel("🛡️ 黑名单中的进程绝对不会被感知（剪贴板内容不会进入 AI 链路）。\n密码管理器、SSH 私钥工具等建议加入。")',
        'warn = QLabel(t("ctx_blacklist_hint"))')
    rep('add_gb = QGroupBox("添加进程")', 'add_gb = QGroupBox(t("ctx_add_process"))')
    
    # Backend
    rep('gb = QGroupBox("AI 后端")', 'gb = QGroupBox(t("ctx_backend_title"))')
    rep('btn_save = QPushButton("💾 保存设置")', 'btn_save = QPushButton(t("ctx_btn_save_backend"))')
    rep('btn_test = QPushButton("🔌 测试连接")', 'btn_test = QPushButton(t("ctx_btn_test_conn"))')
    
    # Proactive
    rep('gb = QGroupBox("🎯 主动嗅探 - 有进程启动/退出时，按规则触发档案匹配")',
        'gb = QGroupBox(t("tab_proactive_sniff"))')
    rep('hint = QLabel("💡 开启后，进程事件会按「主动嗅探档案」规则触发 AI 分析。\n需要同时开启上方「进程监听」复选框。")',
        'hint = QLabel(t("ctx_proactive_hint"))')
    
    # Log
    rep('gb = QGroupBox("📊 AI 感知活动日志")', 'gb = QGroupBox(t("ctx_log_box"))')
    rep('btn_clear = QPushButton("🧹 清空日志")', 'btn_clear = QPushButton(t("ai_btn_clear_log"))')
    
    Path('context_tab.py').write_text(txt, encoding='utf-8')
    for c in changes:
        print(c)
    print(f'context_tab: {sum(1 for c in changes if c.startswith("OK"))} OK, {sum(1 for c in changes if c.startswith("MISS"))} MISS')


def patch_desktop_auto():
    txt = Path('desktop_auto.py').read_text(encoding='utf-8')
    changes = []
    
    def rep(old, new):
        nonlocal txt
        if old in txt:
            txt = txt.replace(old, new)
            changes.append(f'OK: {old[:50]!r}')
        else:
            changes.append(f'MISS: {old[:50]!r}')
    
    rep('self.info_label = QLabel("选中一个快捷方式", self)',
        'self.info_label = QLabel(t("ql_info_selected"), self)')
    rep('self.radio_direct = QRadioButton("🚀 直接启动 (Popen,最优先,最稳定)", self)',
        'self.radio_direct = QRadioButton(t("ql_radio_direct"), self)')
    rep('self.radio_desktop = QRadioButton("🖱️ 鼠标双击桌面图标 (备选)", self)',
        'self.radio_desktop = QRadioButton(t("ql_radio_desktop"), self)')
    rep('self.radio_shellexec = QRadioButton("⚙️ Shell 启动 (cmd /c,特殊场景)", self)',
        'self.radio_shellexec = QRadioButton(t("ql_radio_shell"), self)')
    rep('self.radio_image = QRadioButton("📸 捕捉坐标点击", self)',
        'self.radio_image = QRadioButton(t("ql_radio_image"), self)')
    rep('self.chk_notepad = QCheckBox("启动后模拟键鼠交互 (仅记事本生效)", self)',
        'self.chk_notepad = QCheckBox(t("ql_chk_notepad"), self)')
    rep('self.chk_show_desktop = QCheckBox("执行前先显示桌面 (Win+D)", self)',
        'self.chk_show_desktop = QCheckBox(t("ql_chk_show_desktop"), self)')
    
    Path('desktop_auto.py').write_text(txt, encoding='utf-8')
    for c in changes:
        print(c)
    print(f'desktop_auto: {sum(1 for c in changes if c.startswith("OK"))} OK, {sum(1 for c in changes if c.startswith("MISS"))} MISS')


def main():
    print('=== Adding i18n keys ===')
    add_keys_to_i18n(NEW_KEYS)
    print('\n=== Patching context_tab ===')
    patch_context_tab()
    print('\n=== Patching desktop_auto ===')
    patch_desktop_auto()
    print('\n=== All done ===')

if __name__ == '__main__':
    main()
