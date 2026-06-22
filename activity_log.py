# activity_log.py
# 功能: 线程安全的 SQLite 写入器（自带锁与 threading.local，WAL 模式）

import sqlite3
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

class ActivityLogDB:
    def __init__(self, db_dir: Path):
        self.db_path = db_dir / "activity_log.db"
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self._lock = threading.Lock()     # 保护写操作与建表
        self._local = threading.local()   # 线程局部存储，隔离 connection
        self._created_tables = set()      # 缓存已确认存在的表名
        self.purge_old_tables(retention_months=3)

    def _get_conn(self) -> sqlite3.Connection:
        """获取当前线程的专属数据库连接"""
        if not hasattr(self._local, "conn"):
            # timeout=5：获取写锁最多等待5秒，防止死锁卡死
            conn = sqlite3.connect(self.db_path, timeout=5.0)
            # 极速模式：开启 WAL（预写日志），读写互不阻塞
            conn.execute("PRAGMA journal_mode=WAL;")
            conn.execute("PRAGMA synchronous=NORMAL;")
            self._local.conn = conn
        return self._local.conn

    def _get_table_name(self, ts: float) -> str:
        """根据时间戳计算按月分表的表名 (如: activity_2026_06)"""
        dt = datetime.fromtimestamp(ts)
        return f"activity_{dt.strftime('%Y_%m')}"

    @staticmethod
    def _month_index(year: int, month: int) -> int:
        return year * 12 + month

    @classmethod
    def _parse_activity_table_month(cls, table_name: str) -> Optional[int]:
        """解析 activity_YYYY_MM 表名为月份序号，非法表名返回 None。"""
        parts = str(table_name or "").split("_")
        if len(parts) != 3 or parts[0] != "activity":
            return None
        try:
            year = int(parts[1])
            month = int(parts[2])
        except ValueError:
            return None
        if year < 2000 or month < 1 or month > 12:
            return None
        return cls._month_index(year, month)

    def purge_old_tables(self, retention_months: int = 3, now: Optional[datetime] = None) -> list[str]:
        """清理超过保留期的月分表。

        Activity 数据按月分表，过期数据直接 DROP TABLE，避免单表 DELETE 带来的碎片和慢查询。
        retention_months=3 表示保留当前月及最近 3 个月内的表。
        """
        retention_months = max(1, int(retention_months or 3))
        now = now or datetime.now()
        current_idx = self._month_index(now.year, now.month)
        cutoff_idx = current_idx - retention_months
        dropped: list[str] = []

        with self._lock:
            conn = self._get_conn()
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'activity_%'"
            ).fetchall()
            for (table_name,) in rows:
                table_idx = self._parse_activity_table_month(table_name)
                if table_idx is None or table_idx >= cutoff_idx:
                    continue
                conn.execute(f"DROP TABLE IF EXISTS {table_name}")
                dropped.append(table_name)
                self._created_tables.discard(table_name)
            conn.commit()
        return dropped

    def _ensure_table(self, table_name: str):
        """确保目标月份的数据表存在"""
        if table_name in self._created_tables:
            return

        conn = self._get_conn()
        conn.execute(f"""
            CREATE TABLE IF NOT EXISTS {table_name} (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                start_ts    REAL NOT NULL,
                end_ts      REAL,
                duration_s  REAL DEFAULT 0,
                exe_name    TEXT,
                window_title TEXT,
                category    TEXT,
                is_idle     INTEGER DEFAULT 0,
                date_str    TEXT,
                hour_bucket INTEGER
            )
        """)
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_date ON {table_name}(date_str)")
        conn.execute(f"CREATE INDEX IF NOT EXISTS idx_{table_name}_ts ON {table_name}(start_ts)")
        conn.commit()
        self._created_tables.add(table_name)

    def open_record(self, ts: float, title: str, app: str, category: str, is_idle: int = 0) -> Tuple[str, int]:
        """开启一条新记录，返回 (表名, 记录ID)"""
        table_name = self._get_table_name(ts)

        with self._lock:
            self._ensure_table(table_name)
            conn = self._get_conn()

            dt = datetime.fromtimestamp(ts)
            date_str = dt.strftime("%Y-%m-%d")
            hour_bucket = dt.hour

            cursor = conn.cursor()
            cursor.execute(f"""
                INSERT INTO {table_name}
                (start_ts, end_ts, duration_s, exe_name, window_title, category, is_idle, date_str, hour_bucket)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (ts, ts, 0, app, title, category, is_idle, date_str, hour_bucket))

            record_id = cursor.lastrowid
            conn.commit()
            return table_name, record_id

    def update_end(self, table_name: str, record_id: int, end_ts: float):
        """延长记录的结束时间 (状态合并)"""
        if not table_name or not record_id:
            return

        with self._lock:
            conn = self._get_conn()
            conn.execute(f"""
                UPDATE {table_name}
                SET end_ts = ?, duration_s = ? - start_ts
                WHERE id = ?
            """, (end_ts, end_ts, record_id))
            conn.commit()

    def close_record(self, table_name: str, record_id: int, end_ts: float):
        """关闭一条记录 (语义上与 update_end 一致，保留接口用于后续扩展)"""
        self.update_end(table_name, record_id, end_ts)

    def query_latest(self, limit: int = 10, ref_ts: Optional[float] = None) -> list[dict]:
        """查询最近 N 条记录（跨全表），返回 dict 列表"""
        ref_ts = ref_ts or datetime.now().timestamp()
        # 收集最近 3 个月的表
        tables: list[str] = []
        for offset in range(3):
            dt = datetime.fromtimestamp(ref_ts)
            year = dt.year
            month = dt.month - offset
            while month <= 0:
                month += 12
                year -= 1
            table = f"activity_{year}_{month:02d}"
            conn = self._get_conn()
            cursor = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (table,)
            ).fetchone()
            if cursor:
                tables.append(table)

        if not tables:
            return []

        # 用 UNION ALL 跨表查询（仅最新）
        union = " UNION ALL ".join(
            f"SELECT *, '{t}' as _tbl FROM {t}" for t in tables
        )
        sql = f"""
            SELECT exe_name, window_title, category, is_idle, date_str, start_ts, end_ts, duration_s
            FROM ({union})
            ORDER BY start_ts DESC
            LIMIT ?
        """
        try:
            conn = self._get_conn()
            cursor = conn.execute(sql, (limit,))
            rows = cursor.fetchall()
            cols = ["exe_name", "window_title", "category", "is_idle", "date_str", "start_ts", "end_ts", "duration_s"]
            return [dict(zip(cols, r)) for r in rows]
        except Exception:
            return []
