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

    def _ensure_table(self, table_name: str):
        """确保目标月份的数据表存在"""
        if table_name in self._created_tables:
            return

        conn = self._get_conn()
        # 注意：sqlite 不能用参数化绑定表名，必须用字符串拼接 (已内部控制 table_name 格式，安全)
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
        # 创建索引优化查询
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
            # 动态计算 duration_s
            conn.execute(f"""
                UPDATE {table_name} 
                SET end_ts = ?, duration_s = ? - start_ts 
                WHERE id = ?
            """, (end_ts, end_ts, record_id))
            conn.commit()

    def close_record(self, table_name: str, record_id: int, end_ts: float):
        """关闭一条记录 (语义上与 update_end 一致，保留接口用于后续扩展)"""
        self.update_end(table_name, record_id, end_ts)