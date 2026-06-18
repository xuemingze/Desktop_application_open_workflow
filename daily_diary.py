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