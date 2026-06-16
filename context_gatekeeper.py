"""上下文感知 - 规则拦截器（Gatekeeper）

在传感器层和 AI 推理之间做本地过滤，避免无意义的 AI 调用。
两层防线：
1. 进程黑名单（物理级拦截，最优先）
2. 内容嗅探规则（正则白名单）

只有通过这两层的内容才会被放行到 AI 推理阶段。
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

from context_sensor import ContextCapsule


# ---------------------------------------------------------------------------
# 默认配置
# ---------------------------------------------------------------------------
DEFAULT_PROCESS_BLACKLIST = [
    # 密码管理器
    "1password.exe", "bitwarden.exe", "keepass.exe", "lastpass.exe",
    "dashlane.exe", "enpass.exe", "roboform.exe", "nordpass.exe",
    # 系统凭据
    "credentialuibroker.exe", "lsass.exe",
    # 加密货币钱包
    "metamask.exe", "exodus.exe", "electrum.exe", "atomicwallet.exe",
    # SSH 私钥管理
    "pageant.exe", "ssh-agent.exe",
    # 终端凭据（部分敏感场景）
    # "cmd.exe",  # 默认不禁用，命令行操作也是高频场景
]

# 内置嗅探规则（正则 + 描述）
DEFAULT_SNIFF_RULES = [
    ("IP 地址", r"^(?:[0-9]{1,3}\.){3}[0-9]{1,3}$"),
    ("报错信息", r"Traceback|Exception|Error:|panic:|fatal:"),
    ("Nginx 配置", r"server\s*\{|location\s+/"),
    ("单据/表格", r"商品|单价|重量|合计|客户|应收"),
    ("命令行", r"^(?:pip|npm|cargo|go|git|docker|kubectl|ssh|scp|rsync)\s"),
    ("Windows 路径", r"^[A-Z]:\\"),
    ("Unix 路径", r"^(/home/|/etc/|/var/|~/)"),
    ("URL", r"https?://[^\s]+"),
    ("域名", r"\b[a-zA-Z0-9-]+\.(com|cn|org|net|io|dev|ai|app|me)\b"),
    ("JSON 数据", r'^\s*[\{\[][\s\S]+[\}\]]\s*$'),
    ("Base64", r"^[A-Za-z0-9+/]{20,}={0,2}$"),
    ("Stack Overflow 引用", r"stackoverflow\.com|github\.com/.*issues?"),
    # 学习类规则：默认关闭，用户按需在「嗅探规则」里勾选
    ("英文文本", r"\b[A-Za-z][A-Za-z'’-]{2,}\b(?:[\s,.;:!?()\[\]{}\"“”‘’、，。；：！？-]+[A-Za-z][A-Za-z'’-]{2,}\b){3,}", False),
    ("学术词汇", r"\b(?:hypothesis|methodology|epistemology|ontology|paradigm|empirical|quantitative|qualitative|regression|variance|significance|correlation|causality|algorithm|neural|transformer|embedding)\b|(?:模型|机制|范式|方法论|本体论|认识论|实证|定量|定性|回归|方差|显著性|相关性|因果|假设|变量|样本|置信区间|路径依赖|多重共线性)", False),
]


@dataclass
class SniffRule:
    name: str
    pattern: str
    enabled: bool = True
    _compiled: re.Pattern = field(default=None, repr=False, compare=False)

    def __post_init__(self):
        try:
            self._compiled = re.compile(self.pattern, re.IGNORECASE | re.MULTILINE)
        except re.error:
            self._compiled = None


@dataclass
class GateResult:
    passed: bool
    rule_name: str = ""        # 命中哪条规则（白名单命中时填写）
    blocked_reason: str = ""    # 被黑名单拦截的原因


class Gatekeeper:
    """规则拦截器

    使用方式：
        gk = Gatekeeper()
        result = gk.check(capsule)
        if result.passed:
            send_to_ai(capsule)
    """

    def __init__(
        self,
        process_blacklist: list[str] | None = None,
        sniff_rules: list[tuple[str, str]] | None = None,
    ):
        self._blacklist = set(p.lower() for p in (process_blacklist or DEFAULT_PROCESS_BLACKLIST))
        rules_src = sniff_rules if sniff_rules is not None else DEFAULT_SNIFF_RULES
        self._rules: list[SniffRule] = []
        for item in rules_src:
            if len(item) >= 3:
                name, pattern, enabled = item[0], item[1], bool(item[2])
            else:
                name, pattern, enabled = item[0], item[1], True
            self._rules.append(SniffRule(name, pattern, enabled))

    # ---- 进程黑名单 ----
    def add_to_blacklist(self, app_name: str):
        self._blacklist.add(app_name.lower())

    def remove_from_blacklist(self, app_name: str):
        self._blacklist.discard(app_name.lower())

    def get_blacklist(self) -> list[str]:
        return sorted(self._blacklist)

    def is_blacklisted(self, app_name: str) -> bool:
        return app_name.lower() in self._blacklist

    # ---- 嗅探规则 ----
    def add_rule(self, name: str, pattern: str):
        self._rules.append(SniffRule(name, pattern))

    def remove_rule(self, name: str):
        self._rules = [r for r in self._rules if r.name != name]

    def toggle_rule(self, name: str, enabled: bool):
        for r in self._rules:
            if r.name == name:
                r.enabled = enabled
                return

    def get_rules(self) -> list[SniffRule]:
        return list(self._rules)

    # ---- 主入口 ----
    def check(self, capsule: ContextCapsule) -> GateResult:
        # 第一道防线：进程黑名单（物理级）
        if capsule.foreground_app and self.is_blacklisted(capsule.foreground_app):
            return GateResult(
                passed=False,
                blocked_reason=f"进程黑名单: {capsule.foreground_app}",
            )

        # 第二道防线：嗅探规则（只对 clipboard 内容检查）
        if capsule.source != "clipboard":
            # 非剪贴板事件（窗口切换/文件变化/进程事件）直接放行
            return GateResult(passed=True, rule_name="(非剪贴板事件)")

        text = capsule.clipboard_text or ""
        if not text.strip():
            return GateResult(passed=False, blocked_reason="剪贴板为空")

        for rule in self._rules:
            if not rule.enabled or rule._compiled is None:
                continue
            if rule._compiled.search(text):
                return GateResult(passed=True, rule_name=rule.name)

        return GateResult(passed=False, blocked_reason="未匹配嗅探规则")
