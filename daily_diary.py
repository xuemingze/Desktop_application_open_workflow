# daily_diary.py
# 功能: 定时抓取 SQLite 数据，生成 Markdown 日记，触发气泡

import sqlite3
from datetime import datetime
from pathlib import Path
from PySide6.QtCore import QObject, QTimer, Signal
from log_bus import log_bus

from activity_log import ActivityLogDB

def extract_daily_summary(db: ActivityLogDB, target_date: datetime = None) -> tuple[str, str]:
    """提取某日的【分类汇总】和【Top窗口】"""
    if target_date is None:
        target_date = datetime.now()
        
    date_str = target_date.strftime("%Y-%m-%d")
    ts_start = target_date.replace(hour=0, minute=0, second=0).timestamp()
    ts_end = target_date.replace(hour=23, minute=59, second=59).timestamp()
    table_name = db._get_table_name(ts_start)
    
    # 因为不能确定表是否一定存在，用 try
    try:
        conn = db._get_conn()
        cursor = conn.cursor()
        
        # 1. 分类汇总统计
        cursor.execute(f"""
            SELECT category, SUM(duration_s) 
            FROM {table_name} 
            WHERE date_str = ?
            GROUP BY category
            ORDER BY SUM(duration_s) DESC
        """, (date_str,))
        
        category_stats = []
        for cat, dur in cursor.fetchall():
            hours, remainder = divmod(dur, 3600)
            mins = remainder // 60
            dur_str = f"{int(hours)}h {int(mins)}m" if hours > 0 else f"{int(mins)}m"
            category_stats.append(f"- {cat} 时长: {dur_str}")
            
        # 2. 活跃窗口 TOP 10 (剔除 IDLE)
        cursor.execute(f"""
            SELECT window_title, SUM(duration_s) 
            FROM {table_name} 
            WHERE date_str = ? AND is_idle = 0
            GROUP BY window_title
            HAVING SUM(duration_s) > 30
            ORDER BY SUM(duration_s) DESC
            LIMIT 10
        """, (date_str,))
        
        top_windows = []
        for title, dur in cursor.fetchall():
            mins = int(dur // 60)
            # 截取标题防超长 Token
            short_title = title[:30] + "..." if len(title) > 30 else title
            top_windows.append(f"- 停留 {mins}m | {short_title}")
            
        return "\n".join(category_stats), "\n".join(top_windows)
        
    except (sqlite3.OperationalError, sqlite3.DatabaseError) as e:
        log_bus.emit(f"[Diary] 提取今日数据异常: {e}")
        return "今日暂无分类数据。", "今日暂无窗口记录。"


class DiaryScheduler(QObject):
    """1 分钟对表一次的调度器"""
    trigger_diary_prompt = Signal(str)  # 抛出信号给 UI 弹气泡 (附带 date_str)

    def __init__(self, parent=None, first_hour=22, max_prompts=2):
        super().__init__(parent)
        self.first_hour = first_hour
        self.max_prompts = max_prompts
        
        self._timer = QTimer(self)
        self._timer.timeout.connect(self._check_trigger)
        self._timer.start(60_000) # 1 分钟检测一次
        
        self._prompts_today = 0
        self._last_date_str = ""

    def _check_trigger(self):
        now = datetime.now()
        date_str = now.strftime("%Y-%m-%d")
        
        # 跨日重置计数器
        if date_str != self._last_date_str:
            self._prompts_today = 0
            self._last_date_str = date_str

        if self._prompts_today >= self.max_prompts:
            return
            
        hour = now.hour
        minute = now.minute
        
        # >= 22:30 或 > 22 都可以触发
        if (hour == self.first_hour and minute >= 30) or hour > self.first_hour:
            self._prompts_today += 1
            self.trigger_diary_prompt.emit(date_str)


DIARY_PROMPT_TEMPLATE = """你是用户的私人复盘助手。用户使用 minimax 大模型。

【今日活动统计】（按 category 汇总）
{category_stats}

【今日活跃窗口 TOP 10】（按时长排序）
{top_windows}

【任务要求】
1. 用私人日记口吻，第二人称 "你今天..."
2. 推断"工作重心"（1-3 个关键词）
3. 识别"摸鱼时段"（[娱乐]/[沟通协作] 集中时段）
4. 重点评价"专注度"（[IDLE] 段越长越散）

【分类标签说明】
- [IDLE] = 键鼠超过 3 分钟无操作（不一定代表摸鱼，可能在吃饭/会议/午休/思考）
- [开发编程] [系统运维] = 工作相关
- [娱乐] [沟通协作] 占比高则需提醒

【输出格式】纯 Markdown，不要代码块包裹
"""

def build_diary_prompt(db: ActivityLogDB, target_date: datetime = None) -> tuple[str, str]:
    """返回 (system_prompt, user_prompt) 供外部调用 LLM"""
    cat_stats, top_wins = extract_daily_summary(db, target_date)
    
    sys_prompt = DIARY_PROMPT_TEMPLATE.format(
        category_stats=cat_stats,
        top_windows=top_wins
    )
    return sys_prompt, "请生成今日的 Markdown 复盘日记。"


def _format_duration(seconds: float) -> str:
    seconds = max(0, float(seconds or 0))
    hours, remainder = divmod(seconds, 3600)
    mins = remainder // 60
    if hours >= 1:
        return f"{int(hours)}h {int(mins)}m"
    return f"{int(mins)}m"


def extract_chunk_summary(db: ActivityLogDB, start_ts: float, end_ts: float) -> tuple[str, str, str]:
    """提取一个时间切片的本地聚合摘要，先 GroupBy 再交给 LLM，避免 Token 爆炸。"""
    try:
        conn = db._get_conn()
        tables = [
            r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'activity_%'"
            ).fetchall()
            if db._parse_activity_table_month(r[0]) is not None
        ]
        category_totals: dict[str, float] = {}
        app_totals: dict[str, float] = {}
        window_totals: dict[str, float] = {}
        total_active = 0.0
        record_count = 0

        for table in tables:
            rows = conn.execute(f"""
                SELECT exe_name, window_title, category, duration_s
                FROM {table}
                WHERE is_idle = 0 AND start_ts <= ? AND COALESCE(end_ts, start_ts) >= ?
            """, (end_ts, start_ts)).fetchall()
            for app, title, cat, dur in rows:
                dur = float(dur or 0)
                if dur <= 0:
                    continue
                record_count += 1
                total_active += dur
                category_totals[cat or "[其他]"] = category_totals.get(cat or "[其他]", 0.0) + dur
                app_totals[app or "unknown"] = app_totals.get(app or "unknown", 0.0) + dur
                short_title = (title or "").strip()[:60] or "(无标题)"
                window_totals[short_title] = window_totals.get(short_title, 0.0) + dur

        def top_lines(data: dict[str, float], limit: int = 8) -> str:
            items = sorted(data.items(), key=lambda kv: kv[1], reverse=True)[:limit]
            return "\n".join(f"- {name}: {_format_duration(sec)}" for name, sec in items) or "- 暂无"

        meta = (
            f"切片时间: {datetime.fromtimestamp(start_ts).strftime('%Y-%m-%d %H:%M')}"
            f" - {datetime.fromtimestamp(end_ts).strftime('%H:%M')}\n"
            f"有效记录数: {record_count}\n"
            f"活跃总时长: {_format_duration(total_active)}"
        )
        grouped = (
            "## 分类汇总\n" + top_lines(category_totals) + "\n\n"
            "## 应用汇总\n" + top_lines(app_totals) + "\n\n"
            "## Top 窗口\n" + top_lines(window_totals)
        )
        fallback = f"# 工作切片摘要\n\n{meta}\n\n{grouped}\n"
        return meta, grouped, fallback
    except Exception as e:
        log_bus.emit(f"[Chunk] 提取切片摘要失败: {e}")
        return "切片数据提取失败", "暂无", f"# 工作切片摘要\n\n提取失败: {e}\n"


CHUNK_PROMPT_TEMPLATE = """你是用户的私人工作记忆整理助手。

下面是一段连续工作切片的本地聚合数据，已经由程序先做了 GroupBy 压缩。

【切片元数据】
{meta}

【本地聚合】
{grouped}

请提取：
1. 核心任务：用户这段时间主要在做什么
2. 动作倾向：是在开发、排错、沟通、娱乐还是资料整理
3. 可能的上下文线索：涉及哪些应用/窗口
4. 下一步建议：一句话即可

输出纯 Markdown，不要代码块。
"""


def build_chunk_prompt(db: ActivityLogDB, start_ts: float, end_ts: float) -> tuple[str, str, str]:
    """返回 (system_prompt, user_prompt, fallback_markdown)。"""
    meta, grouped, fallback = extract_chunk_summary(db, start_ts, end_ts)
    sys_prompt = CHUNK_PROMPT_TEMPLATE.format(meta=meta, grouped=grouped)
    return sys_prompt, "请生成这段工作切片的中期记忆 Markdown。", fallback