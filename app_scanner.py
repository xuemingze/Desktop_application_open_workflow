"""
应用扫描器 - 增强版
- 扫描多种文件类型: .lnk, .exe, .bat, .cmd, .url
- 自动去重 (同名 .lnk 和 .exe 不重复)
- 自动分类: 系统/开发/办公/网络/媒体/游戏/其他
- 自定义添加 (从 JSON 配置文件)
"""
import json
import os
import re
from pathlib import Path
from typing import Optional

# 自定义程序的存储位置
CUSTOM_APPS_FILE = Path(__file__).parent / "custom_apps.json"


# ============================================================
# 自动分类字典
# ============================================================
CATEGORY_KEYWORDS = {
    "💻 开发": [
        "code", "studio", "git", "pycharm", "intellij", "vscode", "visual",
        "eclipse", "android", "xcode", "sublime", "atom", "vim", "emacs",
        "docker", "kubernetes", "kubectl", "redis", "mongodb", "mysql",
        "postman", "insomnia", "swagger", "curl", "wget", "npm", "yarn",
        "node", "python", "java", "go", "rust", "ruby", "php", "perl",
        "aipy", "aipypro", "lobster", "claude", "cursor", "windsurf",
        "minimax", "devenv", "compile", "build", "make", "cmake",
        "terminal", "powershell", "cmd", "bash", "wsl",
        "mobaxterm", "xterm", "putty", "ssh", "ftp",
    ],
    "🌐 浏览器": [
        "chrome", "firefox", "edge", "safari", "opera", "brave", "vivaldi",
        "browser", "explorer", "ie",
    ],
    "💬 通讯": [
        "wechat", "qq", "telegram", "discord", "slack", "teams", "skype",
        "zoom", "dingtalk", "钉钉", "feishu", "lark", "企业微信",
        "whatsapp", "line", "signal", "微信",
    ],
    "🎮 游戏": [
        "steam", "epic", "origin", "battle.net", "uplay", "ubisoft",
        "wegame", "网易", "腾讯", "原神", "genshin", "honkai", "star rail",
        "wuthering", "鸣潮", "绝区零", "绝地求生", "英雄联盟", "lol",
        "game", "play", "launcher", "模拟器", "雷电", "夜神", "mumu",
        "我的世界", "minecraft", "steamworks", "uu", "网易云游戏",
    ],
    "🎬 媒体": [
        "vlc", "potplayer", "kmplayer", "mpv", "iina",
        "video", "movie", "film", "video", "audio", "music",
        "spotify", "网易云", "qq音乐", "酷狗", "酷我", "千千",
        "obs", "录屏", "剪辑", "剪映", "pr", "premiere", "达芬奇",
        "davinci", "ae", "after effects", "ps", "photoshop",
        "lightroom", "lr", "figma", "sketch", "illustrator", "ai",
        "blender", "maya", "3d", "cad", "画图",
    ],
    "📝 办公": [
        "office", "word", "excel", "powerpoint", "ppt", "wps", "金山",
        "pdf", "acrobat", "reader", "foxit", "福昕",
        "notion", "obsidian", "typora", "印象笔记", "evernote", "onenote",
        "todoist", "滴答清单", "things", "ticktick", "todo",
        "xmind", "mindmanager", "思维导图", "process", "visio",
        "project", "邮件", "mail", "outlook", "thunderbird", "foxmail",
        "foxmail", "网易邮箱", "qq邮箱",
    ],
    "📁 文件": [
        "explorer", "total commander", "everything", "listary", "wizfile",
        "utools", "uTools", "qttabbar", "clover",
    ],
    "📥 下载": [
        "迅雷", "xunlei", "thunder", "idm", "downloader", "aria2",
        "百度网盘", "夸克网盘", "阿里云盘", "坚果云", "微云", "onedrive",
        "googledrive", "dropbox", "网盘",
    ],
    "🛡️ 安全": [
        "defender", "antivirus", "360", "qq管家", "火绒", "卡巴斯基",
        "kaspersky", "eset", "nod32", "avast", "avg", "bitdefender",
        "malwarebytes", "adwcleaner", "ccleaner", "清理",
    ],
    "🖥️ 系统": [
        "settings", "设置", "control", "控制面板", "task", "任务",
        "registry", "注册表", "device", "设备", "system", "系统",
        "update", "更新", "驱动", "driver", "nvidia", "amd", "intel",
        "realtek", "声卡", "显卡", "网卡", "bluetooth", "蓝牙",
    ],
    "📚 学习": [
        "codecombat", "编程猫", "scratch", "少儿", "儿童", "学习",
        "学习强国", "duolingo", "quizlet", "anki", "有道", "网易云课堂",
    ],
}


def categorize(name: str, target: str = "") -> str:
    """根据名称和目标路径自动分类"""
    n = (name + " " + target).lower()
    # 按优先级匹配 (前面的优先)
    priority = [
        "🎮 游戏",  # 游戏关键词比较泛,优先匹配
        "💬 通讯",  # 微信/QQ 等
        "🌐 浏览器",
        "🛡️ 安全",
        "📥 下载",
        "💻 开发",
        "📝 办公",
        "🎬 媒体",
        "📁 文件",
        "🖥️ 系统",
        "📚 学习",
    ]
    for cat in priority:
        for kw in CATEGORY_KEYWORDS.get(cat, []):
            if kw in n:
                return cat
    return "📦 其他"


# ============================================================
# 文件路径解析
# ============================================================
def parse_shortcut(lnk_path: Path) -> Optional[dict]:
    """解析 .lnk 快捷方式"""
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        sc = shell.CreateShortCut(str(lnk_path))
        return {
            "name": lnk_path.stem,
            "target": sc.TargetPath or "",
            "lnk_path": str(lnk_path),
            "work_dir": sc.WorkingDirectory or "",
        }
    except Exception:
        return None


def load_custom_apps() -> list[dict]:
    """加载用户自定义应用"""
    if not CUSTOM_APPS_FILE.exists():
        return []
    try:
        return json.loads(CUSTOM_APPS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []


def save_custom_apps(apps: list[dict]) -> None:
    """保存用户自定义应用"""
    CUSTOM_APPS_FILE.write_text(
        json.dumps(apps, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def add_custom_app(name: str, target: str, work_dir: str = "") -> dict:
    """添加一个自定义应用"""
    if not Path(target).exists():
        raise FileNotFoundError(f"目标不存在: {target}")
    apps = load_custom_apps()
    # 去重
    for a in apps:
        if a["target"].lower() == target.lower():
            return a  # 已存在
    app = {
        "name": name or Path(target).stem,
        "target": target,
        "work_dir": work_dir or str(Path(target).parent),
        "lnk_path": "",  # 自定义不是快捷方式
        "is_custom": True,
    }
    apps.append(app)
    save_custom_apps(apps)
    return app


def remove_custom_app(target: str) -> bool:
    """移除自定义应用"""
    apps = load_custom_apps()
    new_apps = [a for a in apps if a["target"].lower() != target.lower()]
    if len(new_apps) < len(apps):
        save_custom_apps(new_apps)
        return True
    return False


# ============================================================
# 桌面路径
# ============================================================
def get_real_desktop() -> Path:
    """通过注册表取真实桌面路径"""
    try:
        from winreg import HKEY_CURRENT_USER, OpenKey, QueryValueEx
        with OpenKey(
            HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer\Shell Folders",
        ) as k:
            return Path(QueryValueEx(k, "Desktop")[0])
    except Exception:
        return Path(os.environ.get("USERPROFILE", "")) / "Desktop"


# ============================================================
# 主扫描函数
# ============================================================
def scan_all_apps() -> list[dict]:
    """
    扫描所有应用,返回统一格式列表
    每项: { name, target, lnk_path, work_dir, category, is_custom, exists }
    """
    results = {}  # 用 target 去重

    # 1. 扫描 .lnk 快捷方式
    desktop = get_real_desktop()
    if desktop.exists():
        for lnk in desktop.glob("*.lnk"):
            try:
                info = parse_shortcut(lnk)
                if not info or not info["target"]:
                    continue
                target = info["target"]
                # 去重: 同 target 不重复
                if target.lower() in results:
                    continue
                info["category"] = categorize(info["name"], target)
                info["is_custom"] = False
                info["exists"] = Path(target).exists()
                results[target.lower()] = info
            except Exception:
                continue

        # 2. 扫描桌面上的 .exe 文件 (有些人直接把 exe 放桌面)
        for exe in desktop.glob("*.exe"):
            try:
                target = str(exe)
                if target.lower() in results:
                    continue
                info = {
                    "name": exe.stem,
                    "target": target,
                    "lnk_path": "",
                    "work_dir": str(exe.parent),
                    "category": categorize(exe.stem, target),
                    "is_custom": False,
                    "exists": True,
                }
                results[target.lower()] = info
            except Exception:
                continue

        # 3. 扫描桌面上的 .bat / .cmd 批处理
        for ext in ("*.bat", "*.cmd"):
            for script in desktop.glob(ext):
                try:
                    target = str(script)
                    if target.lower() in results:
                        continue
                    info = {
                        "name": script.stem,
                        "target": target,
                        "lnk_path": "",
                        "work_dir": str(script.parent),
                        "category": categorize(script.stem, target),
                        "is_custom": False,
                        "exists": True,
                        "is_script": True,
                    }
                    results[target.lower()] = info
                except Exception:
                    continue

        # 4. 扫描开始菜单的快捷方式 (扩展)
        start_menu = Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs"
        if start_menu.exists():
            for lnk in start_menu.rglob("*.lnk"):
                try:
                    info = parse_shortcut(lnk)
                    if not info or not info["target"]:
                        continue
                    target = info["target"]
                    if target.lower() in results:
                        continue
                    # 只保留桌面级分类,在名字前标注
                    info["category"] = categorize(info["name"], target)
                    info["is_custom"] = False
                    info["exists"] = Path(target).exists()
                    info["from_start_menu"] = True
                    results[target.lower()] = info
                except Exception:
                    continue

    # 5. 加载用户自定义应用
    for app in load_custom_apps():
        target = app["target"]
        if target.lower() in results:
            continue  # 不覆盖
        app = dict(app)
        app["category"] = categorize(app.get("name", ""), target)
        app["exists"] = Path(target).exists()
        results[target.lower()] = app

    # 排序: 按分类 + 名称
    cat_order = {c: i for i, c in enumerate([
        "💻 开发", "🌐 浏览器", "💬 通讯", "📝 办公", "🎬 媒体",
        "🎮 游戏", "📁 文件", "📥 下载", "🛡️ 安全", "🖥️ 系统",
        "📚 学习", "📦 其他",
    ])}
    sorted_list = sorted(
        results.values(),
        key=lambda x: (cat_order.get(x.get("category", "📦 其他"), 99), x.get("name", "").lower())
    )
    return sorted_list


def group_by_category(apps: list[dict]) -> dict[str, list[dict]]:
    """按分类分组"""
    groups = {}
    for app in apps:
        cat = app.get("category", "📦 其他")
        groups.setdefault(cat, []).append(app)
    return groups


# ============================================================
# 测试
# ============================================================
if __name__ == "__main__":
    print("扫描所有应用...")
    apps = scan_all_apps()
    print(f"共 {len(apps)} 个\n")

    groups = group_by_category(apps)
    for cat, items in groups.items():
        print(f"\n=== {cat} ({len(items)}) ===")
        for app in items[:5]:  # 每组最多显示 5 个
            mark = "🟢" if app.get("exists") else "🔴"
            custom = " ⭐" if app.get("is_custom") else ""
            print(f"  {mark} {app['name']}{custom}")
        if len(items) > 5:
            print(f"  ... 还有 {len(items) - 5} 个")
