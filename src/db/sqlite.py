import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any


class Database:
    def __init__(self, path: str = "data/meetings.db"):
        self.conn = sqlite3.connect(path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS meetings (
                id         TEXT PRIMARY KEY,
                title      TEXT NOT NULL,
                date       TEXT NOT NULL,
                duration_s REAL,
                speakers   TEXT,
                decisions  TEXT,
                summary    TEXT,
                report_md  TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            );
            CREATE TABLE IF NOT EXISTS action_items (
                id         TEXT PRIMARY KEY,
                meeting_id TEXT REFERENCES meetings(id),
                task       TEXT NOT NULL,
                owner      TEXT,
                due_date   TEXT,
                status     TEXT DEFAULT 'pending'
            );
            CREATE TABLE IF NOT EXISTS jobs (
                id          TEXT PRIMARY KEY,
                status      TEXT DEFAULT 'processing',
                meeting_id  TEXT,
                error       TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                finished_at TEXT
            );
        """)
        self.conn.commit()

    # --- Jobs ---
    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self.conn.execute("INSERT INTO jobs (id) VALUES (?)", (job_id,))
        self.conn.commit()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def complete_job(self, job_id: str, meeting_id: str):
        self.conn.execute(
            "UPDATE jobs SET status='done', meeting_id=?, finished_at=? WHERE id=?",
            (meeting_id, datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    def fail_job(self, job_id: str, error: str):
        self.conn.execute(
            "UPDATE jobs SET status='error', error=?, finished_at=? WHERE id=?",
            (error, datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    # --- Meetings ---
    def create_meeting(self, data: dict[str, Any]):
        self.conn.execute(
            "INSERT INTO meetings (id, title, date, duration_s, speakers, decisions, summary, report_md) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                data["id"], data["title"], data["date"],
                data.get("duration_s"),
                json.dumps(data.get("speakers", [])),
                json.dumps(data.get("decisions", [])),
                data.get("summary", ""),
                data.get("report_md", ""),
            ),
        )
        self.conn.commit()

    def get_meeting(self, meeting_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM meetings WHERE id = ?", (meeting_id,)).fetchone()
        if not row:
            return None
        m = dict(row)
        m["speakers"] = json.loads(m["speakers"] or "[]")
        m["decisions"] = json.loads(m["decisions"] or "[]")
        return m

    def list_meetings(self) -> list[dict]:
        rows = self.conn.execute("SELECT * FROM meetings ORDER BY created_at DESC").fetchall()
        result = []
        for row in rows:
            m = dict(row)
            m["speakers"] = json.loads(m["speakers"] or "[]")
            m["decisions"] = json.loads(m["decisions"] or "[]")
            result.append(m)
        return result

    # --- Action Items ---
    def create_action_item(self, data: dict[str, Any]):
        self.conn.execute(
            "INSERT INTO action_items (id, meeting_id, task, owner, due_date, status) VALUES (?,?,?,?,?,?)",
            (data["id"], data["meeting_id"], data["task"],
             data.get("owner"), data.get("due_date"), data.get("status", "pending")),
        )
        self.conn.commit()

    def get_action_item(self, item_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM action_items WHERE id = ?", (item_id,)).fetchone()
        return dict(row) if row else None

    def list_action_items(self, meeting_id: str | None = None,
                          status: str | None = None, owner: str | None = None) -> list[dict]:
        query = "SELECT * FROM action_items WHERE 1=1"
        params: list = []
        if meeting_id:
            query += " AND meeting_id = ?"
            params.append(meeting_id)
        if status:
            query += " AND status = ?"
            params.append(status)
        if owner:
            query += " AND owner = ?"
            params.append(owner)
        return [dict(r) for r in self.conn.execute(query, params).fetchall()]

    def update_action_item_status(self, item_id: str, status: str):
        self.conn.execute("UPDATE action_items SET status = ? WHERE id = ?", (status, item_id))
        self.conn.commit()
