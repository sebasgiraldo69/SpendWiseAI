import os
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent

def get_connection():
    db_file = Path(os.getenv('SPENDWISE_DB_PATH', str(ROOT / 'data' / 'spendwise_v2.db')))
    db_file.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_file, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def initialize_database():
    with get_connection() as conn:
        conn.execute("""
        CREATE TABLE IF NOT EXISTS budgets (
            id TEXT PRIMARY KEY,
            year INTEGER NOT NULL CHECK(year BETWEEN 2000 AND 2200),
            month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
            income REAL,
            status TEXT NOT NULL CHECK(status IN ('draft', 'confirmed')),
            source_mode TEXT NOT NULL CHECK(source_mode IN ('live', 'fixture', 'manual')),
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL,
            UNIQUE(year, month)
        );
        """)
        
        conn.execute("""
        CREATE TABLE IF NOT EXISTS movements (
            id TEXT PRIMARY KEY,
            budget_id TEXT NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
            description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 200),
            amount REAL NOT NULL,
            category TEXT NOT NULL,
            source_quote TEXT,
            origin TEXT NOT NULL CHECK(origin IN ('interpreted', 'manual', 'scenario')),
            created_at TEXT NOT NULL
        );
        """)

def get_budget_by_period(year: int, month: int):
    with get_connection() as conn:
        cursor = conn.execute("SELECT id FROM budgets WHERE year = ? AND month = ? AND status = 'confirmed'", (year, month))
        row = cursor.fetchone()
        return row['id'] if row else None

def get_budget(budget_id: str):
    with get_connection() as conn:
        cursor = conn.execute("SELECT * FROM budgets WHERE id = ?", (budget_id,))
        budget_row = cursor.fetchone()
        if not budget_row:
            return None
            
        budget = dict(budget_row)
        cursor = conn.execute("SELECT * FROM movements WHERE budget_id = ? ORDER BY created_at ASC", (budget_id,))
        budget['movements'] = [dict(row) for row in cursor.fetchall()]
        return budget

def list_budgets(year: int = None):
    with get_connection() as conn:
        query = (
            "SELECT b.id, b.year, b.month, b.income, b.status, b.source_mode, "
            "b.created_at, b.updated_at, "
            "COUNT(m.id) as movement_count, "
            "COALESCE(SUM(m.amount), 0) as total_expense "
            "FROM budgets b "
            "LEFT JOIN movements m ON b.id = m.budget_id "
        )
        params = []
        if year is not None:
            query += " WHERE b.year = ?"
            params.append(year)
            
        query += " GROUP BY b.id ORDER BY b.year DESC, b.month DESC"
        cursor = conn.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

def create_budget(year, month, income, movements, source_mode):
    budget_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).isoformat()
    
    movement_rows = []
    for mov in movements:
        movement_rows.append((
            str(uuid.uuid4()),
            budget_id,
            mov.get('description') or mov.get('descripcion'),
            mov.get('amount') or mov.get('valor'),
            mov.get('category') or mov.get('categoria'),
            mov.get('source_quote'),
            mov.get('origin', 'manual'),
            now_utc
        ))
        
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO budgets 
               (id, year, month, income, status, source_mode, created_at, updated_at) 
               VALUES (?, ?, ?, ?, 'confirmed', ?, ?, ?)""",
            (budget_id, year, month, income, source_mode, now_utc, now_utc)
        )
        conn.executemany(
            """INSERT INTO movements 
               (id, budget_id, description, amount, category, source_quote, origin, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            movement_rows
        )
        
    return get_budget(budget_id)

def update_budget(budget_id, income, movements):
    now_utc = datetime.now(timezone.utc).isoformat()
    
    movement_rows = []
    for mov in movements:
        movement_rows.append((
            str(uuid.uuid4()),
            budget_id,
            mov.get('description') or mov.get('descripcion'),
            mov.get('amount') or mov.get('valor'),
            mov.get('category') or mov.get('categoria'),
            mov.get('source_quote'),
            mov.get('origin', 'manual'),
            now_utc
        ))
        
    with get_connection() as conn:
        conn.execute("UPDATE budgets SET income = ?, updated_at = ? WHERE id = ?", (income, now_utc, budget_id))
        conn.execute("DELETE FROM movements WHERE budget_id = ?", (budget_id,))
        conn.executemany(
            """INSERT INTO movements 
               (id, budget_id, description, amount, category, source_quote, origin, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            movement_rows
        )
        
    return get_budget(budget_id)

def delete_budget(budget_id):
    with get_connection() as conn:
        cursor = conn.execute("DELETE FROM budgets WHERE id = ?", (budget_id,))
        return cursor.rowcount > 0

