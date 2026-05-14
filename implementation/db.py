"""
db.py — Database Adapters: safe, validated operations for MCP server.

Provides a shared `DatabaseAdapter` interface with two implementations:
- `SQLiteAdapter` (default)
- `PostgresAdapter` (bonus)

Design principles:
- Identifiers are validated against a live schema whitelist.
- Parameterized SQL is used exclusively to prevent injection.
- Operators and metrics are strictly allowlisted.
"""

import sqlite3
import os
from abc import ABC, abstractmethod
from typing import Any
from pathlib import Path

# Try to import psycopg2 for Postgres support
try:
    import psycopg2
    from psycopg2.extras import DictCursor
    HAS_PSYCOPG2 = True
except ImportError:
    HAS_PSYCOPG2 = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DB_PATH = Path(__file__).parent / "lab.db"

ALLOWED_METRICS = {"count", "avg", "sum", "min", "max"}
ALLOWED_OPERATORS = {"eq", "neq", "gt", "gte", "lt", "lte", "like", "in"}

_OP_MAP = {
    "eq":   "=",
    "neq":  "!=",
    "gt":   ">",
    "gte":  ">=",
    "lt":   "<",
    "lte":  "<=",
    "like": "LIKE",
    "in":   "IN",
}

# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when a request cannot be safely executed."""

# ---------------------------------------------------------------------------
# Shared Interface
# ---------------------------------------------------------------------------

class DatabaseAdapter(ABC):
    """Abstract base class for safe database access."""

    @abstractmethod
    def list_tables(self) -> list[str]: ...

    @abstractmethod
    def get_table_schema(self, table: str) -> list[dict]: ...

    def get_full_schema(self) -> dict[str, list[dict]]:
        """Return schema for all tables."""
        return {t: self.get_table_schema(t) for t in self.list_tables()}

    def _validate_table(self, table: str) -> None:
        allowed = self.list_tables()
        if table not in allowed:
            raise ValidationError(f"Unknown table '{table}'. Allowed: {allowed}")

    def _get_columns(self, table: str) -> set[str]:
        return {c["name"] for c in self.get_table_schema(table)}

    def _validate_column(self, column: str, table: str) -> None:
        allowed = self._get_columns(table)
        if column not in allowed:
            raise ValidationError(
                f"Unknown column '{column}' in table '{table}'. Allowed: {sorted(allowed)}"
            )

    @abstractmethod
    def search(self, table: str, columns: list[str] | None = None, filters: dict | None = None,
               limit: int = 20, offset: int = 0, order_by: str | None = None, descending: bool = False) -> dict: ...

    @abstractmethod
    def insert(self, table: str, values: dict) -> dict: ...

    @abstractmethod
    def aggregate(self, table: str, metric: str, column: str | None = None,
                  filters: dict | None = None, group_by: str | None = None) -> dict: ...


# ---------------------------------------------------------------------------
# SQLite Implementation
# ---------------------------------------------------------------------------

class SQLiteAdapter(DatabaseAdapter):
    """Thread-safe SQLite adapter with identifier validation."""

    def __init__(self, db_path: Path):
        self.db_path = db_path

    def connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()
        return [r["name"] for r in rows]

    def get_table_schema(self, table: str) -> list[dict]:
        self._validate_table(table)
        with self.connect() as conn:
            rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
        if not rows:
            raise ValidationError(f"Table '{table}' not found or is empty.")
        return [
            {
                "cid": r["cid"], "name": r["name"], "type": r["type"],
                "notnull": bool(r["notnull"]), "default": r["dflt_value"], "primary_key": bool(r["pk"]),
            } for r in rows
        ]

    def _build_where(self, table: str, filters: dict | None) -> tuple[str, list[Any]]:
        if not filters: return "", []
        clauses, params = [], []
        for col, condition in filters.items():
            self._validate_column(col, table)
            if not isinstance(condition, dict) or len(condition) != 1:
                raise ValidationError(f"Filter for '{col}' must be {{operator: value}}.")
            op_key, value = next(iter(condition.items()))
            if op_key not in ALLOWED_OPERATORS:
                raise ValidationError(f"Unsupported operator '{op_key}'. Allowed: {sorted(ALLOWED_OPERATORS)}")
            sql_op = _OP_MAP[op_key]
            if op_key == "in":
                if not isinstance(value, list) or not value:
                    raise ValidationError("Operator 'in' requires a non-empty list.")
                clauses.append(f"{col} {sql_op} ({', '.join('?' * len(value))})")
                params.extend(value)
            else:
                clauses.append(f"{col} {sql_op} ?")
                params.append(value)
        return "WHERE " + " AND ".join(clauses), params

    def search(self, table: str, columns: list[str] | None = None, filters: dict | None = None,
               limit: int = 20, offset: int = 0, order_by: str | None = None, descending: bool = False) -> dict:
        self._validate_table(table)
        if columns:
            for col in columns: self._validate_column(col, table)
            select = ", ".join(columns)
        else: select = "*"
        
        where_clause, params = self._build_where(table, filters)
        order_clause = ""
        if order_by:
            self._validate_column(order_by, table)
            order_clause = f"ORDER BY {order_by} {'DESC' if descending else 'ASC'}"
        
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        sql = f"SELECT {select} FROM {table} {where_clause} {order_clause} LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        results = [dict(r) for r in rows]
        return {
            "table": table, "rows": results, "total_returned": len(results),
            "limit": limit, "offset": offset, "has_more": len(results) == limit,
            "next_offset": offset + limit if len(results) == limit else None,
        }

    def insert(self, table: str, values: dict) -> dict:
        self._validate_table(table)
        if not values: raise ValidationError("'values' must not be empty.")
        for col in values: self._validate_column(col, table)
        
        cols = list(values.keys())
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join('?' * len(cols))})"
        bound = [values[c] for c in cols]

        with self.connect() as conn:
            cursor = conn.execute(sql, bound)
            conn.commit()
            last_id = cursor.lastrowid

        row = conn.execute(f"SELECT * FROM {table} WHERE rowid = ?", [last_id]).fetchone()
        return {"table": table, "inserted": dict(row) if row else {**values, "id": last_id}}

    def aggregate(self, table: str, metric: str, column: str | None = None,
                  filters: dict | None = None, group_by: str | None = None) -> dict:
        self._validate_table(table)
        metric = metric.lower()
        if metric not in ALLOWED_METRICS:
            raise ValidationError(f"Unsupported metric '{metric}'.")
        
        if metric == "count":
            agg_expr = "COUNT(*)"
        else:
            if not column: raise ValidationError(f"Metric '{metric}' requires a 'column' argument.")
            self._validate_column(column, table)
            agg_expr = f"{metric.upper()}({column})"

        where_clause, params = self._build_where(table, filters)
        group_clause = select_prefix = ""
        if group_by:
            self._validate_column(group_by, table)
            group_clause = f"GROUP BY {group_by}"
            select_prefix = f"{group_by}, "

        sql = f"SELECT {select_prefix}{agg_expr} AS value FROM {table} {where_clause} {group_clause}"
        with self.connect() as conn:
            rows = conn.execute(sql, params).fetchall()

        return {
            "table": table, "metric": metric, "column": column,
            "group_by": group_by, "results": [dict(r) for r in rows],
        }


# ---------------------------------------------------------------------------
# PostgreSQL Implementation
# ---------------------------------------------------------------------------

class PostgresAdapter(DatabaseAdapter):
    """PostgreSQL adapter using psycopg2."""

    def __init__(self, dsn: str):
        if not HAS_PSYCOPG2:
            raise RuntimeError("psycopg2-binary is required for PostgresAdapter.")
        self.dsn = dsn

    def connect(self):
        return psycopg2.connect(self.dsn, cursor_factory=DictCursor)

    def list_tables(self) -> list[str]:
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
                return [r["table_name"] for r in cur.fetchall()]

    def get_table_schema(self, table: str) -> list[dict]:
        self._validate_table(table)
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT column_name, data_type, is_nullable, column_default "
                    "FROM information_schema.columns WHERE table_name = %s", (table,)
                )
                rows = cur.fetchall()
        if not rows:
            raise ValidationError(f"Table '{table}' not found.")
        return [
            {
                "name": r["column_name"], "type": r["data_type"],
                "notnull": r["is_nullable"] == "NO", "default": r["column_default"],
            } for r in rows
        ]

    def _build_where(self, table: str, filters: dict | None) -> tuple[str, list[Any]]:
        if not filters: return "", []
        clauses, params = [], []
        for col, condition in filters.items():
            self._validate_column(col, table)
            if not isinstance(condition, dict) or len(condition) != 1:
                raise ValidationError("Invalid filter format")
            op_key, value = next(iter(condition.items()))
            if op_key not in ALLOWED_OPERATORS:
                raise ValidationError("Unsupported operator")
            sql_op = _OP_MAP[op_key]
            if op_key == "in":
                clauses.append(f"{col} {sql_op} %s")
                params.append(tuple(value)) # psycopg2 adapts tuples to IN (...)
            else:
                clauses.append(f"{col} {sql_op} %s")
                params.append(value)
        return "WHERE " + " AND ".join(clauses), params

    def search(self, table: str, columns: list[str] | None = None, filters: dict | None = None,
               limit: int = 20, offset: int = 0, order_by: str | None = None, descending: bool = False) -> dict:
        self._validate_table(table)
        select = ", ".join(columns) if columns and all(self._validate_column(c, table) is None for c in columns) else "*"
        where_clause, params = self._build_where(table, filters)
        order_clause = f"ORDER BY {order_by} {'DESC' if descending else 'ASC'}" if order_by and not self._validate_column(order_by, table) else ""
        
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        sql = f"SELECT {select} FROM {table} {where_clause} {order_clause} LIMIT %s OFFSET %s"
        params.extend([limit, offset])

        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]

        return {
            "table": table, "rows": rows, "total_returned": len(rows),
            "limit": limit, "offset": offset, "has_more": len(rows) == limit,
            "next_offset": offset + limit if len(rows) == limit else None,
        }

    def insert(self, table: str, values: dict) -> dict:
        self._validate_table(table)
        if not values: raise ValidationError("'values' must not be empty.")
        cols = list(values.keys())
        for c in cols: self._validate_column(c, table)
        
        sql = f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(['%s']*len(cols))}) RETURNING *"
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, [values[c] for c in cols])
                row = dict(cur.fetchone())
                conn.commit()
        return {"table": table, "inserted": row}

    def aggregate(self, table: str, metric: str, column: str | None = None,
                  filters: dict | None = None, group_by: str | None = None) -> dict:
        self._validate_table(table)
        metric = metric.lower()
        if metric not in ALLOWED_METRICS: raise ValidationError("Unsupported metric")
        agg_expr = "COUNT(*)" if metric == "count" else f"{metric.upper()}({column})"
        if metric != "count": self._validate_column(column, table)
        
        where_clause, params = self._build_where(table, filters)
        group_clause = f"GROUP BY {group_by}" if group_by and not self._validate_column(group_by, table) else ""
        select_prefix = f"{group_by}, " if group_by else ""

        sql = f"SELECT {select_prefix}{agg_expr} AS value FROM {table} {where_clause} {group_clause}"
        with self.connect() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = [dict(r) for r in cur.fetchall()]
        return {"table": table, "metric": metric, "column": column, "group_by": group_by, "results": rows}


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

def get_database_adapter() -> DatabaseAdapter:
    """Returns a configured DatabaseAdapter based on DB_BACKEND environment variable."""
    backend = os.environ.get("DB_BACKEND", "sqlite").lower()
    if backend == "postgres":
        dsn = os.environ.get("POSTGRES_DSN", "postgresql://localhost:5432/lab")
        return PostgresAdapter(dsn)
    else:
        return SQLiteAdapter(DB_PATH)
