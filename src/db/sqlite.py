import json
import sqlite3
import uuid
from datetime import datetime
from typing import Any


JOB_STEP_DEFINITIONS = [
    ("transcribing", 1, "Whisper transcribiendo", "Whisper local estÃ¡ leyendo el audio y generando segmentos"),
    ("summarizing", 2, "Generando resumen", "LLM resume la reunión y detecta decisiones"),
    ("extracting", 3, "Extrayendo action items", "LLM identifica tareas, owners y fechas"),
    ("reporting", 4, "Construyendo reporte", "Se genera el markdown final de la reunión"),
    ("indexing", 5, "Indexando en Chroma", "Los segmentos se preparan para búsqueda semántica"),
    ("saving", 6, "Guardando en SQLite", "Se persisten reunión y tasks en base de datos"),
]

JOB_STEP_MAP = {step_key: (sort_order, label, default_detail) for step_key, sort_order, label, default_detail in JOB_STEP_DEFINITIONS}


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
                stage       TEXT,
                stage_detail TEXT,
                meeting_id  TEXT,
                error       TEXT,
                created_at  TEXT DEFAULT (datetime('now')),
                finished_at TEXT
            );
            CREATE TABLE IF NOT EXISTS job_steps (
                job_id      TEXT NOT NULL,
                step_key    TEXT NOT NULL,
                sort_order  INTEGER NOT NULL,
                label       TEXT NOT NULL,
                detail      TEXT,
                status      TEXT NOT NULL DEFAULT 'pending',
                updated_at  TEXT DEFAULT (datetime('now')),
                PRIMARY KEY (job_id, step_key)
            );
            CREATE TABLE IF NOT EXISTS job_logs (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id      TEXT NOT NULL,
                timestamp   TEXT NOT NULL,
                level       TEXT NOT NULL,
                message     TEXT NOT NULL
            );
        """)
        self.conn.commit()
        self._migrate()

    def _migrate(self):
        """Add columns introduced after initial release."""
        try:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN stage TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass  # column already exists
        try:
            self.conn.execute("ALTER TABLE jobs ADD COLUMN stage_detail TEXT")
            self.conn.commit()
        except sqlite3.OperationalError:
            pass

    # --- Jobs ---
    def create_job(self) -> str:
        job_id = str(uuid.uuid4())
        self.conn.execute(
            "INSERT INTO jobs (id, stage, stage_detail) VALUES (?, ?, ?)",
            (job_id, "queued", "Trabajo recibido. Preparando Whisper y el pipeline local"),
        )
        self._seed_job_steps(job_id)
        self.add_job_log(job_id, "info", "Job creado y en cola para procesamiento")
        self.add_job_log(job_id, "info", "Esperando a que arranque la transcripción inicial")
        self.conn.commit()
        return job_id

    def get_job(self, job_id: str) -> dict | None:
        row = self.conn.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
        return dict(row) if row else None

    def complete_job(self, job_id: str, meeting_id: str):
        if self.get_job(job_id):
            self._mark_previous_steps_done(job_id, len(JOB_STEP_DEFINITIONS) + 1)
        self.add_job_log(job_id, "info", "Pipeline completado y reunión persistida correctamente")
        self.conn.execute(
            "UPDATE jobs SET status='done', meeting_id=?, stage='completed', stage_detail=?, finished_at=? WHERE id=?",
            (meeting_id, "Pipeline completado", datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    def update_job_stage(self, job_id: str, stage: str, detail: str | None = None):
        sort_order, label, default_detail = JOB_STEP_MAP.get(stage, (0, stage, detail or stage))
        self._mark_previous_steps_done(job_id, sort_order)
        self.upsert_job_step(job_id, stage, detail or default_detail, "active")
        self.add_job_log(job_id, "info", f"{label}: {detail or default_detail}")
        self.conn.execute("UPDATE jobs SET stage=?, stage_detail=? WHERE id=?", (stage, detail or label, job_id))
        self.conn.commit()

    def fail_job(self, job_id: str, error: str):
        job = self.get_job(job_id)
        if job and job.get("stage"):
            self.upsert_job_step(job_id, job["stage"], error, "error")
        self.add_job_log(job_id, "error", error)
        self.conn.execute(
            "UPDATE jobs SET status='error', error=?, stage_detail=?, finished_at=? WHERE id=?",
            (error, error, datetime.now().isoformat(), job_id),
        )
        self.conn.commit()

    def list_job_steps(self, job_id: str) -> list[dict]:
        rows = self.conn.execute(
            "SELECT step_key, sort_order, label, detail, status FROM job_steps WHERE job_id = ? ORDER BY sort_order",
            (job_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def add_job_log(self, job_id: str, level: str, message: str):
        self.conn.execute(
            "INSERT INTO job_logs (job_id, timestamp, level, message) VALUES (?, ?, ?, ?)",
            (job_id, datetime.now().isoformat(), level, message),
        )

    def list_job_logs(self, job_id: str, limit: int = 20) -> list[dict]:
        rows = self.conn.execute(
            "SELECT timestamp, level, message FROM job_logs WHERE job_id = ? ORDER BY id DESC LIMIT ?",
            (job_id, limit),
        ).fetchall()
        return [dict(row) for row in reversed(rows)]

    def upsert_job_step(self, job_id: str, step_key: str, detail: str | None, status: str):
        sort_order, label, default_detail = JOB_STEP_MAP.get(step_key, (999, step_key, detail or step_key))
        self.conn.execute(
            """
            INSERT INTO job_steps (job_id, step_key, sort_order, label, detail, status, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(job_id, step_key) DO UPDATE SET
                detail=excluded.detail,
                status=excluded.status,
                updated_at=excluded.updated_at
            """,
            (job_id, step_key, sort_order, label, detail or default_detail, status, datetime.now().isoformat()),
        )

    def _seed_job_steps(self, job_id: str):
        for step_key, sort_order, label, default_detail in JOB_STEP_DEFINITIONS:
            self.conn.execute(
                """
                INSERT OR IGNORE INTO job_steps (job_id, step_key, sort_order, label, detail, status)
                VALUES (?, ?, ?, ?, ?, 'pending')
                """,
                (job_id, step_key, sort_order, label, default_detail),
            )

    def _mark_previous_steps_done(self, job_id: str, current_sort_order: int):
        self.conn.execute(
            """
            UPDATE job_steps
            SET status='done', updated_at=?
            WHERE job_id = ? AND sort_order < ? AND status IN ('pending', 'active')
            """,
            (datetime.now().isoformat(), job_id, current_sort_order),
        )

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
