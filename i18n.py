"""
i18n - 简易 i18n 系统
- 默认中文
- 切换英文从 strings_en 字典查
- 配置存 ~/桌面自动化助手/config.json: {"language": "en" | "zh"}

使用:
    from i18n import t, get_lang, set_lang
    label = t("tab_quick_launch")
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Literal


_USER_CONFIG = Path.home() / "桌面自动化助手" / "config.json"


def get_lang() -> Literal["zh", "en"]:
    """读取当前语言设置, 默认 zh"""
    try:
        if _USER_CONFIG.exists():
            cfg = json.loads(_USER_CONFIG.read_text(encoding="utf-8"))
            lang = cfg.get("language", "zh")
            return "en" if lang == "en" else "zh"
    except Exception:
        pass
    return "zh"


def set_lang(lang: Literal["zh", "en"]) -> None:
    """保存语言设置到 config.json"""
    _USER_CONFIG.parent.mkdir(parents=True, exist_ok=True)
    cfg = {}
    if _USER_CONFIG.exists():
        try:
            cfg = json.loads(_USER_CONFIG.read_text(encoding="utf-8"))
        except Exception:
            pass
    cfg["language"] = lang
    _USER_CONFIG.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


# ============================================================
# 翻译字典
# ============================================================
_STRINGS_ZH: dict[str, str] = {
    # 主窗口
    "app_title": "桌面自动化助手",
    "app_title_tray": "桌面自动化助手 - 后台任务栏",

    # 标签页
    "tab_search": "🔍 文件搜索",
    "tab_quick_launch": "🚀 快速启动",
    "tab_workflow": "🔄 工作流",
    "tab_tools": "🛠 工具",
    "tab_ai_perception": "🧠 AI 感知",

    # AI 感知子标签
    "tab_sensor_behavior": "📡 感知行为",
    "tab_ai_chat": "💬 AI 对话",
    "tab_sniff_rules": "🔎 嗅探规则",
    "tab_blacklist": "🚫 进程黑名单",
    "tab_backend": "🤖 后端",
    "tab_proactive_sniff": "🎯 主动嗅探",
    "tab_log": "📋 日志",

    # 通用按钮
    "btn_run": "🎯 执行",
    "btn_stop": "⏹ 停止",
    "btn_save": "💾 保存",
    "btn_cancel": "取消",
    "btn_delete": "删除",
    "btn_refresh": "🔄 刷新",
    "btn_apply": "应用",
    "btn_close": "关闭",
    "btn_browse": "浏览...",
    "btn_test": "测试",

    # 快速启动
    "label_target_info": "目标信息",
    "label_launch_mode": "启动方式",
    "label_coord": "📍 坐标",
    "label_capture_coord": "📍 捕捉坐标",
    "label_template": "模板",
    "btn_bind_launch_mode": "💾 绑定当前启动方式",
    "btn_clear_launch_mode": "🗑 清除绑定",
    "radio_direct": "🚀 直接启动 (Popen)",
    "radio_desktop": "🖱️ 鼠标双击桌面图标",
    "radio_shell": "⚙️ Shell 启动 (cmd /c)",
    "radio_image": "📸 图像识别 / 坐标点击",

    # 工作流
    "wf_list_title": "工作流列表",
    "wf_btn_new": "新建",
    "wf_btn_delete": "删除",
    "wf_btn_run": "▶ 执行",
    "wf_btn_stop": "⏹ 停止",
    "wf_step_list": "步骤列表",
    "wf_btn_add_step": "+ 添加步骤",
    "wf_btn_remove_step": "- 删除",
    "wf_step_type": "步骤类型:",
    "wf_step_name": "步骤名称:",
    "wf_step_enabled": "启用",

    # 工作流步骤类型
    "step_launch_app": "启动软件",
    "step_wait": "等待",
    "step_click_image": "截图匹配点击",
    "step_key_press": "按键输入",
    "step_type_text": "文字输入",
    "step_click_coords": "坐标点击",
    "step_search_file": "文件搜索",

    # 工具页
    "tools_system_settings": "🔧 系统设置",
    "tools_chk_autostart": "🚀 开机自动启动 (登录后自动后台运行)",
    "tools_chk_start_bg": "📦 启动时默认后台运行 (不显示窗口,仅托盘图标)",
    "tools_chk_show_log": "📋 显示底部操作日志",
    "tools_btn_hide_to_tray": "📦 最小化到托盘",
    "tools_btn_refresh": "🔄 刷新状态",
    "tools_mcp_server": "🤖 MCP Server (AI 接入)",
    "tools_btn_start_mcp": "▶ 启动 MCP Server",
    "tools_btn_stop_mcp": "⏹ 停止 MCP Server",
    "tools_btn_uninstall": "🗑 卸载程序",
    "tools_status_not_started": "状态: 未启动",
    "tools_status_not_enabled": "状态: 未启用",
    "tools_status_running": "状态: ✅ 运行中",

    # 语言设置
    "tools_language": "🌐 语言 / Language",
    "tools_lang_label": "界面语言:",
    "tools_lang_zh": "中文",
    "tools_lang_en": "English",
    "tools_lang_apply_hint": "切换语言后需重启 GUI 生效",
    "msg_lang_changed_title": "语言已切换",
    "msg_lang_changed_body": "界面语言已切换为「{lang}」。请关闭并重新启动程序以生效。",

    # 通用
    "msg_confirm": "确认",
    "msg_warning": "警告",
    "msg_info": "提示",
    "msg_error": "错误",
}

_STRINGS_EN: dict[str, str] = {
    # Main window
    "app_title": "Desktop Auto Assistant",
    "app_title_tray": "Desktop Auto Assistant - Background",

    # Tabs
    "tab_search": "🔍 File Search",
    "tab_quick_launch": "🚀 Quick Launch",
    "tab_workflow": "🔄 Workflows",
    "tab_tools": "🛠 Tools",
    "tab_ai_perception": "🧠 AI Awareness",

    # AI awareness subtabs
    "tab_sensor_behavior": "📡 Sensor Behavior",
    "tab_ai_chat": "💬 AI Chat",
    "tab_sniff_rules": "🔎 Sniff Rules",
    "tab_blacklist": "🚫 Process Blacklist",
    "tab_backend": "🤖 Backend",
    "tab_proactive_sniff": "🎯 Proactive Sniff",
    "tab_log": "📋 Log",

    # Common buttons
    "btn_run": "🎯 Run",
    "btn_stop": "⏹ Stop",
    "btn_save": "💾 Save",
    "btn_cancel": "Cancel",
    "btn_delete": "Delete",
    "btn_refresh": "🔄 Refresh",
    "btn_apply": "Apply",
    "btn_close": "Close",
    "btn_browse": "Browse...",
    "btn_test": "Test",

    # Quick launch
    "label_target_info": "Target Info",
    "label_launch_mode": "Launch Mode",
    "label_coord": "📍 Coordinates",
    "label_capture_coord": "📍 Capture",
    "label_template": "Template",
    "btn_bind_launch_mode": "💾 Bind Current Launch Mode",
    "btn_clear_launch_mode": "🗑 Clear Binding",
    "radio_direct": "🚀 Direct Launch (Popen)",
    "radio_desktop": "🖱️ Double-click Desktop Icon",
    "radio_shell": "⚙️ Shell Launch (cmd /c)",
    "radio_image": "📸 Image Match / Coord Click",

    # Workflow
    "wf_list_title": "Workflow List",
    "wf_btn_new": "New",
    "wf_btn_delete": "Delete",
    "wf_btn_run": "▶ Run",
    "wf_btn_stop": "⏹ Stop",
    "wf_step_list": "Steps",
    "wf_btn_add_step": "+ Add Step",
    "wf_btn_remove_step": "- Remove",
    "wf_step_type": "Step Type:",
    "wf_step_name": "Step Name:",
    "wf_step_enabled": "Enabled",

    # Workflow step types
    "step_launch_app": "Launch App",
    "step_wait": "Wait",
    "step_click_image": "Click on Image Match",
    "step_key_press": "Press Key",
    "step_type_text": "Type Text",
    "step_click_coords": "Click Coordinates",
    "step_search_file": "Search File",

    # Tools tab
    "tools_system_settings": "🔧 System Settings",
    "tools_chk_autostart": "🚀 Auto-start on login (run in background after login)",
    "tools_chk_start_bg": "📦 Start in background by default (hide window, tray only)",
    "tools_chk_show_log": "📋 Show bottom log panel",
    "tools_btn_hide_to_tray": "📦 Minimize to Tray",
    "tools_btn_refresh": "🔄 Refresh Status",
    "tools_mcp_server": "🤖 MCP Server (AI Integration)",
    "tools_btn_start_mcp": "▶ Start MCP Server",
    "tools_btn_stop_mcp": "⏹ Stop MCP Server",
    "tools_btn_uninstall": "🗑 Uninstall",
    "tools_status_not_started": "Status: Not running",
    "tools_status_not_enabled": "Status: Disabled",
    "tools_status_running": "Status: ✅ Running",

    # Language settings
    "tools_language": "🌐 Language / 语言",
    "tools_lang_label": "Interface Language:",
    "tools_lang_zh": "中文",
    "tools_lang_en": "English",
    "tools_lang_apply_hint": "Restart GUI to apply language change",
    "msg_lang_changed_title": "Language Changed",
    "msg_lang_changed_body": "Interface language has been switched to '{lang}'. Please close and restart the program to apply.",

    # Common
    "msg_confirm": "Confirm",
    "msg_warning": "Warning",
    "msg_info": "Info",
    "msg_error": "Error",
}


def t(key: str, **kwargs) -> str:
    """获取翻译。如果当前是英文且键存在则返回英文，否则返回中文。
    支持 .format(**kwargs) 占位符替换。"""
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


def all_keys() -> list[str]:
    """返回所有键(用于调试/审计)"""
    return list(_STRINGS_ZH.keys())
