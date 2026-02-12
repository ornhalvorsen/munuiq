"""
User/tenant management CRUD on the munuiq database.

Reuses the logging_db connection (same writable MotherDuck database).
All operations are thread-safe via the logging_db lock.
"""

import json
import threading
import duckdb
from app.config import settings

_conn: duckdb.DuckDBPyConnection | None = None
_lock = threading.Lock()

_CREATE_USERS_TABLE = """
CREATE SEQUENCE IF NOT EXISTS users_seq START 1;
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY DEFAULT nextval('users_seq'),
    email         VARCHAR NOT NULL UNIQUE,
    password_hash VARCHAR,
    supabase_id   VARCHAR UNIQUE,
    name          VARCHAR NOT NULL,
    role          VARCHAR NOT NULL DEFAULT 'viewer',
    is_active     BOOLEAN NOT NULL DEFAULT true,
    created_at    TIMESTAMP DEFAULT current_timestamp
);
"""

_CREATE_TENANTS_TABLE = """
CREATE SEQUENCE IF NOT EXISTS tenants_seq START 1;
CREATE TABLE IF NOT EXISTS tenants (
    id           INTEGER PRIMARY KEY DEFAULT nextval('tenants_seq'),
    name         VARCHAR NOT NULL,
    customer_ids VARCHAR NOT NULL,
    settings     VARCHAR DEFAULT '{}',
    is_active    BOOLEAN NOT NULL DEFAULT true,
    created_at   TIMESTAMP DEFAULT current_timestamp
);
"""

_CREATE_TENANT_USERS_TABLE = """
CREATE SEQUENCE IF NOT EXISTS tenant_users_seq START 1;
CREATE TABLE IF NOT EXISTS tenant_users (
    id        INTEGER PRIMARY KEY DEFAULT nextval('tenant_users_seq'),
    user_id   INTEGER NOT NULL,
    tenant_id INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT current_timestamp
);
"""

_CREATE_ONBOARDING_STATE_TABLE = """
CREATE SEQUENCE IF NOT EXISTS onboarding_state_seq START 1;
CREATE TABLE IF NOT EXISTS onboarding_state (
    id              INTEGER PRIMARY KEY DEFAULT nextval('onboarding_state_seq'),
    customer_id     INTEGER NOT NULL,
    tenant_id       INTEGER NOT NULL,
    current_step    VARCHAR NOT NULL DEFAULT 'entities',
    completed_steps VARCHAR DEFAULT '[]',
    metadata        VARCHAR DEFAULT '{}',
    started_at      TIMESTAMP DEFAULT current_timestamp,
    updated_at      TIMESTAMP DEFAULT current_timestamp
);
"""

_CREATE_ONBOARDING_MAPPINGS_TABLE = """
CREATE SEQUENCE IF NOT EXISTS onboarding_mappings_seq START 1;
CREATE TABLE IF NOT EXISTS onboarding_mappings (
    id                INTEGER PRIMARY KEY DEFAULT nextval('onboarding_mappings_seq'),
    customer_id       INTEGER NOT NULL,
    mapping_type      VARCHAR NOT NULL,
    source_key        VARCHAR NOT NULL,
    source_label      VARCHAR,
    proposed_value    VARCHAR NOT NULL,
    confidence        FLOAT,
    status            VARCHAR NOT NULL DEFAULT 'proposed',
    final_value       VARCHAR,
    approved_by       INTEGER,
    created_at        TIMESTAMP DEFAULT current_timestamp
);
"""


def connect():
    """Open writable MotherDuck connection and create management tables."""
    global _conn
    token = settings.motherduck_logging_token or settings.motherduck_token
    if not token:
        print("Management DB: no token configured — management disabled.")
        return
    try:
        _conn = duckdb.connect(f"md:?motherduck_token={token}")
        _conn.execute(f'CREATE DATABASE IF NOT EXISTS "{settings.motherduck_logging_database}"')
        _conn.execute(f'USE "{settings.motherduck_logging_database}"')

        # Create sequences first (ignore if exists)
        for seq in ["users_seq", "tenants_seq", "tenant_users_seq",
                     "onboarding_state_seq", "onboarding_mappings_seq"]:
            try:
                _conn.execute(f"CREATE SEQUENCE IF NOT EXISTS {seq} START 1")
            except Exception:
                pass

        # Create tables
        for ddl in [_CREATE_USERS_TABLE, _CREATE_TENANTS_TABLE,
                    _CREATE_TENANT_USERS_TABLE,
                    _CREATE_ONBOARDING_STATE_TABLE, _CREATE_ONBOARDING_MAPPINGS_TABLE]:
            for stmt in ddl.strip().split(";"):
                stmt = stmt.strip()
                if stmt and not stmt.startswith("CREATE SEQUENCE"):
                    try:
                        _conn.execute(stmt)
                    except Exception as e:
                        # Table likely already exists
                        if "already exists" not in str(e).lower():
                            print(f"Management DB: DDL warning — {e}")

        # Migrate existing tables: add supabase_id column if missing
        try:
            _conn.execute("ALTER TABLE users ADD COLUMN supabase_id VARCHAR UNIQUE")
            print("Management DB: added supabase_id column to users table.")
        except Exception:
            pass  # Column already exists

        # Make password_hash nullable (DuckDB doesn't support ALTER COLUMN, so skip if already nullable)

        print("Management DB connected and tables ensured.")
    except Exception as e:
        print(f"Management DB: connection failed — {e}")
        _conn = None


def close():
    global _conn
    if _conn:
        try:
            _conn.close()
        except Exception:
            pass
        _conn = None


def _fetchone(sql: str, params: list = None) -> dict | None:
    """Execute query and return first row as dict, or None."""
    if _conn is None:
        return None
    try:
        with _lock:
            result = _conn.execute(sql, params or [])
            columns = [desc[0] for desc in result.description]
            row = result.fetchone()
            if row is None:
                return None
            return dict(zip(columns, row))
    except Exception as e:
        print(f"Management DB: query failed — {e}")
        return None


def _fetchall(sql: str, params: list = None) -> list[dict]:
    """Execute query and return all rows as list of dicts."""
    if _conn is None:
        return []
    try:
        with _lock:
            result = _conn.execute(sql, params or [])
            columns = [desc[0] for desc in result.description]
            rows = result.fetchall()
            return [dict(zip(columns, row)) for row in rows]
    except Exception as e:
        print(f"Management DB: query failed — {e}")
        return []


def _execute(sql: str, params: list = None) -> bool:
    """Execute a write statement. Returns True on success."""
    if _conn is None:
        return False
    try:
        with _lock:
            _conn.execute(sql, params or [])
        return True
    except Exception as e:
        print(f"Management DB: execute failed — {e}")
        return False


# ─── User CRUD ───────────────────────────────────────────────────────

def get_user_by_supabase_id(supabase_id: str) -> dict | None:
    return _fetchone("SELECT * FROM users WHERE supabase_id = ?", [supabase_id])


def get_user_by_email(email: str) -> dict | None:
    return _fetchone("SELECT * FROM users WHERE email = ?", [email])


def get_user_by_id(user_id: int) -> dict | None:
    return _fetchone("SELECT * FROM users WHERE id = ?", [user_id])


def list_users() -> list[dict]:
    return _fetchall(
        "SELECT id, email, name, role, is_active, created_at FROM users ORDER BY id"
    )


def create_user(email: str, name: str, role: str = "viewer", supabase_id: str = None) -> dict | None:
    """Create a user and return the created row."""
    if _conn is None:
        return None
    try:
        with _lock:
            _conn.execute(
                "INSERT INTO users (email, name, role, supabase_id) VALUES (?, ?, ?, ?)",
                [email, name, role, supabase_id],
            )
        return get_user_by_email(email)
    except Exception as e:
        print(f"Management DB: create_user failed — {e}")
        return None


def update_user(user_id: int, **kwargs) -> bool:
    """Update user fields. Only updates provided kwargs."""
    if not kwargs:
        return True
    sets = []
    params = []
    for k, v in kwargs.items():
        if k in ("email", "name", "role", "is_active", "supabase_id") and v is not None:
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return True
    params.append(user_id)
    return _execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", params)


def delete_user(user_id: int) -> bool:
    _execute("DELETE FROM tenant_users WHERE user_id = ?", [user_id])
    return _execute("DELETE FROM users WHERE id = ?", [user_id])


# ─── Tenant CRUD ─────────────────────────────────────────────────────

def get_tenant_by_id(tenant_id: int) -> dict | None:
    return _fetchone("SELECT * FROM tenants WHERE id = ?", [tenant_id])


def list_tenants() -> list[dict]:
    return _fetchall("SELECT * FROM tenants WHERE is_active = true ORDER BY id")


def create_tenant(name: str, customer_ids: list[int], tenant_settings: dict = None) -> dict | None:
    if _conn is None:
        return None
    try:
        cids_json = json.dumps(customer_ids)
        settings_json = json.dumps(tenant_settings or {})
        with _lock:
            _conn.execute(
                "INSERT INTO tenants (name, customer_ids, settings) VALUES (?, ?, ?)",
                [name, cids_json, settings_json],
            )
        # Return the created tenant
        return _fetchone(
            "SELECT * FROM tenants WHERE name = ? ORDER BY id DESC LIMIT 1", [name]
        )
    except Exception as e:
        print(f"Management DB: create_tenant failed — {e}")
        return None


def update_tenant(tenant_id: int, **kwargs) -> bool:
    sets = []
    params = []
    for k, v in kwargs.items():
        if v is None:
            continue
        if k == "customer_ids":
            sets.append("customer_ids = ?")
            params.append(json.dumps(v))
        elif k == "settings":
            sets.append("settings = ?")
            params.append(json.dumps(v))
        elif k in ("name", "is_active"):
            sets.append(f"{k} = ?")
            params.append(v)
    if not sets:
        return True
    params.append(tenant_id)
    return _execute(f"UPDATE tenants SET {', '.join(sets)} WHERE id = ?", params)


def delete_tenant(tenant_id: int) -> bool:
    _execute("DELETE FROM tenant_users WHERE tenant_id = ?", [tenant_id])
    return _execute("DELETE FROM tenants WHERE id = ?", [tenant_id])


# ─── Tenant-User Assignment ─────────────────────────────────────────

def assign_user_to_tenant(user_id: int, tenant_id: int) -> bool:
    """Assign a user to a tenant. Removes previous assignment first."""
    _execute("DELETE FROM tenant_users WHERE user_id = ?", [user_id])
    return _execute(
        "INSERT INTO tenant_users (user_id, tenant_id) VALUES (?, ?)",
        [user_id, tenant_id],
    )


def get_user_tenant(user_id: int) -> dict | None:
    """Get the tenant assigned to a user."""
    return _fetchone(
        """SELECT t.* FROM tenants t
           JOIN tenant_users tu ON t.id = tu.tenant_id
           WHERE tu.user_id = ?""",
        [user_id],
    )


def get_tenant_users(tenant_id: int) -> list[dict]:
    """Get all users assigned to a tenant."""
    return _fetchall(
        """SELECT u.id, u.email, u.name, u.role, u.is_active
           FROM users u JOIN tenant_users tu ON u.id = tu.user_id
           WHERE tu.tenant_id = ?""",
        [tenant_id],
    )


# ─── Onboarding State ───────────────────────────────────────────────

def get_onboarding_state(customer_id: int) -> dict | None:
    return _fetchone(
        "SELECT * FROM onboarding_state WHERE customer_id = ? ORDER BY id DESC LIMIT 1",
        [customer_id],
    )


def create_onboarding_state(customer_id: int, tenant_id: int) -> dict | None:
    _execute(
        "INSERT INTO onboarding_state (customer_id, tenant_id) VALUES (?, ?)",
        [customer_id, tenant_id],
    )
    return get_onboarding_state(customer_id)


def update_onboarding_state(customer_id: int, current_step: str, completed_steps: list[str], metadata: dict = None) -> bool:
    return _execute(
        """UPDATE onboarding_state
           SET current_step = ?, completed_steps = ?, metadata = ?, updated_at = current_timestamp
           WHERE customer_id = ? AND id = (SELECT MAX(id) FROM onboarding_state WHERE customer_id = ?)""",
        [current_step, json.dumps(completed_steps), json.dumps(metadata or {}), customer_id, customer_id],
    )


# ─── Onboarding Mappings ────────────────────────────────────────────

def get_mappings(customer_id: int, mapping_type: str = None) -> list[dict]:
    if mapping_type:
        return _fetchall(
            "SELECT * FROM onboarding_mappings WHERE customer_id = ? AND mapping_type = ? ORDER BY id",
            [customer_id, mapping_type],
        )
    return _fetchall(
        "SELECT * FROM onboarding_mappings WHERE customer_id = ? ORDER BY mapping_type, id",
        [customer_id],
    )


def create_mappings(mappings: list[dict]) -> bool:
    """Bulk insert proposed mappings."""
    if _conn is None or not mappings:
        return False
    try:
        with _lock:
            for m in mappings:
                _conn.execute(
                    """INSERT INTO onboarding_mappings
                       (customer_id, mapping_type, source_key, source_label, proposed_value, confidence, status)
                       VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    [
                        m["customer_id"], m["mapping_type"], m["source_key"],
                        m.get("source_label"), m["proposed_value"],
                        m.get("confidence", 0.0), m.get("status", "proposed"),
                    ],
                )
        return True
    except Exception as e:
        print(f"Management DB: create_mappings failed — {e}")
        return False


def update_mapping(mapping_id: int, status: str, final_value: str = None, approved_by: int = None) -> bool:
    return _execute(
        "UPDATE onboarding_mappings SET status = ?, final_value = ?, approved_by = ? WHERE id = ?",
        [status, final_value, approved_by, mapping_id],
    )


def bulk_update_mappings(updates: list[dict]) -> bool:
    """Update multiple mappings at once. Each dict has id, status, optional final_value."""
    if _conn is None or not updates:
        return False
    try:
        with _lock:
            for u in updates:
                _conn.execute(
                    "UPDATE onboarding_mappings SET status = ?, final_value = ?, approved_by = ? WHERE id = ?",
                    [u["status"], u.get("final_value"), u.get("approved_by"), u["id"]],
                )
        return True
    except Exception as e:
        print(f"Management DB: bulk_update_mappings failed — {e}")
        return False


# ─── Admin Seed ──────────────────────────────────────────────────────

def link_supabase_id(user_id: int, supabase_id: str) -> bool:
    """Link a Supabase UUID to an existing internal user."""
    return _execute(
        "UPDATE users SET supabase_id = ? WHERE id = ?",
        [supabase_id, user_id],
    )
