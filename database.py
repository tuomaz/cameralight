import sqlite3
import time
from typing import Optional


class Database:
    def __init__(self, db_path: str = "data.db") -> None:
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _init_db(self) -> None:
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = self.conn.cursor()
        cursor.execute("CREATE TABLE IF NOT EXISTS history (ts INTEGER, value REAL)")
        self.conn.commit()

    def insert_history(self, value: float) -> None:
        if not self.conn:
            raise ConnectionError("Database not connected")
        current_timestamp = int(time.time())
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO history (ts, value) VALUES (?, ?)", (current_timestamp, value)
        )
        self.conn.commit()

    def get_delayed_value(self, delay_hours: float = 22.5) -> Optional[float]:
        if not self.conn:
            raise ConnectionError("Database not connected")
        delayed_ts = int(time.time()) - int(delay_hours * 60 * 60)
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT value FROM history WHERE ts < ? ORDER BY ts DESC LIMIT 1",
            (delayed_ts,),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
