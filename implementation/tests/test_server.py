"""
tests/test_server.py — Unit tests for SQLiteAdapter using an in-memory database.

Run with:
    pytest tests/ -v
"""

import json
import sqlite3
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Make sure the parent implementation directory is importable
# ---------------------------------------------------------------------------
sys.path.insert(0, str(Path(__file__).parent.parent))

from db import SQLiteAdapter, ValidationError, ALLOWED_METRICS, ALLOWED_OPERATORS  # noqa: E402

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SCHEMA_SQL = """
CREATE TABLE students (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    name    TEXT NOT NULL,
    email   TEXT UNIQUE NOT NULL,
    cohort  TEXT NOT NULL,
    score   REAL DEFAULT 0.0
);
CREATE TABLE courses (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    code     TEXT UNIQUE NOT NULL,
    title    TEXT NOT NULL,
    credits  INTEGER NOT NULL DEFAULT 3,
    instructor TEXT NOT NULL
);
CREATE TABLE enrollments (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    student_id INTEGER NOT NULL REFERENCES students(id),
    course_id  INTEGER NOT NULL REFERENCES courses(id),
    grade      REAL,
    status     TEXT NOT NULL DEFAULT 'active'
);
"""

SEED_SQL = """
INSERT INTO students (name, email, cohort, score) VALUES
    ('Alice', 'alice@test.com', 'A1', 92.0),
    ('Bob',   'bob@test.com',   'A1', 75.0),
    ('Carol', 'carol@test.com', 'A2', 85.0),
    ('David', 'david@test.com', 'A2', 60.0),
    ('Eva',   'eva@test.com',   'B1', 95.0);

INSERT INTO courses (code, title, credits, instructor) VALUES
    ('CS101', 'Intro', 3, 'Dr. X'),
    ('CS201', 'DS',    4, 'Dr. Y');

INSERT INTO enrollments (student_id, course_id, grade, status) VALUES
    (1, 1, 90.0, 'active'),
    (2, 1, 75.0, 'active'),
    (3, 2, 82.0, 'active'),
    (4, 2, 60.0, 'dropped'),
    (5, 1, 95.0, 'active');
"""


@pytest.fixture
def adapter(tmp_path):
    """SQLiteAdapter backed by a fresh temporary database."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.executescript(SEED_SQL)
    conn.commit()
    conn.close()
    return SQLiteAdapter(db_path)


# ---------------------------------------------------------------------------
# Schema inspection
# ---------------------------------------------------------------------------

class TestSchemaInspection:
    def test_list_tables(self, adapter):
        tables = adapter.list_tables()
        assert "students" in tables
        assert "courses" in tables
        assert "enrollments" in tables

    def test_get_table_schema_students(self, adapter):
        cols = adapter.get_table_schema("students")
        names = [c["name"] for c in cols]
        assert "id" in names
        assert "name" in names
        assert "cohort" in names
        assert "score" in names

    def test_get_full_schema(self, adapter):
        schema = adapter.get_full_schema()
        assert set(schema.keys()) == {"students", "courses", "enrollments"}

    def test_get_schema_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError, match="Unknown table"):
            adapter.get_table_schema("ghost")


# ---------------------------------------------------------------------------
# search — happy path
# ---------------------------------------------------------------------------

class TestSearch:
    def test_search_all_rows(self, adapter):
        result = adapter.search("students")
        assert result["total_returned"] == 5
        assert len(result["rows"]) == 5

    def test_search_limit(self, adapter):
        result = adapter.search("students", limit=2)
        assert result["total_returned"] == 2
        assert result["has_more"] is True

    def test_search_offset(self, adapter):
        first = adapter.search("students", limit=2, offset=0)
        second = adapter.search("students", limit=2, offset=2)
        first_ids = {r["id"] for r in first["rows"]}
        second_ids = {r["id"] for r in second["rows"]}
        assert first_ids.isdisjoint(second_ids)

    def test_search_columns_selection(self, adapter):
        result = adapter.search("students", columns=["name", "cohort"])
        for row in result["rows"]:
            assert set(row.keys()) == {"name", "cohort"}

    def test_search_filter_eq(self, adapter):
        result = adapter.search("students", filters={"cohort": {"eq": "A1"}})
        assert all(r["cohort"] == "A1" for r in result["rows"])
        assert result["total_returned"] == 2

    def test_search_filter_gt(self, adapter):
        result = adapter.search("students", filters={"score": {"gt": 90}})
        assert all(r["score"] > 90 for r in result["rows"])

    def test_search_filter_gte(self, adapter):
        result = adapter.search("students", filters={"score": {"gte": 92}})
        assert all(r["score"] >= 92 for r in result["rows"])

    def test_search_filter_lt(self, adapter):
        result = adapter.search("students", filters={"score": {"lt": 80}})
        assert all(r["score"] < 80 for r in result["rows"])

    def test_search_filter_lte(self, adapter):
        result = adapter.search("students", filters={"score": {"lte": 75}})
        assert all(r["score"] <= 75 for r in result["rows"])

    def test_search_filter_neq(self, adapter):
        result = adapter.search("students", filters={"cohort": {"neq": "A1"}})
        assert all(r["cohort"] != "A1" for r in result["rows"])

    def test_search_filter_like(self, adapter):
        result = adapter.search("students", filters={"name": {"like": "A%"}})
        assert result["total_returned"] >= 1
        assert all(r["name"].startswith("A") for r in result["rows"])

    def test_search_filter_in(self, adapter):
        result = adapter.search("students", filters={"cohort": {"in": ["A1", "B1"]}})
        assert all(r["cohort"] in ("A1", "B1") for r in result["rows"])

    def test_search_order_by_asc(self, adapter):
        result = adapter.search("students", order_by="score", descending=False)
        scores = [r["score"] for r in result["rows"]]
        assert scores == sorted(scores)

    def test_search_order_by_desc(self, adapter):
        result = adapter.search("students", order_by="score", descending=True)
        scores = [r["score"] for r in result["rows"]]
        assert scores == sorted(scores, reverse=True)

    def test_search_pagination_metadata(self, adapter):
        result = adapter.search("students", limit=2)
        assert result["next_offset"] == 2
        result2 = adapter.search("students", limit=10)
        assert result2["has_more"] is False
        assert result2["next_offset"] is None


# ---------------------------------------------------------------------------
# search — validation errors
# ---------------------------------------------------------------------------

class TestSearchValidation:
    def test_unknown_table(self, adapter):
        with pytest.raises(ValidationError, match="Unknown table"):
            adapter.search("ghost_table")

    def test_unknown_column_in_filters(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.search("students", filters={"ghost_col": {"eq": 1}})

    def test_unknown_column_in_columns(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.search("students", columns=["ghost_col"])

    def test_unknown_order_by_column(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.search("students", order_by="ghost_col")

    def test_unsupported_operator(self, adapter):
        with pytest.raises(ValidationError, match="Unsupported operator"):
            adapter.search("students", filters={"score": {"drop_table": 0}})

    def test_in_operator_requires_list(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students", filters={"cohort": {"in": "A1"}})

    def test_bad_filter_format(self, adapter):
        with pytest.raises(ValidationError):
            adapter.search("students", filters={"score": "bad"})


# ---------------------------------------------------------------------------
# insert — happy path
# ---------------------------------------------------------------------------

class TestInsert:
    def test_insert_returns_payload(self, adapter):
        result = adapter.insert("students", {
            "name": "Zara", "email": "zara@test.com",
            "cohort": "C1", "score": 88.0,
        })
        assert "inserted" in result
        assert result["inserted"]["name"] == "Zara"
        assert result["inserted"]["id"] is not None

    def test_inserted_row_is_searchable(self, adapter):
        adapter.insert("students", {
            "name": "Nova", "email": "nova@test.com",
            "cohort": "C2", "score": 99.0,
        })
        result = adapter.search("students", filters={"email": {"eq": "nova@test.com"}})
        assert result["total_returned"] == 1
        assert result["rows"][0]["name"] == "Nova"

    def test_insert_table_in_result(self, adapter):
        result = adapter.insert("students", {
            "name": "Tim", "email": "tim@test.com", "cohort": "A1", "score": 50.0,
        })
        assert result["table"] == "students"


# ---------------------------------------------------------------------------
# insert — validation errors
# ---------------------------------------------------------------------------

class TestInsertValidation:
    def test_empty_values_raises(self, adapter):
        with pytest.raises(ValidationError, match="empty"):
            adapter.insert("students", {})

    def test_unknown_table_raises(self, adapter):
        with pytest.raises(ValidationError, match="Unknown table"):
            adapter.insert("ghost", {"name": "x"})

    def test_unknown_column_raises(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.insert("students", {"ghost_col": "value"})


# ---------------------------------------------------------------------------
# aggregate — happy path
# ---------------------------------------------------------------------------

class TestAggregate:
    def test_count(self, adapter):
        result = adapter.aggregate("students", metric="count")
        assert result["results"][0]["value"] == 5

    def test_avg(self, adapter):
        result = adapter.aggregate("students", metric="avg", column="score")
        avg = result["results"][0]["value"]
        assert isinstance(avg, float)
        assert 60 < avg < 100

    def test_sum(self, adapter):
        result = adapter.aggregate("courses", metric="sum", column="credits")
        assert result["results"][0]["value"] == 7  # 3+4

    def test_min(self, adapter):
        result = adapter.aggregate("students", metric="min", column="score")
        assert result["results"][0]["value"] == 60.0

    def test_max(self, adapter):
        result = adapter.aggregate("students", metric="max", column="score")
        assert result["results"][0]["value"] == 95.0

    def test_group_by(self, adapter):
        result = adapter.aggregate(
            "students", metric="avg", column="score", group_by="cohort"
        )
        cohorts = {r["cohort"] for r in result["results"]}
        assert "A1" in cohorts
        assert "A2" in cohorts

    def test_aggregate_with_filter(self, adapter):
        result = adapter.aggregate(
            "students", metric="count",
            filters={"cohort": {"eq": "A1"}}
        )
        assert result["results"][0]["value"] == 2

    def test_result_metadata(self, adapter):
        result = adapter.aggregate("students", metric="count")
        assert result["table"] == "students"
        assert result["metric"] == "count"


# ---------------------------------------------------------------------------
# aggregate — validation errors
# ---------------------------------------------------------------------------

class TestAggregateValidation:
    def test_unsupported_metric(self, adapter):
        with pytest.raises(ValidationError, match="Unsupported metric"):
            adapter.aggregate("students", metric="drop_table")

    def test_avg_without_column(self, adapter):
        with pytest.raises(ValidationError, match="column"):
            adapter.aggregate("students", metric="avg", column=None)

    def test_unknown_table(self, adapter):
        with pytest.raises(ValidationError, match="Unknown table"):
            adapter.aggregate("ghost", metric="count")

    def test_unknown_column(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.aggregate("students", metric="sum", column="ghost_col")

    def test_unknown_group_by_column(self, adapter):
        with pytest.raises(ValidationError, match="Unknown column"):
            adapter.aggregate("students", metric="count", group_by="ghost_col")


# ---------------------------------------------------------------------------
# Constants sanity
# ---------------------------------------------------------------------------

class TestConstants:
    def test_allowed_metrics_complete(self):
        assert ALLOWED_METRICS == {"count", "avg", "sum", "min", "max"}

    def test_allowed_operators_complete(self):
        assert "eq" in ALLOWED_OPERATORS
        assert "like" in ALLOWED_OPERATORS
        assert "in" in ALLOWED_OPERATORS
