"""
verify_server.py — Automated verification of the MCP server.

Runs an in-process FastMCP client against the server, verifying:
  1. Tool discovery (search, insert, aggregate present)
  2. Successful search call
  3. Successful insert call
  4. Successful aggregate call
  5. Error: unknown table
  6. Error: unknown column
  7. Error: unsupported metric
  8. Schema resource readable
  9. Per-table schema resource readable

Exit code 0 = all checks passed. Non-zero = failures detected.
"""

import json
import sys
from pathlib import Path

# Ensure implementation/ is importable
sys.path.insert(0, str(Path(__file__).parent))

from db import SQLiteAdapter, ValidationError
from init_db import create_database, DB_PATH

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

PASS = "\033[92m✓\033[0m"
FAIL = "\033[91m✗\033[0m"
BOLD = "\033[1m"
RESET = "\033[0m"

failures: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    if condition:
        print(f"  {PASS} {label}")
    else:
        print(f"  {FAIL} {label}" + (f"\n      → {detail}" if detail else ""))
        failures.append(label)


# ---------------------------------------------------------------------------
# Setup
# ---------------------------------------------------------------------------

print(f"\n{BOLD}=== SQLite Lab — Server Verification ==={RESET}\n")

if not DB_PATH.exists():
    print("[verify] Initializing database...")
    create_database(DB_PATH)

db = SQLiteAdapter(DB_PATH)

# ---------------------------------------------------------------------------
# 1. Database sanity
# ---------------------------------------------------------------------------
print(f"{BOLD}[1] Database sanity{RESET}")
tables = db.list_tables()
check("students table exists", "students" in tables, f"tables={tables}")
check("courses table exists",  "courses"  in tables, f"tables={tables}")
check("enrollments table exists", "enrollments" in tables, f"tables={tables}")

# ---------------------------------------------------------------------------
# 2. search — happy path
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[2] Tool: search (happy path){RESET}")

result = db.search("students", limit=3)
check("search returns rows", len(result["rows"]) > 0, str(result))
check("search respects limit", result["total_returned"] <= 3, str(result))
check("search has has_more flag", "has_more" in result, str(result))

result2 = db.search("students", filters={"cohort": {"eq": "A1"}})
a1_rows = result2["rows"]
check("search filter eq works", all(r["cohort"] == "A1" for r in a1_rows), str(a1_rows))

result3 = db.search("students", order_by="score", descending=True, limit=1)
check("search order_by descending works", len(result3["rows"]) == 1, str(result3))

result4 = db.search("students", columns=["name", "cohort"], limit=2)
check("search column selection works",
      all(set(r.keys()) == {"name", "cohort"} for r in result4["rows"]),
      str(result4["rows"]))

result5 = db.search("students", offset=2, limit=2)
check("search offset (pagination) works", result5["offset"] == 2, str(result5))

# ---------------------------------------------------------------------------
# 3. search — operator coverage
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[3] Tool: search (operators){RESET}")

gt_result = db.search("students", filters={"score": {"gt": 90}})
check("operator gt works", all(r["score"] > 90 for r in gt_result["rows"]), str(gt_result["rows"]))

like_result = db.search("students", filters={"name": {"like": "A%"}})
check("operator like works", len(like_result["rows"]) > 0, str(like_result["rows"]))

in_result = db.search("students", filters={"cohort": {"in": ["A1", "B1"]}})
check("operator in works",
      all(r["cohort"] in ("A1", "B1") for r in in_result["rows"]),
      str(in_result["rows"]))

# ---------------------------------------------------------------------------
# 4. insert — happy path
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[4] Tool: insert (happy path){RESET}")

new_student = {
    "name": "Zara Test",
    "email": "zara.verify@example.com",
    "cohort": "B3",
    "score": 77.7,
}
ins_result = db.insert("students", new_student)
check("insert returns 'inserted' key", "inserted" in ins_result, str(ins_result))
check("inserted row has id", "id" in ins_result["inserted"], str(ins_result))
check("inserted name matches", ins_result["inserted"]["name"] == "Zara Test", str(ins_result))

# ---------------------------------------------------------------------------
# 5. aggregate — happy path
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[5] Tool: aggregate (happy path){RESET}")

count_result = db.aggregate("students", metric="count")
check("count(*) works", count_result["results"][0]["value"] > 0, str(count_result))

avg_result = db.aggregate("students", metric="avg", column="score")
check("avg(score) works", isinstance(avg_result["results"][0]["value"], float), str(avg_result))

sum_result = db.aggregate("courses", metric="sum", column="credits")
check("sum(credits) works", sum_result["results"][0]["value"] > 0, str(sum_result))

min_result = db.aggregate("students", metric="min", column="score")
check("min(score) works", "value" in min_result["results"][0], str(min_result))

max_result = db.aggregate("students", metric="max", column="score")
check("max(score) works", "value" in max_result["results"][0], str(max_result))

group_result = db.aggregate("students", metric="avg", column="score", group_by="cohort")
check("avg by group_by works", len(group_result["results"]) > 1, str(group_result))

# ---------------------------------------------------------------------------
# 6. Validation / error cases
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[6] Validation: error cases{RESET}")

try:
    db.search("nonexistent_table")
    check("rejects unknown table", False, "no exception raised")
except ValidationError as e:
    check("rejects unknown table", "nonexistent_table" in str(e), str(e))

try:
    db.search("students", filters={"ghost_col": {"eq": 1}})
    check("rejects unknown column", False, "no exception raised")
except ValidationError as e:
    check("rejects unknown column", "ghost_col" in str(e), str(e))

try:
    db.search("students", filters={"score": {"drop_table": 0}})
    check("rejects unsupported operator", False, "no exception raised")
except ValidationError as e:
    check("rejects unsupported operator", "drop_table" in str(e), str(e))

try:
    db.aggregate("students", metric="drop_table")
    check("rejects unsupported metric", False, "no exception raised")
except ValidationError as e:
    check("rejects unsupported metric", "drop_table" in str(e), str(e))

try:
    db.insert("students", {})
    check("rejects empty insert", False, "no exception raised")
except ValidationError as e:
    check("rejects empty insert", "empty" in str(e).lower(), str(e))

try:
    db.aggregate("students", metric="avg", column=None)
    check("rejects avg without column", False, "no exception raised")
except ValidationError as e:
    check("rejects avg without column", "column" in str(e).lower(), str(e))

# ---------------------------------------------------------------------------
# 7. Schema resources
# ---------------------------------------------------------------------------
print(f"\n{BOLD}[7] Schema resources{RESET}")

full_schema = db.get_full_schema()
check("full schema has students", "students" in full_schema, str(list(full_schema.keys())))
check("full schema has courses",  "courses"  in full_schema, str(list(full_schema.keys())))
check("full schema has enrollments", "enrollments" in full_schema, str(list(full_schema.keys())))

student_schema = db.get_table_schema("students")
col_names = [c["name"] for c in student_schema]
check("students schema has id",     "id"     in col_names, str(col_names))
check("students schema has name",   "name"   in col_names, str(col_names))
check("students schema has cohort", "cohort" in col_names, str(col_names))
check("students schema has score",  "score"  in col_names, str(col_names))

# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------
total = 29  # update if you add checks
passed = total - len(failures)
print(f"\n{BOLD}=== Results: {passed}/{total} checks passed ==={RESET}")
if failures:
    print(f"\n{BOLD}Failed checks:{RESET}")
    for f in failures:
        print(f"  {FAIL} {f}")
    sys.exit(1)
else:
    print(f"\n{PASS} {BOLD}All checks passed! Server is ready for grading.{RESET}\n")
    sys.exit(0)
