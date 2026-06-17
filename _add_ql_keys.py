# -*- coding: utf-8 -*-
"""Add missing i18n keys for context_tab and desktop_auto, then patch desktop_auto."""
import sys
from pathlib import Path
sys.stdout.reconfigure(encoding='utf-8')

# Step 1: Add missing keys to i18n.py
i18n_txt = Path('i18n.py').read_text(encoding='utf-8')

NEW_KEYS = [
    # context_tab dynamic/log strings
    ("ctx_placeholder_hobbies", "\u4f8b\u5982\uff1a\u5c71\u4e0a\u3001\u6444\u5f71\u3001\u68a6\u6885", "e.g. hiking, photography, weiqi"),
    ("ctx_placeholder_interests", "\u4f8b\u5982\uff1aAI\u3001\u52a0\u5bc6\u8d27\u5e01\u3001\u72ec\u7acb\u6e38\u620f", "e.g. AI, crypto, indie games"),
    ("ctx_placeholder_learning", "\u4f8b\u5982\uff1aRust \u7f16\u7a0b\u3001\u7cfb\u7edf\u8bbe\u8ba1", "e.g. Rust, system design"),
    ("ctx_placeholder_work", "\u4f8b\u5982\uff1a\u684c\u9762\u81ea\u52a8\u5316\u3001Python \u540e\u7aef", "e.g. desktop automation, Python backend"),
    ("ctx_placeholder_keywords", "\u4f8b\u5982\uff1a\u9e23\u6f6e,\u539f\u795e,\u5d29\u574f\u661f\u7a57\u94c1\u9053", "e.g. game names, topics"),
    ("ctx_placeholder_trans_lang", "\u4f8b\u5982\uff1a\u4e2d\u6587 \/ English \/ \u65e5\u672c\u8a9e", "e.g. Chinese / English / Japanese"),
    ("ctx_placeholder_rule_name", "\u89c4\u5219\u540d\u79f0\uff0c\u5982 Git \u4ed3\u5e93\u8def\u5f84", "Rule name, e.g. Git repo path"),
    ("ctx_placeholder_pattern", "\u6b63\u5219\u8868\u8fbe\u5f0f\uff0c\u5982 ^git@", "Regex, e.g. ^git@"),
    ("ctx_placeholder_process", "\u8fdb\u7a0b\u540d\uff0c\u5982 1Password.exe", "Process name, e.g. 1Password.exe"),
    ("ctx_placeholder_tavily", "\u53ef\u9009\uff1aTavily API Key\uff0c\u8054\u7f51\u641c\u7d22\u4f18\u5148\u4f7f\u7528 Tavily", "Optional: Tavily API Key"),
    ("ctx_base_url", "Base URL:", "Base URL:"),
    ("ctx_api_key", "API Key:", "API Key:"),
    ("ctx_model", "Model:", "Model:"),
    ("ctx_timeout", "\u8d85\u65f6:", "Timeout:"),
    ("ctx_tavily_key", "Tavily Key:", "Tavily Key:"),
    ("ctx_ip_address", "IP \u5730\u5740", "IP Address"),
    ("ctx_nginx_config", "Nginx \u914d\u7f6e", "Nginx Config"),
    ("ctx_backend_echo", "EchoBackend (\u672c\u5730\u6d4b\u8bd5\uff0c\u4e0d\u53d1\u8bf7\u6c42)", "EchoBackend (local test, no requests)"),
    ("ctx_backend_openai", "OpenAI \u5171\u5bb9 (Hermes\/Qianlia\/\u672c\u5730\u6a21\u578b)", "OpenAI Compatible (Hermes/Qianlia/local)"),
    ("ctx_workflow_info", "\u2022 \u6c14\u6ce1\u70b9\u51fb\u540e\u4f1a\u8c03\u7528 AI \u63a8\u8350\u7684\u5de5\u5177\uff08MCP \u5de5\u5177\u6216\u5de5\u4f5c\u6d41\uff09\n\u2022 \u5f53\u524d\u652f\u6301\u7684\u5de5\u5177\uff1asearch_local_files \/ run_workflow \/ launch_shortcut\n\u2022 \u63a8\u8350\u5de5\u4f5c\u6d41\u9700\u8981\u5148\u5728\u300c\u5de5\u4f5c\u6d41\u300d\u6807\u7b7e\u9875\u521b\u5efa\n\u2022 \u6574\u4e2a\u8fc7\u7a0b\u53ef\u5728\u300c\u65e5\u5fd7\u300d\u6807\u7b7e\u9875\u67e5\u770b\u5b9e\u65f6\u6d3b\u52a8", "Tools recommended via bubbles. search_local_files / run_workflow / launch_shortcut available."),
    # Quick launch (desktop_auto.py)
    ("ql_coord_box", "\ud83d\udcaf \u5750\u6807\u70b9\u51fb (\u56fe\u50cf\u6a21\u5f0f\u53ef\u9009,\u514d\u622a\u56fe)", "Image Match Click (optional, no screenshot needed)"),
    ("ql_info_no_selection", "\u672a\u9009\u4e2d\u5feb\u6377\u65b9\u5f0f", "No shortcut selected"),
    ("ql_onekey_hint", "\ud83d\udca1 \u8bf7\u4f7f\u7528\u4e0b\u65b9\u300c\u5de5\u4f5c\u6d41\u300d\u9762\u677f", "Please use the Workflow panel below"),
    ("ql_onekey_sub", "(\u652f\u6301: \u542f\u52a8\u8f6f\u4ef6\u3001\u622a\u56fe\u5339\u914d\u70b9\u51fb\u3001\u6309\u952e\u3001\u7b49\u5f85\u3001\u5750\u6807\u70b9\u51fb)", "(Supports: launch app, image match, key press, wait, coord click)"),
    ("ql_cleanup_label", "\u5173\u952e\u8bcd:", "Keywords:"),
    ("ql_item_tooltip", "\u53cc\u51fb\u6253\u5f00,\u5982\u6253\u5f00\u5931\u8d25,\u4f7f\u7528\u5feb\u901f\u542f\u52a8", "Double-click to open; if fails, use quick launch"),
    ("ql_launch_bound", "\u5df2\u7ed1\u5b9a\u542f\u52a8\u65b9\u5f0f: {mode}\u3002\n\u53cc\u51fb\/\u5de5\u4f5c\u6d41 \u8c03\u7528\u65f6\u5c06\u4f7f\u7528\u8be5 mode\uff0c\u4e0d\u518d\u53d7 UI \u5355\u9009\u6309\u94ae\u5f71\u54cd\u3002", "Bound: {mode}. Double-click/workflow use this mode."),
    ("ql_launch_unbound", "\u672a\u7ed1\u5b9a\u542f\u52a8\u65b9\u5f0f\u3002\u53cc\u51fb\/\u5de5\u4f5c\u6d41 \u8c03\u7528\u65f6\u4f7f\u7528\u5f53\u524d UI \u9009\u62e9\u7684 mode\u3002", "Not bound. Double-click/workflow uses current UI mode."),
    ("ql_coord_display_wind", "\u6309 Win+D \u663e\u793a\u684c\u9762...", "Press Win+D to show desktop..."),
    ("ql_coord_captured_display", "\u2705 \u5df2\u6355\u83b7: ({x}, {y})", "Captured: ({x}, {y})"),
    ("ql_coord_countdown", "\u23f1 {n} \u79d2\u540e\u6355\u83b7...", "Capturing in {n}s..."),
    # Mode names for _mode_name display
    ("ql_mode_desktop", "\u9f20\u6807\u53cc\u51fb\u684c\u9762\u56fe\u6807", "Double-click Desktop Icon"),
    ("ql_mode_direct", "\u76f4\u63a5\u542f\u52a8 (Popen)", "Direct Launch (Popen)"),
    ("ql_mode_shell", "Shell \u542f\u52a8 (cmd \/c)", "Shell Launch (cmd \/c)"),
    ("ql_mode_image", "\u56fe\u50cf\u8bc6\u522b \/ \u5750\u6807\u70b9\u51fb", "Image Match \/ Coord Click"),
    # Log messages (user sees in log panel)
    ("ql_log_bound", "\ud83d\udd17 \u5df2\u7ed1\u5b9a\u300c{sc}\u300d\u542f\u52a8\u65b9\u5f0f: {mode}", "Bound {sc} to {mode}"),
    ("ql_log_cleared", "\ud83d\uddd1 \u5df2\u6e05\u9664\u300c{sc}\u300d\u7684\u542f\u52a8\u65b9\u5f0f\u7ed1\u5b9a", "Cleared binding for {sc}"),
    ("ql_log_stop_requested", "\u23f9 \u5df2\u8bf7\u6c42\u505c\u6b62 worker", "Worker stop requested"),
    ("ql_log_stopped", "\u23f9 Worker \u5df2\u505c\u6b62", "Worker stopped"),
    ("ql_log_coord_saved", "\ud83d\udccd \u5df2\u8bb0\u5f55\u5750\u6807: ({x}, {y}) \u7c7b\u578b={t}", "Saved coord: ({x}, {y}) type={t}"),
    ("ql_log_template_saved", "\ud83d\udcf8 \u6a21\u677f\u5df2\u4fdd\u5b58: {f}", "Template saved: {f}"),
    ("ql_log_template_loaded", "\ud83d\udcc1 \u5df2\u52a0\u8f7d {n} \u4e2a\u6a21\u677f", "Loaded {n} templates"),
    ("ql_log_cleanup_done", "\ud83e\uddf9 \u6e05\u7406\u5b8c\u6210: {k}\/{t} \u4e2a", "Cleanup: {k}\/{t} done"),
    ("ql_log_cleanup_none", "\ud83e\uddf9 \u672a\u53d1\u73b0\u542f\u52a8\u4e2d\u7684\u8fdb\u7a0b", "No running processes found"),
    # File dialog
    ("ql_add_app_title", "\u9009\u62e9\u8981\u6dfb\u52a0\u7684\u5e94\u7528", "Select App to Add"),
    ("ql_add_app_name_label", "\u5e94\u7528\u540d\u79f0", "App Name"),
    ("ql_add_app_name_hint", "\u5e94\u7528\u540d\u79f0 (\u7559\u7a7a\u7528\u6587\u4ef6\u540d):", "App name (empty = filename):"),
    ("ql_exe_filter", "\u53ef\u6267\u884c\u6587\u4ef6 (*.exe *.bat *.cmd);;\u6240\u6709\u6587\u4ef6 (*.*)", "Executables (*.exe *.bat *.cmd);;All files (*.*)"),
    # Status display
    ("ql_template_none", "\u5f53\u524d\u6a21\u677f: \u65e0", "Template: none"),
    ("ql_template_count", "\u5f53\u524d\u6a21\u677f ({n}):\n{f}", "Template ({n}):\n{f}"),
    # Dialog titles
    ("dlg_confirm_delete", "\u786e\u8ba4\u5220\u9664", "Confirm Delete"),
    ("dlg_confirm_cleanup", "\u786e\u8ba4\u6e05\u7406", "Confirm Cleanup"),
    ("dlg_confirm_quit", "\u786e\u8ba4\u9000\u51fa", "Confirm Quit"),
    ("dlg_confirm_start", "\u786e\u8ba4\u542f\u52a8", "Confirm Start"),
    ("dlg_tip", "\u63d0\u793a", "Tip"),
    ("dlg_warning", "\u8b66\u544a", "Warning"),
    ("dlg_info", "\u6d88\u606f", "Info"),
]

added = 0
for key, zh, en in NEW_KEYS:
    zh_line = f'    {key!r}: {zh!r},\n'
    en_line = f'    {key!r}: {en!r},\n'
    if f'{key!r}:' in i18n_txt:
        print(f'SKIP: {key}')
        continue
    zh_start = i18n_txt.find('_STRINGS_ZH: dict[str, str] = {')
    en_start = i18n_txt.find('_STRINGS_EN: dict[str, str] = {')
    zh_section = i18n_txt[zh_start:en_start]
    zh_dict_end = zh_start + zh_section.rfind('}')
    i18n_txt = i18n_txt[:zh_dict_end] + zh_line + i18n_txt[zh_dict_end:]
    en_section = i18n_txt[en_start:]
    en_dict_end = en_start + en_section.rfind('}')
    i18n_txt = i18n_txt[:en_dict_end] + en_line + i18n_txt[en_dict_end:]
    added += 1
    print(f'ADD: {key}')

Path('i18n.py').write_text(i18n_txt, encoding='utf-8')
print(f'Added {added} keys')
