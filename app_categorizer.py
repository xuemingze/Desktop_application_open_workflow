# app_categorizer.py
# 功能: 静态分类字典 + JSON持久化，负责将 exe_name 映射为语义化标签

import json
from pathlib import Path
from log_bus import log_bus

DEFAULT_CATEGORIES = {
    "[开发编程]": ["code.exe", "cursor.exe", "pycharm64.exe", "idea64.exe", 
                  "sublime_text.exe", "notepad++.exe", "devenv.exe"],
    "[系统运维]": ["mobaxterm.exe", "cmd.exe", "powershell.exe", "windowsterminal.exe",
                  "putty.exe", "winscp.exe", "xshell.exe", "mstsc.exe"],
    "[沟通协作]": ["wechat.exe", "feishu.exe", "dingtalk.exe", "qq.exe", "slack.exe", "wxwork.exe"],
    "[浏览器]": ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "safari.exe"],
    "[办公文档]": ["winword.exe", "excel.exe", "powerpnt.exe", "wps.exe", "foxitreader.exe", "obsidian.exe"],
    "[设计创意]": ["photoshop.exe", "figma.exe", "illustrator.exe", "blender.exe", "premiere.exe"],
    "[娱乐]": ["steam.exe", "epicgameslauncher.exe", "spotify.exe", "qqmusic.exe", "bilibili.exe"],
    "[其他]": [],
}

class AppCategorizer:
    def __init__(self, config_dir: Path):
        self.config_path = config_dir / "app_categories.json"
        self.categories = {}
        self._load()

    def _load(self):
        """加载自定义分类，如果没有则使用默认并保存"""
        if self.config_path.exists():
            try:
                with open(self.config_path, "r", encoding="utf-8") as f:
                    self.categories = json.load(f)
                return
            except Exception as e:
                log_bus.emit(f"[Categorizer] JSON 读取失败，使用默认配置: {e}")
        
        self.categories = DEFAULT_CATEGORIES.copy()
        self._save()

    def _save(self):
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.categories, f, ensure_ascii=False, indent=4)
        except Exception as e:
            log_bus.emit(f"[Categorizer] JSON 保存失败: {e}")

    def categorize(self, exe_name: str) -> str:
        """根据进程名返回标签"""
        if not exe_name:
            return "[其他]"
        
        exe_lower = exe_name.lower()
        for cat, exes in self.categories.items():
            if exe_lower in exes:
                return cat
        return "[其他]"

# 提供一个单例供外部快捷调用 (需要先 init_categorizer)
_global_categorizer = None

def init_categorizer(config_dir: Path):
    global _global_categorizer
    _global_categorizer = AppCategorizer(config_dir)

def categorize(exe_name: str) -> str:
    if _global_categorizer:
        return _global_categorizer.categorize(exe_name)
    return "[其他]"