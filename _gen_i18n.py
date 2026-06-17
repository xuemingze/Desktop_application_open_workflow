# -*- coding: utf-8 -*-
"""Regenerate i18n.py from scratch."""
from pathlib import Path
import sys
sys.stdout.reconfigure(encoding='utf-8')

PROLOGUE = '''"""
i18n - simple i18n system
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import Literal

_USER_CONFIG = Path.home() / "桌面自动化助手" / "config.json"

def get_lang() -> Literal["zh", "en"]:
    try:
        if _USER_CONFIG.exists():
            cfg = json.loads(_USER_CONFIG.read_text(encoding="utf-8"))
            return "en" if cfg.get("language") == "en" else "zh"
    except Exception:
        pass
    return "zh"

def set_lang(lang: Literal["zh", "en"]) -> None:
    _USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if _USER_CONFIG.exists():
        try:
            cfg = json.loads(_USER_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg["language"] = lang
    _USER_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")

'''

EPILOGUE = '''
def t(key: str, **kwargs) -> str:
    lang = get_lang()
    if lang == "en":
        s = _STRINGS_EN.get(key) or _STRINGS_ZH.get(key, key)
    else:
        s = _STRINGS_ZH.get(key, key)
    if kwargs:
        try:
            return s.format(**kwargs)
        except Exception:
            return s
    return s
'''

# (key, ZH, EN)
PAIRS = [
    ("app_title", "\u684c\u9762\u81ea\u52a8\u5316\u52a9\u624b", "Desktop Auto Assistant"),
    ("app_title_tray", "\u684c\u9762\u81ea\u52a8\u5316\u52a9\u624b - \u540e\u53f0\u4efb\u52a1\u680f", "Desktop Auto Assistant - Background"),
    ("msg_confirm", "\u786e\u8ba4", "Confirm"),
    ("msg_warning", "\u8b66\u544a", "Warning"),
    ("msg_info", "\u63d0\u793a", "Info"),
    ("msg_error", "\u9519\u8bef", "Error"),
    ("msg_ok", "\u786e\u5b9a", "OK"),
    ("msg_cancel", "\u53d6\u6d88", "Cancel"),
    ("msg_yes", "\u662f", "Yes"),
    ("msg_no", "\u5426", "No"),
    # Tabs
    ("tab_search", "\ud83d\udd0d \u6587\u4ef6\u641c\u7d22", "File Search"),
    ("tab_quick_launch", "\ud83d\ude80 \u5feb\u901f\u542f\u52a8", "Quick Launch"),
    ("tab_workflow", "\ud83d\udd04 \u5de5\u4f5c\u6d41", "Workflows"),
    ("tab_tools", "\ud83d\udee0 \u5de5\u5177", "Tools"),
    ("tab_ai_perception", "\ud83e\udda0 AI \u611f\u77e5", "AI Awareness"),
    ("tab_sensor_behavior", "\ud83d\udcad \u611f\u77e5\u884c\u4e3a", "Sensor Behavior"),
    ("tab_ai_chat", "\ud83d\udcac AI \u5bf9\u8bdd", "AI Chat"),
    ("tab_sniff_rules", "\ud83d\udd0e \u5616\u89c9\u89c4\u5219", "Sniff Rules"),
    ("tab_blacklist", "\ud83d\udd2b \u8fdb\u7a0b\u9ed1\u540d\u5355", "Process Blacklist"),
    ("tab_backend", "\u2699\ufe0f \u540e\u7aef", "Backend"),
    ("tab_proactive_sniff", "\ud83c\udfaf \u4e3b\u52a8\u5616\u89c9", "Proactive Sniff"),
    ("tab_log", "\ud83d\udccb \u65e5\u5fd7", "Log"),
    # Buttons
    ("btn_run", "\ud83d\ude4f \u6267\u884c", "Run"),
    ("btn_stop", "\u23f9 \u505c\u6b62", "Stop"),
    ("btn_save", "\ud83d\udcbe \u4fdd\u5b58", "Save"),
    ("btn_cancel", "\u53d6\u6d88", "Cancel"),
    ("btn_delete", "\u5220\u9664", "Delete"),
    ("btn_refresh", "\ud83d\udd04 \u5237\u65b0", "Refresh"),
    ("btn_apply", "\u5e94\u7528", "Apply"),
    ("btn_close", "\u5173\u95ed", "Close"),
    ("btn_browse", "\u6d4f\u89c8...", "Browse..."),
    ("btn_test", "\u6d4b\u8bd5", "Test"),
    ("btn_add", "\u6dfb\u52a0", "Add"),
    ("btn_remove", "\u5220\u9664", "Remove"),
    ("btn_clear", "\u6e05\u7a7a", "Clear"),
    # Tools
    ("tools_system_settings", "\u2699\ufe0f \u7cfb\u7edf\u8bbe\u7f6e", "System Settings"),
    ("tools_chk_autostart", "\u2705 \u5f00\u673a\u81ea\u52a8\u542f\u52a8 (\u767b\u5f55\u540e\u81ea\u52a8\u540e\u53f0\u8fd0\u884c)", "Auto-start on login"),
    ("tools_chk_start_bg", "\ud83d\udfe5 \u542f\u52a8\u65f6\u9ed8\u8ba4\u540e\u53f0\u8fd0\u884c", "Start in background by default"),
    ("tools_chk_show_log", "\ud83d\udccb \u663e\u793a\u5e95\u90e8\u64cd\u4f5c\u65e5\u5fd7", "Show bottom activity log"),
    ("tools_btn_hide_to_tray", "\ud83d\udfe5  \u7acb\u5373\u9690\u85cf\u5230\u6258\u76d8", "Hide to Tray Now"),
    ("tools_btn_refresh", "\ud83d\udd04  \u5237\u65b0\u72b6\u6001", "Refresh Status"),
    ("tools_status_not_started", "\u72b6\u6001: \u672a\u542f\u52a8", "Status: Not running"),
    ("tools_status_not_enabled", "\u72b6\u6001: \u672a\u542f\u7528", "Status: Disabled"),
    ("tools_status_autostart_enabled", "\u72b6\u6001: \u2705 \u5df2\u542f\u7528 (\u542f\u52a8\u9879: {cmd})", "Status: Enabled (Startup: {cmd})"),
    ("tools_status_autostart_disabled", "\u72b6\u6001: \u274c \u672a\u542f\u7528 (\u52fe\u9009\u4e0a\u9762\u590d\u9009\u6846\u4ee5\u542f\u7528\u5f00\u673a\u542f\u52a8)", "Status: Disabled (check box above to enable)"),
    ("tools_status_autostart_unavailable", "\u72b6\u6001: \u26a0\ufe0f autostart \u6a21\u5757\u4e0d\u53ef\u7528", "Status: autostart unavailable"),
    ("tools_status_startbg_enabled", "\u72b6\u6001: \u2705 \u542f\u7528 - \u4e0b\u6b21\u542f\u52a8\u65f6\u9ed8\u8ba4\u4ec5\u6258\u76d8\u8fd0\u884c,\u7a97\u53e3\u9690\u85cf\n  \u63d0\u793a: \u4ecd\u7136\u53ef\u4ee5\u53cc\u51fb\u6258\u76d8\u56fe\u6807\u6062\u590d\u7a97\u53e3", "Status: Enabled - next launch tray-only, window hidden\n  Tip: double-click tray icon to restore"),
    ("tools_status_startbg_disabled", "\u72b6\u6001: \u274c \u672a\u542f\u7528 - \u4e0b\u6b21\u542f\u52a8\u4f1a\u663e\u793a\u4e3b\u7a97\u53e3", "Status: Disabled - main window shows next launch"),
    ("tools_hint", "\ud83d\udca1 \u63d0\u793a:\u5173\u95ed\u7a97\u53e3\u540e\u4f1a\u6700\u5c0f\u5316\u5230\u6258\u76d8;\u53f3\u952e\u6258\u76d8\u56fe\u6807\u53ef\u300c\u9000\u51fa\u300d\u3002\n   \u5982\u9700\u5f00\u673a\u542f\u52a8\u4f1a\u5199\u5165 HKCU \u6ce8\u518c\u8868\u9879 (\u65e0\u9700\u7ba1\u7406\u5458\u6743\u9650)\u3002", "Tip: Closing minimizes to tray; right-click tray for Quit."),
    ("tools_danger_box", "* \u5371\u9669\u64cd\u4f5c", "Danger Zone"),
    ("tools_danger_warn", "* \u5378\u8f7d\u5c06\u5220\u9664:\n   - \u6240\u6709\u8fd0\u884c\u65f6\u6570\u636e(\u5de5\u4f5c\u6d41\u3001\u81ea\u5b9a\u4e49\u5e94\u7528\u3001\u7a97\u53e3\u72b6\u6001)\n   - \u7528\u6237\u914d\u7f6e(\u540e\u7aef\u5730\u5740\u3001API Key\u3001AI \u611f\u77e5\u6863\u6848)\n   - \u65e5\u5fd7\u6587\u4ef6\n   - \u672c\u7a0b\u5e8f exe \u6587\u4ef6\n\u6b64\u64cd\u4f5c\u4e0d\u53ef\u9006!", "Uninstall deletes: runtime data, config, logs, exe. Irreversible!"),
    ("tools_btn_uninstall", "X \u5378\u8f7d\u672c\u8f6f\u4ef6", "X Uninstall this program"),
    ("tools_uninstall_confirm_title", "\u26d4 \u786e\u8ba4\u5378\u8f7d", "Confirm Uninstall"),
    ("tools_uninstall_confirm_body", "\u4f60\u786e\u5b9a\u8981\u5378\u8f7d\u300c\u684c\u9762\u81ea\u52a8\u5316\u52a9\u624b\u300d\u5417?\n\n\u5c06\u5220\u9664:n  \u00b7 \u6240\u6709\u8fd0\u884c\u65f6\u6570\u636en  \u00b7 \u65e5\u5fd7\u6587\u4ef6n  \u00b7 \u672c\u7a0b\u5e8f exe \u6587\u4ef6nn\u26a0 \u6b64\u64cd\u4f5c\u4e0d\u53ef\u9006!", "Uninstall Desktop Auto Assistant? All data/logs/exe deleted. Irreversible!"),
    ("tools_mcp_server", "\ud83e\uddd2 MCP Server (AI \u63a5\u5165)", "MCP Server (AI Integration)"),
    ("tools_btn_start_mcp", "\u25b6 \u542f\u52a8 MCP Server", "Start MCP Server"),
    ("tools_btn_stop_mcp", "\u23f9 \u505c\u6b62", "Stop"),
    ("tools_mcp_cfg_label", "\ud83d\udccb MCP \u5ba2\u6237\u7aef\u914d\u7f6e\u793a\u4f8b (mcp_config.json):", "MCP client config (mcp_config.json):"),
    ("tools_mcp_docs_title", "\ud83d\udcda MCP \u5de5\u5177\u7b80\u4ecb (\u5171 {n} \u4e2a)", "MCP Tools ({n} tools)"),
    ("tools_btn_collapse", "\u25b2 \u6298\u53e3", "Collapse"),
    ("tools_btn_expand", "\u25bc \u5c55\u5f00", "Expand"),
    ("tools_mcp_param_label", "\u53c2\u6570:", "Params:"),
    ("tools_mcp_example_label", "\u793a\u4f8b:", "Example:"),
    ("tools_launcher_title", "\ud83d\ude80 \u542f\u52a8\u5668 (\u684c\u9762\u5feb\u6377\u65b9\u5f0f)", "Launcher (desktop shortcut)"),
    ("tools_launcher_info", "\u70b9\u51fb\u684c\u9762\u4e0a <b>\u300c\u684c\u9762\u52a9\u624b\u300d</b> \u5feb\u6377\u65b9\u5f0f,\u53ef\u5f39\u51fa\u83dc\u5355\u9009\u62e9:n  \ud83d\udfe2 \u542f\u52a8 GUIn  \ud83d\udfeb \u542f\u52a8 GUI + MCP servern  \ud83d\udd34 \u505c\u6b62\u6240\u6709", "Click Desktop Helper shortcut to choose:n  Green: Start GUIn  Yellow: Start GUI + MCPn  Red: Stop all"),
    ("tools_btn_install_shortcut", "\ud83d\udce5 \u521b\u5efa\u684c\u9762\u5feb\u6377\u65b9\u5f0f", "Create desktop shortcut"),
    ("tools_btn_uninstall_shortcut", "\ud83d\uddd1 \u5220\u9664\u684c\u9762\u5feb\u6377\u65b9\u5f0f", "Remove desktop shortcut"),
    ("tools_shortcut_created_msg", "\u684c\u9762\u5feb\u6377\u65b9\u5f0f\u5df2\u521b\u5efa!nn\u53cc\u51fb\u300c\u684c\u9762\u52a9\u624b\u300d\u5373\u53ef\u542f\u52a8\u672c\u7a0b\u5e8f\u3002n\u5982\u679c\u7a0b\u5e8f\u5df2\u8fd0\u884c,\u4f1a\u81ea\u52a8\u5207\u6362\u5230\u5df2\u8fd0\u884c\u7a97\u53e3\u3002", "Desktop shortcut created! Double-click Desktop Helper to start."),
    ("tools_language", "\ud83c\udf0d \u8bed\u8a00 / Language", "Language / \u8bed\u8a00"),
    ("tools_lang_label", "\u754c\u9762\u8bed\u8a00:", "Interface Language:"),
    ("tools_lang_zh", "\u4e2d\u6587", "\u4e2d\u6587"),
    ("tools_lang_en", "English", "English"),
    ("tools_lang_apply_hint", "\u5207\u6362\u8bed\u8a00\u540e\u9700\u91cd\u542f GUI \u751f\u6548", "Restart GUI to apply language change"),
    ("msg_lang_changed_title", "\u8bed\u8a00\u5df2\u5207\u6362", "Language Changed"),
    ("msg_lang_changed_body", "\u754c\u9762\u8bed\u8a00\u5df2\u5207\u6362\u4e3a\u300c{lang}\u300d\u3002\u8bf7\u5173\u95ed\u5e76\u91cd\u65b0\u542f\u52a8\u7a0b\u5e8f\u4ee5\u751f\u6548\u3002", "Language switched to '{lang}'. Restart to apply."),
    # Quick launch
    ("ql_info_selected", "\u9009\u4e2d\u4e00\u4e2a\u5feb\u6377\u65b9\u5f0f", "Select a shortcut"),
    ("ql_radio_direct", "\ud83d\ude80 \u76f4\u63a5\u542f\u52a8 (Popen,\u6700\u4f18\u5148,\u6700\u7a33\u5b9a)", "Direct Launch (Popen, fastest, most stable)"),
    ("ql_radio_desktop", "\ud83d\uddb1\ufe0f \u9f20\u6807\u53cc\u51fb\u684c\u9762\u56fe\u6807 (\u5907\u9009)", "Double-click Desktop Icon (fallback)"),
    ("ql_radio_shell", "\u2699\ufe0f Shell \u542f\u52a8 (cmd /c,\u7279\u6b8a\u573a\u666f)", "Shell Launch (cmd /c, special cases)"),
    ("ql_radio_image", "\ud83d\udcf8 \u57fa\u4e8e\u56fe\u6807\u8bc6\u522b\u7684\u5750\u6807\u70b9\u51fb", "Image Match / Coord Click"),
    ("ql_chk_notepad", "\u542f\u52a8\u540e\u6a21\u62df\u952e\u9f20\u4ea4\u4e92 (\u4ec5\u8bb0\u4e8b\u672c\u751f\u6548)", "Simulate keyboard/mouse after launch (notepad only)"),
    ("ql_chk_show_desktop", "\u6267\u884c\u524d\u5148\u663e\u793a\u684c\u9762 (Win+D)", "Show desktop before execution (Win+D)"),
    ("ql_coord_status", "\ud83d\udccd \u5750\u6807\u72b6\u6001:", "Coord Status:"),
    ("ql_coord_not_set", "\u672a\u8bbe\u7f6e", "Not set"),
    ("ql_search_placeholder", "\ud83d\udd0d \u641c\u7d22\u5feb\u6377\u65b9\u5f0f...", "Search shortcuts..."),
    ("ql_btn_refresh", "\ud83d\udd04 \u5237\u65b0\u5217\u8868", "Refresh List"),
    ("ql_btn_add_custom", "\u2795 \u6dfb\u52a0\u81ea\u5b9a\u4e49", "Add Custom"),
    ("ql_btn_show_desktop", "\ud83d\uddd4 Win+D", "Win+D"),
    ("ql_label_log", "\ud83d\udddc \u64cd\u4f5c\u65e5\u5fd7", "Activity Log"),
    ("ql_no_target", "(\u672a\u9009\u4e2d)", "(none)"),
    ("ql_no_template", "\u672a\u8bbe\u7f6e", "Not set"),
    ("ql_click_double", "\u53cc\u51fb", "Double"),
    ("ql_click_single", "\u5355\u51fb", "Single"),
    ("ql_click_right", "\u53f3\u51fb", "Right"),
    # Workflow
    ("wf_list_title", "\u5de5\u4f5c\u6d41\u5217\u8868", "Workflow List"),
    ("wf_btn_new", "\u65b0\u5efa", "New"),
    ("wf_btn_delete", "\u5220\u9664", "Delete"),
    ("wf_btn_add_step", "+ \u6dfb\u52a0\u6b65\u9aa4", "+ Add Step"),
    ("wf_btn_remove_step", "- \u5220\u9664", "Remove"),
    ("wf_step_section", "\ud83d\udcd9 \u6b65\u9aa4\u8be6\u60c5", "Step Details"),
    ("wf_step_type", "\u7c7b\u578b:", "Type:"),
    ("wf_step_name", "\u540d\u79f0:", "Name:"),
    ("wf_step_enabled", "\u542f\u7528", "Enabled"),
    ("wf_select_app_hint", "\u4ece\u684c\u9762\u5feb\u6377\u65b9\u5f0f\u5217\u8868\u9009\u62e9(\u53ef\u6267\u884c/\u505c\u6b62):", "Select from shortcut list:"),
    ("wf_select_app_placeholder", "-- \u9009\u62e9\u8f6f\u4ef6 --", "-- Select app --"),
    ("wf_path_label", "\u8def\u5f84: ", "Path: "),
    ("wf_seconds_suffix", " \u79d2", " sec"),
    ("wf_no_preview", "(\u65e0\u9884\u89c8)", "(no preview)"),
    ("wf_chk_show_desktop", "\u5148\u6309 Win+D \u663e\u793a\u684c\u9762", "Show desktop with Win+D first"),
    ("wf_click_type", "\u70b9\u51fb\u7c7b\u578b:", "Click type:"),
    ("wf_click_left_single", "\u5de6\u952e\u5355\u51fb", "Left single"),
    ("wf_click_left_double", "\u5de6\u952e\u53cc\u51fb", "Left double"),
    ("wf_click_right_single", "\u53f3\u952e\u5355\u51fb", "Right single"),
    ("wf_key_press_hint", "\u6309\u952e (\u652f\u6301\u7ec4\u5408\u952e,\u5982 ctrl+c / alt+tab / win+d):", "Keys (e.g. ctrl+c / alt+tab / win+d):"),
    ("wf_text_input_hint", "\u8981\u8f93\u5165\u7684\u6587\u5b57(\u652f\u6301\u4e2d\u6587/\u591a\u884c):", "Text to type (supports Chinese/multiline):"),
    ("wf_seconds_unit", "\u79d2", "sec"),
    ("wf_click_coords_label", "\u70b9\u51fb:", "Click:"),
    ("wf_btn_save_step", "\ud83d\udcbe \u4fdd\u5b58\u6b65\u9aa4\u4fee\u6539", "Save step"),
    ("wf_btn_save_to_file", "\ud83d\udcbe \u4fdd\u5b58\u5230\u6587\u4ef6", "Save to file"),
    ("wf_btn_run", "\u25b6 \u6267\u884c", "Run"),
    ("wf_btn_stop", "\u23f9 \u505c\u6b62", "Stop"),
    ("wf_no_workflow", "\u8bf7\u9009\u62e9\u4e00\u4e2a\u5de5\u4f5c\u6d41", "Please select a workflow"),
    ("wf_no_step", "\u8bf7\u9009\u62e9\u4e00\u4e2a\u6b65\u9aa4", "Please select a step"),
    ("wf_msg_no_steps", "\u5de5\u4f5c\u6d41\u6ca1\u6709\u6b65\u9aa4", "Workflow has no steps"),
    ("wf_msg_name_exists", "\u5de5\u4f5c\u6d41\u540d\u79f0\u5df2\u5b58\u5728", "Workflow name already exists"),
    ("wf_msg_saved", "\u5df2\u4fdd\u5b58", "Saved"),
    ("wf_msg_loaded", "\u5df2\u91cd\u65b0\u52a0\u8f7d", "Reloaded"),
    ("wf_msg_stop_requested", "\u5df2\u8bf7\u6c42\u505c\u6b62", "Stop requested"),
    ("wf_coord_captured", "\ud83d\udccd \u5df2\u57f9\u6355\u5750\u6807 ({cx},{cy})", "Captured ({cx},{cy})"),
    ("wf_template_missing", "\u26a0\ufe0f \u6a21\u677f\u4e0d\u5b58\u5728: {path}", "Template missing: {path}"),
    ("wf_match_found", "\u2705 \u627e\u5230 @ ({cx},{cy}) \u7f6e\u4fe1\u5ea6={conf:.2f}", "Found @ ({cx},{cy}) conf={conf:.2f}"),
    ("wf_pil_found", "\u2705 PIL \u627e\u5230 @ ({cx},{cy})", "PIL found @ ({cx},{cy})"),
    ("wf_match_error", "\u26a0\ufe0f \u5339\u914d\u5f02\u5e38: {e}", "Match error: {e}"),
    ("wf_coord_written", "\u2705 \u5df2\u5199\u5165\u5750\u6807 ({cx},{cy}) \u5e76\u70b9\u51fb", "Wrote coord ({cx},{cy}) and clicked"),
    ("wf_coord_display", "\u5df2\u57f9\u6355: ({x}, {y})", "Captured: ({x}, {y})"),
    ("wf_capture_countdown", "{n} \u79d2\u540e\u57f9\u6355...", "{n}s before capture..."),
    ("wf_step_added", "\u5df2\u6dfb\u52a0\u65b0\u6b65\u9aa4,\u9009\u4e2d row={row}", "Added step, selected row={row}"),
    ("wf_save_failed_no_step", "\u26a0\ufe0f \u4fdd\u5b58\u5931\u8d25: \u672a\u9009\u4e2d\u6b65\u9aa4 (row={row}, total={total})", "Save failed: no step selected (row={row}, total={total})"),
    ("wf_save_failed_no_wf", "\u26a0\ufe0f \u4fdd\u5b58\u5931\u8d25: \u672a\u9009\u4e2d\u5de5\u4f5c\u6d41", "Save failed: no workflow selected"),
    ("wf_save_failed_not_found", "\u26a0\ufe0f \u4fdd\u5b58\u5931\u8d25: \u5de5\u4f5c\u6d41 '{wf_name}' \u4e0d\u5728\u5217\u8868\u4e2d", "Save failed: workflow '{wf_name}' not found"),
    ("wf_step_saved", "\u6b65\u9aa4\u5df2\u4fdd\u5b58: {name} (\u7c7b\u578b={type})", "Step saved: {name} (type={type})"),
    ("wf_coord_log", "\u57f9\u6355\u5230\u5750\u6807: ({x}, {y})", "Captured: ({x}, {y})"),
    ("wf_screenshot_saved", "\u622a\u56fe\u5df2\u4fdd\u5b58: {out}", "Screenshot saved: {out}"),
    ("wf_select_program_title", "\u9009\u62e9\u7a0b\u5e8f", "Select Program"),
    ("wf_exe_filter", "\u53ef\u6267\u884c\u6587\u4ef6 (*.exe *.bat *.cmd);;\u6240\u6709\u6587\u4ef6 (*.*)", "Executables (*.exe *.bat *.cmd);;All files (*.*)"),
    ("wf_btn_screenshot", "\u2702\ufe0f \u622a\u56fe\u6846\u9009", "Screenshot select"),
    ("wf_btn_capture_coord", "\ud83d\udd0d \u57f9\u6355\u5750\u6807", "Capture Coordinate"),
    ("wf_btn_capture_mouse", "\ud83d\ude4f \u57f9\u6355\u5f53\u524d\u9f20\u6807\u5750\u6807 (3\u79d2\u5012\u8ba1\u65f6)", "Capture mouse coord (3s countdown)"),
    # Step types
    ("step_launch_app", "\u542f\u52a8\u8f6f\u4ef6", "Launch App"),
    ("step_wait", "\u7b49\u5f85", "Wait"),
    ("step_click_image", "\u622a\u56fe\u5339\u914d\u70b9\u51fb", "Image Match Click"),
    ("step_key_press", "\u6309\u952e\u8f93\u5165", "Key Press"),
    ("step_type_text", "\u6587\u5b57\u8f93\u5165", "Type Text"),
    ("step_click_coords", "\u5750\u6807\u70b9\u51fb", "Coord Click"),
    ("step_search_file", "\u6587\u4ef6\u641c\u7d22", "Search File"),
    # AI awareness
    ("ai_chk_enabled", "\u542f\u7528 AI \u611f\u77e5", "Enable AI Awareness"),
    ("ai_label_backend", "\u540e\u7aef\u5730\u5740:", "Backend URL:"),
    ("ai_label_model", "\u6a21\u578b\u540d:", "Model name:"),
    ("ai_label_api_key", "API Key:", "API Key:"),
    ("ai_btn_save_settings", "\ud83d\udcbe \u4fdd\u5b58\u8bbe\u7f6e", "Save Settings"),
    ("ai_btn_test_conn", "\ud83d\udd0c \u6d4b\u8bd5\u8fde\u63a5", "Test Connection"),
    ("ai_btn_clear_log", "\ud83e\uddf9 \u6e05\u7a7a\u65e5\u5fd7", "Clear Log"),
    # Context tab
    ("ctx_sensor_box", "\u611f\u901a\u5668\uff08\u591a\u9009\uff09", "Sensors (multi-select)"),
    ("ctx_chk_clipboard", "\ud83d\udccb \u526a\u8d34\u677f\u76d1\u542c\uff08\u63a8\u8350\u5f00\u542c\uff0c\u96f6\u5f00\u9500\uff09", "Clipboard monitor (recommended)"),
    ("ctx_chk_window", "\ud83d\ude3f \u524d\u53f0\u7a97\u53e3\u5207\u6362\u76d1\u542c", "Foreground window switch monitor"),
    ("ctx_chk_file", "\ud83d\udcc1 \u6587\u4ef6\u7cfb\u7edf\u76d1\u89c6\uff08\u624b\u52a8\u6dfb\u52a0\u76ee\u5f55\uff09", "File system monitor (add dirs manually)"),
    ("ctx_chk_process", "\u2699\ufe0f \u8fdb\u7a0b\u542f\u52a8/\u9000\u51fa\u76d1\u542c\uff08\u914d\u5408\u4e3b\u52a8\u5616\u89c9\u7528\u6237\u6863\u6848\u89e6\u53d1\uff09", "Process start/exit monitor"),
    ("ctx_file_watch_path", "\u6587\u4ef6\u76d1\u89c6\u8def\u5f84", "File watch paths"),
    ("ctx_btn_add_dir", "\u2795 \u6dfb\u52a0\u76ee\u5f55", "Add Directory"),
    ("ctx_btn_rm_dir", "\u2796 \u79fb\u9664\u9009\u4e2d", "Remove Selected"),
    ("ctx_btn_test_clipboard", "\ud83e\uddea \u6d4b\u8bd5\u526a\u8d34\u677f\u6349\u53d6", "Test Clipboard Capture"),
    ("ctx_btn_test_toast", "\ud83d\udcac \u6d4b\u8bd5\u6c14\u6ce1", "Test Toast"),
    ("ctx_btn_clear_toasts", "\ud83e\uddf9 \u6e05\u9664\u6240\u6709\u6c14\u6ce1", "Clear