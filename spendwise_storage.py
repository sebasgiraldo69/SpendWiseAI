"""SQLite persistence layer. No model, no HTTP, no business logic."""
import os
import sqlite3
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from spendwise_core import money, CATEGORIES

ROOT = Path(__file__).resolve().parent

def _db_path():
    """Resolve database file path from env or default."""
    return Path(os.getenv('SPENDWISE_DB_PATH', str(ROOT / 'data' / 'spendwise.db')))

def get_connection(path=None):
    """Open a connection with FK enforcement and 5s timeout."""
    db_file = Path(path) if path else _db_path()
    db_file.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(db_file, timeout=5, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 1500")
    return conn

def initialize_database(conn=None):
    """Create tables and indexes. Safe to call on every startup."""
    close_conn = False
    if conn is None:
        conn = get_connection()
        close_conn = True
        
    try:
        with conn:
            conn.execute("""
            CREATE TABLE IF NOT EXISTS profiles (
              id TEXT PRIMARY KEY,
              display_name TEXT NOT NULL CHECK(length(display_name) BETWEEN 1 AND 80),
              profile_type TEXT NOT NULL CHECK(profile_type = 'demo'),
              created_at TEXT NOT NULL
            );
            """)
            
            conn.execute("""
            CREATE TABLE IF NOT EXISTS budgets (
              id TEXT PRIMARY KEY,
              profile_id TEXT NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
              year INTEGER NOT NULL CHECK(year BETWEEN 2000 AND 2200),
              month INTEGER NOT NULL CHECK(month BETWEEN 1 AND 12),
              income TEXT,
              currency TEXT NOT NULL DEFAULT 'COP' CHECK(currency = 'COP'),
              status TEXT NOT NULL CHECK(status IN ('draft', 'confirmed')),
              source_mode TEXT NOT NULL CHECK(source_mode IN ('live', 'fixture', 'manual')),
              created_at TEXT NOT NULL,
              updated_at TEXT NOT NULL,
              UNIQUE(profile_id, year, month)
            );
            """)
            
            conn.execute("""
            CREATE TABLE IF NOT EXISTS movements (
              id TEXT PRIMARY KEY,
              budget_id TEXT NOT NULL REFERENCES budgets(id) ON DELETE CASCADE,
              description TEXT NOT NULL CHECK(length(description) BETWEEN 1 AND 200),
              amount TEXT NOT NULL,
              category TEXT NOT NULL,
              source_quote TEXT,
              origin TEXT NOT NULL CHECK(origin IN ('interpreted', 'manual', 'scenario')),
              created_at TEXT NOT NULL
            );
            """)
            
            conn.execute("CREATE INDEX IF NOT EXISTS idx_budgets_profile_period ON budgets(profile_id, year, month);")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_movements_budget ON movements(budget_id);")
            
            seed_demo_profiles(conn)
    finally:
        if close_conn:
            conn.close()

def seed_demo_profiles(conn):
    """Insert demo profiles idempotently using INSERT OR IGNORE."""
    now_utc = datetime.now(timezone.utc).isoformat()
    profiles = [
        ('demo-ana-001', 'Ana Demo', 'demo', now_utc),
        ('demo-carlos-002', 'Carlos Demo', 'demo', now_utc)
    ]
    with conn:
        conn.executemany(
            "INSERT OR IGNORE INTO profiles (id, display_name, profile_type, created_at) VALUES (?, ?, ?, ?)",
            profiles
        )

# --- Profile operations ---

def list_profiles(conn):
    """Return all demo profiles as list of dicts."""
    cursor = conn.execute("SELECT id, display_name, profile_type, created_at FROM profiles ORDER BY display_name")
    return [dict(row) for row in cursor.fetchall()]

def get_profile(conn, profile_id):
    """Return a single profile dict or None."""
    cursor = conn.execute("SELECT * FROM profiles WHERE id = ?", (profile_id,))
    row = cursor.fetchone()
    return dict(row) if row else None

# --- Budget operations ---

def budget_exists(conn, profile_id, year, month):
    """Check if a confirmed budget exists for this profile+period. Returns budget id or None."""
    cursor = conn.execute(
        "SELECT id FROM budgets WHERE profile_id = ? AND year = ? AND month = ? AND status = 'confirmed'",
        (profile_id, year, month)
    )
    row = cursor.fetchone()
    return row['id'] if row else None

def create_budget(conn, profile_id, year, month, income, movements, source_mode):
    """Create a new confirmed budget with its movements in a single transaction.
    
    Args:
        profile_id: owner profile
        year, month: period
        income: Decimal string or None
        movements: list of dicts with keys: description, amount (as string/number), category, source_quote (optional), origin
        source_mode: 'live', 'fixture', or 'manual'
    
    Returns: dict with budget id and metadata
    Raises: ValueError if profile doesn't exist, sqlite3.IntegrityError if duplicate period
    """
    if get_profile(conn, profile_id) is None:
        raise ValueError(f"Profile {profile_id} does not exist")
    
    budget_id = str(uuid.uuid4())
    now_utc = datetime.now(timezone.utc).isoformat()
    
    canonical_income = None
    if income is not None:
        canonical_income = str(money(float(income)))
        
    movement_rows = []
    for mov in movements:
        if mov['category'] not in CATEGORIES:
            raise ValueError(f"Invalid category: {mov['category']}")
        canonical_amount = str(money(float(mov['amount'])))
        movement_rows.append((
            str(uuid.uuid4()),
            budget_id,
            mov['description'],
            canonical_amount,
            mov['category'],
            mov.get('source_quote'),
            mov['origin'],
            now_utc
        ))
        
    with conn:
        conn.execute(
            """INSERT INTO budgets 
               (id, profile_id, year, month, income, status, source_mode, created_at, updated_at) 
               VALUES (?, ?, ?, ?, ?, 'confirmed', ?, ?, ?)""",
            (budget_id, profile_id, year, month, canonical_income, source_mode, now_utc, now_utc)
        )
        conn.executemany(
            """INSERT INTO movements 
               (id, budget_id, description, amount, category, source_quote, origin, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            movement_rows
        )
        
    return {
        'id': budget_id,
        'profile_id': profile_id,
        'year': year,
        'month': month,
        'income': canonical_income,
        'status': 'confirmed',
        'source_mode': source_mode,
        'created_at': now_utc,
        'updated_at': now_utc
    }

def list_budgets(conn, profile_id, year=None):
    """List budget summaries for a profile, newest first.

    Returns list of dicts with: id, year, month, income, status, source_mode,
    created_at, updated_at, movement_count, total_expense
    """
    query = (
        "SELECT b.id, b.year, b.month, b.income, b.status, b.source_mode, "
        "b.created_at, b.updated_at, "
        "COUNT(m.id) as movement_count, "
        "COALESCE(SUM(CAST(m.amount AS REAL)), 0) as total_expense "
        "FROM budgets b "
        "LEFT JOIN movements m ON b.id = m.budget_id "
        "WHERE b.profile_id = ?"
    )
    params = [profile_id]

    if year is not None:
        query += " AND b.year = ?"
        params.append(year)

    query += " GROUP BY b.id ORDER BY b.year DESC, b.month DESC"

    cursor = conn.execute(query, params)
    return [dict(row) for row in cursor.fetchall()]


def get_budget(conn, budget_id, profile_id):
    """Get a single budget with all its movements. Returns None if not found or wrong owner.
    
    ALWAYS filter by profile_id to prevent cross-profile access.
    """
    cursor = conn.execute("SELECT * FROM budgets WHERE id = ? AND profile_id = ?", (budget_id, profile_id))
    budget_row = cursor.fetchone()
    if not budget_row:
        return None
        
    budget = dict(budget_row)
    cursor = conn.execute("SELECT * FROM movements WHERE budget_id = ? ORDER BY created_at ASC", (budget_id,))
    budget['movements'] = [dict(row) for row in cursor.fetchall()]
    return budget

def update_budget(conn, budget_id, profile_id, income, movements):
    """Update an existing budget: replace income and all movements in a transaction.
    
    - Verify ownership first
    - Delete old movements, insert new ones with new UUIDs
    - Update budget's income and updated_at
    - All in one transaction
    """
    budget = get_budget(conn, budget_id, profile_id)
    if not budget:
        raise ValueError(f"Budget {budget_id} not found or not owned by {profile_id}")
        
    now_utc = datetime.now(timezone.utc).isoformat()
    
    canonical_income = None
    if income is not None:
        canonical_income = str(money(float(income)))
        
    movement_rows = []
    for mov in movements:
        if mov['category'] not in CATEGORIES:
            raise ValueError(f"Invalid category: {mov['category']}")
        canonical_amount = str(money(float(mov['amount'])))
        movement_rows.append((
            str(uuid.uuid4()),
            budget_id,
            mov['description'],
            canonical_amount,
            mov['category'],
            mov.get('source_quote'),
            mov['origin'],
            now_utc
        ))
        
    with conn:
        conn.execute(
            "UPDATE budgets SET income = ?, updated_at = ? WHERE id = ?",
            (canonical_income, now_utc, budget_id)
        )
        conn.execute("DELETE FROM movements WHERE budget_id = ?", (budget_id,))
        conn.executemany(
            """INSERT INTO movements 
               (id, budget_id, description, amount, category, source_quote, origin, created_at) 
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            movement_rows
        )
        
    return get_budget(conn, budget_id, profile_id)

def delete_budget(conn, budget_id, profile_id):
    """Delete a budget and its movements (cascade). Returns True if deleted, False if not found/not owned."""
    with conn:
        cursor = conn.execute("DELETE FROM budgets WHERE id = ? AND profile_id = ?", (budget_id, profile_id))
        return cursor.rowcount > 0


def save_budget(conn, profile_id, year, month, income, movements, source_mode, replace=False):
    """Replace in one transaction, preserving the existing ID and data on failure."""
    existing = budget_exists(conn, profile_id, year, month)
    if existing:
        if not replace:
            raise FileExistsError('Ya existe un presupuesto para ese mes.')
        return update_budget(conn, existing, profile_id, income, movements)
    return create_budget(conn, profile_id, year, month, income, movements, source_mode)
