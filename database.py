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
        cursor.execute(
            "CREATE TABLE IF NOT EXISTS history (ts INTEGER, sensor_name TEXT, value REAL)"
        )

        # Migration: Add sensor_name if it doesn't exist (for older databases)
        cursor.execute("PRAGMA table_info(history)")
        columns = [column[1] for column in cursor.fetchall()]
        if "sensor_name" not in columns:
            cursor.execute("ALTER TABLE history ADD COLUMN sensor_name TEXT")
            cursor.execute("UPDATE history SET sensor_name = 'default'")

        cursor.execute(
            "CREATE INDEX IF NOT EXISTS idx_history_sensor_ts ON history(sensor_name, ts)"
        )
        self.conn.commit()

    def insert_history(self, sensor_name: str, value: float) -> None:
        if not self.conn:
            raise ConnectionError("Database not connected")
        current_timestamp = int(time.time())
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO history (ts, sensor_name, value) VALUES (?, ?, ?)",
            (current_timestamp, sensor_name, value),
        )
        self.conn.commit()

    def get_delayed_value(self, sensor_name: str, delay_seconds: int) -> Optional[float]:
        if not self.conn:
            raise ConnectionError("Database not connected")
        delayed_ts = int(time.time()) - delay_seconds
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT value FROM history WHERE sensor_name = ? AND ts < ? ORDER BY ts DESC LIMIT 1",
            (sensor_name, delayed_ts),
        )
        row = cursor.fetchone()
        if row:
            return row[0]
        return None

    def close(self) -> None:
        if self.conn:
            self.conn.close()
            self.conn = None
