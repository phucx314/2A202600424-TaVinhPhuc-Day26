# Lab 26 — Database MCP Server with FastMCP & SQLite

> **Student:** 2A202600424 — Tạ Vĩnh Phúc  
> **Lab:** Day 26 — Build a Database MCP Server

A production-quality MCP server built with **FastMCP 3.x** and **SQLite**, exposing a student-course database through three tools and two schema resources.

---

## Features at a glance

| Component | Detail |
|---|---|
| **Tools** | `search`, `insert`, `aggregate` |
| **Resources** | `schema://database`, `schema://table/{table_name}` |
| **Transport** | stdio (default), SSE, HTTP |
| **Safety** | Identifier whitelist validation, parameterized SQL, operator allowlist |
| **Pagination** | `limit`, `offset`, `has_more`, `next_offset` on every `search` |
| **Tests** | 47 pytest unit tests + 29 automated verification checks |

---

## Project structure

```
implementation/
├── db.py              # SQLiteAdapter — all database logic and validation
├── init_db.py         # Creates schema and seeds data
├── mcp_server.py      # FastMCP server (tools + resources)
├── verify_server.py   # Automated verification script (29 checks)
├── start_inspector.sh # Launches MCP Inspector in one command
├── lab.db             # SQLite database (auto-created)
└── tests/
    └── test_server.py # 47 pytest unit tests
```

---

## Quick start

### 1 — Create and activate the virtual environment

```bash
cd 2A202600424-TaVinhPhuc-Day26
python3 -m venv .venv
source .venv/bin/activate
pip install fastmcp pytest
```

### 2 — Initialize the database

```bash
cd implementation
python init_db.py
# [init_db] Database ready at: .../implementation/lab.db
```

This creates three tables with seed data:

| Table | Rows | Description |
|---|---|---|
| `students` | 10 | name, email, cohort, score |
| `courses` | 5 | code, title, credits, instructor |
| `enrollments` | 12 | student_id, course_id, grade, status |

### 3 — Run automated verification

```bash
python verify_server.py
# === Results: 29/29 checks passed ===
```

### 4 — Run unit tests

```bash
python -m pytest tests/ -v
# 47 passed in 0.15s
```

### 5 — Start the server (stdio)

```bash
python mcp_server.py
# Server runs in stdio mode, ready for MCP clients
```

---

## Tool reference

### `search`

Query rows from any table with optional filtering, column selection, ordering, and pagination.

```json
{
  "table": "students",
  "filters": {"cohort": {"eq": "A1"}, "score": {"gte": 80}},
  "columns": ["name", "score"],
  "order_by": "score",
  "descending": true,
  "limit": 5,
  "offset": 0
}
```

**Supported filter operators:** `eq`, `neq`, `gt`, `gte`, `lt`, `lte`, `like`, `in`

**Returns:**
```json
{
  "table": "students",
  "rows": [{"name": "Iris Nguyen", "score": 99.0}, ...],
  "total_returned": 2,
  "limit": 5,
  "offset": 0,
  "has_more": false,
  "next_offset": null
}
```

---

### `insert`

Insert a new row into a table. Returns the full stored record (including auto-generated `id`).

```json
{
  "table": "students",
  "values": {
    "name": "Zara Demo",
    "email": "zara@example.com",
    "cohort": "B3",
    "score": 88.5
  }
}
```

**Returns:**
```json
{
  "table": "students",
  "inserted": {"id": 11, "name": "Zara Demo", "cohort": "B3", "score": 88.5, ...}
}
```

---

### `aggregate`

Run `count`, `avg`, `sum`, `min`, or `max` queries with optional filters and group-by.

```json
{"table": "students", "metric": "count"}
{"table": "students", "metric": "avg", "column": "score", "group_by": "cohort"}
{"table": "enrollments", "metric": "min", "column": "grade", "filters": {"status": {"eq": "active"}}}
```

**Returns:**
```json
{
  "table": "students",
  "metric": "avg",
  "column": "score",
  "group_by": "cohort",
  "results": [
    {"cohort": "A1", "value": 88.16},
    {"cohort": "A2", "value": 73.25},
    ...
  ]
}
```

---

## Resources

### `schema://database`

Returns the full schema for all tables as JSON. Use this to discover available tables and columns before querying.

### `schema://table/{table_name}`

Returns schema for a single table.

Example: `schema://table/students` →
```json
{
  "table": "students",
  "columns": [
    {"cid": 0, "name": "id", "type": "INTEGER", "primary_key": true},
    {"cid": 1, "name": "name", "type": "TEXT", "notnull": true},
    ...
  ]
}
```

---

## Error handling

All tools reject unsafe or invalid input:

| Error case | Response |
|---|---|
| Unknown table name | `{"error": "Unknown table 'xyz'. Allowed: [...]"}` |
| Unknown column name | `{"error": "Unknown column 'xyz' in table '...'. Allowed: [...]"}` |
| Unsupported operator | `{"error": "Unsupported operator 'drop_table'. Allowed: [...]"}` |
| Unsupported metric | `{"error": "Unsupported metric 'xyz'. Allowed: [...]"}` |
| Empty insert | `{"error": "'values' must not be empty."}` |
| avg/sum/min/max without column | `{"error": "Metric 'avg' requires a 'column' argument."}` |

No raw user input is ever concatenated into SQL — all values use parameterized queries and all identifiers are validated against a live whitelist.

---

## MCP Inspector

```bash
cd implementation
./start_inspector.sh
```

Or manually:
```bash
mkdir -p .npm-cache
NPM_CONFIG_CACHE="$PWD/.npm-cache" npx -y @modelcontextprotocol/inspector \
  /ABSOLUTE/PATH/TO/.venv/bin/python \
  /ABSOLUTE/PATH/TO/implementation/mcp_server.py
```

Inspector checklist:
- [ ] 3 tools visible: `search`, `insert`, `aggregate`
- [ ] 2 resources visible: `schema://database`, `schema://table/{table_name}`
- [ ] Valid `search` call returns rows
- [ ] Invalid table name returns clear error

---

## Client configuration

### Gemini CLI

```bash
gemini mcp add sqlite-lab \
  /home/phucx314/Documents/Code\ Base/ai20k/day026/2A202600424-TaVinhPhuc-Day26/.venv/bin/python \
  /home/phucx314/Documents/Code\ Base/ai20k/day026/2A202600424-TaVinhPhuc-Day26/implementation/mcp_server.py \
  --description "SQLite Lab FastMCP server" \
  --timeout 10000

# Verify connection
gemini mcp list

# Smoke test
gemini --allowed-mcp-server-names sqlite-lab --yolo \
  -p "Use the sqlite-lab MCP server. Show me the top 3 students by score descending."
```

### Claude Code (`.mcp.json`)

```json
{
  "mcpServers": {
    "sqlite-lab": {
      "type": "stdio",
      "command": "/home/phucx314/Documents/Code Base/ai20k/day026/2A202600424-TaVinhPhuc-Day26/.venv/bin/python",
      "args": [
        "/home/phucx314/Documents/Code Base/ai20k/day026/2A202600424-TaVinhPhuc-Day26/implementation/mcp_server.py"
      ],
      "env": {}
    }
  }
}
```

After connecting, Claude Code can reference:
- `@sqlite-lab:schema://database` to read the full schema
- `@sqlite-lab:schema://table/students` for a specific table

---

## Example demo tasks

```
# 1. Search students in cohort A1 with score >= 80
search: table=students, filters={cohort: {eq: A1}, score: {gte: 80}}, order_by=score, descending=true

# 2. Insert a new student
insert: table=students, values={name: "Zara", email: "zara@demo.com", cohort: "B1", score: 91.0}

# 3. Count students per cohort
aggregate: table=students, metric=count, group_by=cohort

# 4. Average grade for active enrollments
aggregate: table=enrollments, metric=avg, column=grade, filters={status: {eq: active}}

# 5. Read full schema
resource: schema://database

# 6. Error case — unknown table
search: table=nonexistent_table  → error response
```

---

## Running with SSE transport (optional)

```bash
python mcp_server.py --transport sse --port 8000
# Server starts at http://localhost:8000/sse
```

---

## Verification summary

```bash
python verify_server.py    # 29/29 checks: DB, search, insert, aggregate, errors, schema
python -m pytest tests/ -v # 47/47 unit tests: all modules, all operators, all edge cases
```