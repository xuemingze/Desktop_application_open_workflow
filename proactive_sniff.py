"""主动嗅探引擎（Proactive Sniffing）

按用户配置的"每日主动次数"，在剩余时间段里随机时间点主动生成"朋友式问题"。
- 主题基于用户档案（爱好/兴趣/学习/工作）
- 通过 AI 后端生成简短问句（≤20 字，朋友聊天风格）
- 复用现有 Toast 系统呈现
- 自动去重（与最近 N 条历史比对）
"""
from __future__ import annotations

import json
import random
import re
import time
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

from PySide6.QtCore import QObject, QTimer, Signal, Slot

from context_agent import LLMBackend, EchoBackend, parse_intent_response
from context_toast import ToastManager, ToastIntent


PROACTIVE_SYSTEM_PROMPT = """你是一个关心用户的朋友式桌宠。基于用户的个人档案，主动想一个有趣的话题或问题。

【用户档案】
{user_profile}

【历史已问（避免重复）】
{history}

【当前时间】{now}
【可选话题类型】
- 工作相关的新动态 / 行业新闻
- 学习进展 / 推荐学习资源
- 兴趣爱好相关的小知识
- 闲聊式的小问题（如天气、心情）

要求：
1. 输出一句简短的话（10-20 字）
2. 朋友聊天口吻（轻松自然，可以用 emoji）
3. 必须输出 JSON 格式：
{{"question": "你今天加班了吗？注意休息哦 🌙", "category": "work"}}
"category" 可选: work / study / hobby / chat
"""

BEHAVIOR_SYSTEM_PROMPT = """你是一个关心用户的朋友式桌宠。用户刚刚打开了/关注了【{detected_topic}】，这是他们感兴趣的东西。

【用户档案】
{user_profile}

【检测到的行为】
检测关键词：{detected_topic}

【历史已问（避免重复）】
{history}

【当前时间】{now}

要求：
1. 基于用户兴趣和当前行为，想一个相关的朋友式问题或评论（10-20 字）
2. 朋友聊天口吻（轻松自然，可以用 emoji）
3. 必须输出 JSON 格式：
{{"question": "哇你在玩鸣潮啊，最近抽到啥好角色了吗 🎮", "category": "hobby"}}
"category" 可选: work / study / hobby / chat
"""


@dataclass
class ProactiveQuestion:
    """一条主动问题"""
    text: str                # "你今天加班了吗？"
    category: str            # "work" / "study" / "hobby" / "chat"
    timestamp: float
    shown: bool = False      # 是否已展示


@dataclass
class UserProfile:
    """用户档案——驱动主动嗅探主题"""
    hobbies: str = ""        # "爬山、摄影、围棋"
    interests: str = ""      # "AI、加密货币、独立游戏"
    learning: str = ""       # "Rust 编程、系统设计"
    work: str = ""           # "桌面自动化、Python 后端"
    interest_keywords: str = ""  # "鸣潮,原神,崩坏"（行为触发关键词）

    def is_empty(self) -> bool:
        return not (self.hobbies.strip() or self.interests.strip()
                   or self.learning.strip() or self.work.strip())

    def get_interest_keywords(self) -> list[str]:
        """解析逗号分隔的兴趣关键词列表"""
        if not self.interest_keywords.strip():
            return []
        return [kw.strip() for kw in self.interest_keywords.split(",") if kw.strip()]

    def to_prompt(self) -> str:
        """转成给 AI 的档案字符串"""
        if self.is_empty():
            return "（用户未填写档案，请自由发挥，问一些通用的、轻松的话题）"
        parts = []
        if self.hobbies.strip():
            parts.append(f"爱好：{self.hobbies.strip()}")
        if self.interests.strip():
            parts.append(f"兴趣：{self.interests.strip()}")
        if self.learning.strip():
            parts.append(f"学习：{self.learning.strip()}")
        if self.work.strip():
            parts.append(f"工作：{self.work.strip()}")
        return "\n".join(parts)


class QuestionGenerator:
    """问题生成器——用 AI 后端生成朋友式问题"""

    def __init__(self, backend: LLMBackend):
        self._backend = backend

    def set_backend(self, backend: LLMBackend):
        """热替换后端"""
        self._backend = backend

    def generate(self, profile: UserProfile, history: list[ProactiveQuestion]) -> Optional[ProactiveQuestion]:
        """生成一条新问题（失败返回 None）"""
        history_str = "\n".join(f"- {q.text}" for q in history[-10:]) or "（无）"
        sys_prompt = PROACTIVE_SYSTEM_PROMPT.format(
            user_profile=profile.to_prompt(),
            history=history_str,
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        # 简短 user 消息触发即可
        raw = self._backend.infer(sys_prompt, "请生成一个问题")
        if not raw:
            return None

        data = parse_intent_response(raw)
        if not data:
            return None

        text = (data.get("question") or "").strip()
        if not text:
            return None

        return ProactiveQuestion(
            text=text,
            category=data.get("category", "chat"),
            timestamp=datetime.now().timestamp(),
        )

    def generate_behavior_question(self, detected_topic: str, profile: UserProfile, history: list[ProactiveQuestion]) -> Optional[ProactiveQuestion]:
        """基于检测到的行为生成一条即时问题（失败返回 None）"""
        history_str = "\n".join(f"- {q.text}" for q in history[-10:]) or "（无）"
        sys_prompt = BEHAVIOR_SYSTEM_PROMPT.format(
            detected_topic=detected_topic,
            user_profile=profile.to_prompt(),
            history=history_str,
            now=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        raw = self._backend.infer(sys_prompt, f"用户打开了【{detected_topic}】，基于此生成一个问题")
        if not raw:
            return None

        data = parse_intent_response(raw)
        if not data:
            return None

        text = (data.get("question") or "").strip()
        if not text:
            return None

        return ProactiveQuestion(
            text=text,
            category=data.get("category", "hobby"),
            timestamp=datetime.now().timestamp(),
        )


class ProactiveScheduler(QObject):
    """主动嗅探调度器——按配置次数在剩余时间段随机触发

    算法：
    1. 算出今天到 23:59 的剩余分钟数
    2. 在剩余时间里随机分配 N 个时间点
    3. 每个时间点触发一次问题生成
    4. 跨天自动重置时间表
    """

    triggered = Signal(ProactiveQuestion)   # 有新问题生成
    schedule_updated = Signal(dict)          # 调度信息更新（剩余次数、下次时间等）
    log_signal = Signal(str)

    def __init__(self, generator: QuestionGenerator,
                 history: deque[ProactiveQuestion],
                 parent=None):
        super().__init__(parent)
        self._generator = generator
        self._history = history
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._enabled = False
        self._daily_count = 3
        self._fired_today = 0
        self._current_day = datetime.now().date()
        self._schedule: list[float] = []  # 时间戳列表
        self._profile = UserProfile()

    # ---- 配置 ----
    def set_profile(self, profile: UserProfile):
        self._profile = profile

    def set_daily_count(self, n: int):
        n = max(0, min(n, 20))
        self._daily_count = n

    def profile(self) -> UserProfile:
        return self._profile

    def daily_count(self) -> int:
        return self._daily_count

    # ---- 启停 ----
    def start(self):
        if self._enabled:
            return
        self._enabled = True
        self._regenerate_schedule()
        self._timer.start(30 * 1000)  # 30 秒检查一次
        self.log_signal.emit(f"[主动嗅探] 已启动，每日 {self._daily_count} 次")
        self._emit_status()

    def stop(self):
        if not self._enabled:
            return
        self._enabled = False
        self._timer.stop()
        self._schedule.clear()
        self.log_signal.emit("[主动嗅探] 已停止")
        self._emit_status()

    def is_enabled(self) -> bool:
        return self._enabled

    # ---- 调度算法 ----
    def _regenerate_schedule(self):
        """重新生成今日剩余时间的时间槽"""
        now = datetime.now()
        end_of_day = now.replace(hour=23, minute=59, second=0, microsecond=0)
        remaining_minutes = max(1, int((end_of_day - now).total_seconds() / 60))

        # 剩余次数
        remaining_count = max(1, self._daily_count - self._fired_today)
        # 至少间隔 15 分钟
        if remaining_minutes < remaining_count * 15:
            remaining_count = max(1, remaining_minutes // 15)

        # 随机分布时间点
        slots = sorted(random.sample(range(1, remaining_minutes), remaining_count))
        base = now.timestamp()
        self._schedule = [base + slot * 60 for slot in slots]
        self.log_signal.emit(f"[主动嗅探] 今日剩余 {remaining_count} 次，时间槽已生成")

    def _tick(self):
        """30 秒检查一次"""
        if not self._enabled:
            return

        # 跨天重置
        today = datetime.now().date()
        if today != self._current_day:
            self._current_day = today
            self._fired_today = 0
            self._regenerate_schedule()
            self.log_signal.emit("[主动嗅探] 跨天重置")
            self._emit_status()
            return

        # 检查是否有时间点到期
        now_ts = datetime.now().timestamp()
        while self._schedule and self._schedule[0] <= now_ts:
            self._schedule.pop(0)
            self._fire_one()
            if self._fired_today >= self._daily_count:
                break

        self._emit_status()

    def _fire_one(self):
        """触发一次问题生成"""
        if self._fired_today >= self._daily_count:
            return
        self._fired_today += 1

        # 生成（带去重）
        for attempt in range(3):
            q = self._generator.generate(self._profile, list(self._history))
            if q is None:
                self.log_signal.emit("[主动嗅探] 生成失败（后端无响应）")
                return
            # 去重：与最近 20 条比对
            if not self._is_duplicate(q):
                self._history.append(q)
                # 历史最多保留 100 条
                while len(self._history) > 100:
                    self._history.popleft()
                self.log_signal.emit(f"[主动嗅探] 生成问题: {q.text}")
                self.triggered.emit(q)
                return
            self.log_signal.emit(f"[主动嗅探] 重复，重试 ({attempt + 1}/3)")

        self.log_signal.emit("[主动嗅探] 重试 3 次仍重复，跳过")

    def _is_duplicate(self, q: ProactiveQuestion) -> bool:
        """简单去重——前 N 条做相似度比对（子串包含）"""
        recent = list(self._history)[-20:]
        for prev in recent:
            if prev.text == q.text:
                return True
            # 子串包含也算重复
            if prev.text and (prev.text in q.text or q.text in prev.text):
                return True
        return False

    def _emit_status(self):
        next_ts = self._schedule[0] if self._schedule else None
        self.schedule_updated.emit({
            "enabled": self._enabled,
            "fired": self._fired_today,
            "total": self._daily_count,
            "next_at": next_ts,
            "remaining_slots": len(self._schedule),
        })

    # ---- 状态查询 ----
    def get_status(self) -> dict:
        next_ts = self._schedule[0] if self._schedule else None
        next_str = ""
        if next_ts:
            delta = next_ts - datetime.now().timestamp()
            if delta > 0:
                next_str = f"{int(delta // 60)} 分 {int(delta % 60)} 秒后"
        return {
            "enabled": self._enabled,
            "fired": self._fired_today,
            "total": self._daily_count,
            "next_in": next_str,
            "remaining": self._daily_count - self._fired_today,
        }

    def get_history(self) -> list[ProactiveQuestion]:
        return list(self._history)


# ---------------------------------------------------------------------------
# 与 Toast 系统打通
# ---------------------------------------------------------------------------
class ProactiveRunner(QObject):
    """把调度器生成的问题转成 Toast 展示"""

    def __init__(self, scheduler: ProactiveScheduler,
                 toast_manager: ToastManager, parent=None):
        super().__init__(parent)
        self._scheduler = scheduler
        self._toast_manager = toast_manager
        scheduler.triggered.connect(self._on_question)

    @Slot(object)
    def _on_question(self, q: ProactiveQuestion):
        # 转成 ToastIntent 喂给 ToastManager
        icon_map = {
            "work": "💼", "study": "📚", "hobby": "🎮", "chat": "💬",
        }
        intent = ToastIntent(
            intent=f"主动嗅探 - {q.category}",
            message=q.text,
            suggested_action="proactive_question",
            action_param=q.category,
        )
        self._toast_manager.show_toast(intent)


# ---------------------------------------------------------------------------
# 行为兴趣触发器（Behavior-Interest Matcher）
# ---------------------------------------------------------------------------
class BehaviorInterestMatcher(QObject):
    """监听上下文胶囊，当检测到用户行为匹配兴趣关键词时，立即触发主动对话"""

    triggered = Signal(ProactiveQuestion)  # 匹配到兴趣时立即触发
    log_signal = Signal(str)

    def __init__(self, generator: QuestionGenerator,
                 history: deque[ProactiveQuestion],
                 parent=None):
        super().__init__(parent)
        self._generator = generator
        self._history = history
        self._profile = UserProfile()
        # 冷却字典：{keyword: 上次触发时间戳}
        self._cooldown: dict[str, float] = {}
        self._cooldown_seconds = 300  # 5 分钟冷却
        self._enabled = False

    def set_profile(self, profile: UserProfile):
        self._profile = profile

    def set_enabled(self, enabled: bool):
        self._enabled = enabled
        if enabled:
            self.log_signal.emit("[行为触发] 已启用")
        else:
            self.log_signal.emit("[行为触发] 已停用")

    def is_enabled(self) -> bool:
        return self._enabled

    def on_capsule(self, capsule):
        """当收到新的 ContextCapsule 时调用（外部槽）"""
        if not self._enabled:
            return

        keywords = self._profile.get_interest_keywords()
        if not keywords:
            return

        # 获取待检测文本
        process_name = getattr(capsule, "process_name", "") or ""
        window_title = getattr(capsule, "foreground_window", "") or ""
        window_app = getattr(capsule, "foreground_app", "") or ""

        for kw in keywords:
            kw_lower = kw.lower()
            matched = False
            matched_text = ""

            # 进程名匹配
            if process_name and kw_lower in process_name.lower():
                matched = True
                matched_text = process_name
            # 窗口标题匹配
            elif window_title and kw_lower in window_title.lower():
                matched = True
                matched_text = window_title
            # 窗口进程名匹配
            elif window_app and kw_lower in window_app.lower():
                matched = True
                matched_text = window_app

            if matched:
                # 冷却检查
                now = time.time()
                last = self._cooldown.get(kw_lower, 0)
                if now - last < self._cooldown_seconds:
                    self.log_signal.emit(f"[行为触发] {kw} 冷却中，跳过")
                    continue

                self._cooldown[kw_lower] = now
                self._fire_behavior_question(kw, matched_text)
                break  # 一次只触发一个关键词

    def _fire_behavior_question(self, keyword: str, matched_text: str):
        """触发一次行为相关问题生成"""
        # 去重检查
        for prev in list(self._history)[-10:]:
            if keyword.lower() in prev.text.lower():
                self.log_signal.emit(f"[行为触发] {keyword} 近期已问过，跳过")
                return

        q = self._generator.generate_behavior_question(
            keyword, self._profile, list(self._history)
        )
        if q is None:
            self.log_signal.emit(f"[行为触发] {keyword} 生成失败（后端无响应）")
            return

        self._history.append(q)
        while len(self._history) > 100:
            self._history.popleft()

        self.log_signal.emit(f"[行为触发] 检测到 {keyword} → {q.text}")
        self.triggered.emit(q)
