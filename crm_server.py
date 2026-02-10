from __future__ import annotations

import json
import sqlite3
from datetime import datetime
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
DB_PATH = ROOT / "crm.db"
WEB_DIR = ROOT / "web"


def now_iso() -> str:
    return datetime.utcnow().isoformat(timespec="seconds") + "Z"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    with get_conn() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                source TEXT DEFAULT 'manual',
                status TEXT DEFAULT 'new',
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                company_name TEXT NOT NULL,
                primary_contact TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS opportunities (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                value REAL NOT NULL,
                stage TEXT DEFAULT 'prospecting',
                expected_close_date TEXT,
                created_at TEXT NOT NULL,
                FOREIGN KEY(customer_id) REFERENCES customers(id)
            );

            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title TEXT NOT NULL,
                owner TEXT NOT NULL,
                due_date TEXT,
                completed INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            );
            """
        )


class CRMHandler(BaseHTTPRequestHandler):
    def _send_json(self, payload: dict | list, status: HTTPStatus = HTTPStatus.OK) -> None:
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path: Path, content_type: str) -> None:
        data = path.read_bytes()
        self.send_response(HTTPStatus.OK)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _read_json(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def do_GET(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            return self._send_file(WEB_DIR / "index.html", "text/html; charset=utf-8")
        if path == "/app.js":
            return self._send_file(WEB_DIR / "app.js", "application/javascript; charset=utf-8")
        if path == "/styles.css":
            return self._send_file(WEB_DIR / "styles.css", "text/css; charset=utf-8")

        if path == "/health":
            return self._send_json({"status": "ok"})

        if path == "/api/summary":
            with get_conn() as conn:
                lead_count = conn.execute("SELECT COUNT(*) c FROM leads").fetchone()["c"]
                customer_count = conn.execute("SELECT COUNT(*) c FROM customers").fetchone()["c"]
                task_open = conn.execute("SELECT COUNT(*) c FROM tasks WHERE completed = 0").fetchone()["c"]
                value = conn.execute("SELECT COALESCE(SUM(value),0) v FROM opportunities").fetchone()["v"]
            return self._send_json(
                {
                    "leads": lead_count,
                    "customers": customer_count,
                    "open_tasks": task_open,
                    "pipeline_value": value,
                }
            )

        if path in {"/api/leads", "/api/customers", "/api/opportunities", "/api/tasks"}:
            table = path.split("/")[-1]
            with get_conn() as conn:
                rows = [dict(row) for row in conn.execute(f"SELECT * FROM {table} ORDER BY id DESC").fetchall()]
            return self._send_json(rows)

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        payload = self._read_json()

        if path == "/api/leads":
            required = ["name", "email"]
            if any(not payload.get(k) for k in required):
                return self._send_json({"error": "name and email are required"}, HTTPStatus.BAD_REQUEST)
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO leads(name,email,phone,source,status,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        payload["name"],
                        payload["email"],
                        payload.get("phone"),
                        payload.get("source", "manual"),
                        payload.get("status", "new"),
                        now_iso(),
                    ),
                )
                lead = dict(conn.execute("SELECT * FROM leads WHERE id = ?", (cur.lastrowid,)).fetchone())
            return self._send_json(lead, HTTPStatus.CREATED)

        if path == "/api/customers":
            required = ["company_name", "primary_contact", "email"]
            if any(not payload.get(k) for k in required):
                return self._send_json({"error": "company_name, primary_contact and email are required"}, HTTPStatus.BAD_REQUEST)
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO customers(company_name,primary_contact,email,phone,created_at) VALUES(?,?,?,?,?)",
                    (payload["company_name"], payload["primary_contact"], payload["email"], payload.get("phone"), now_iso()),
                )
                customer = dict(conn.execute("SELECT * FROM customers WHERE id = ?", (cur.lastrowid,)).fetchone())
            return self._send_json(customer, HTTPStatus.CREATED)

        if path == "/api/opportunities":
            required = ["customer_id", "title", "value"]
            if any(payload.get(k) in (None, "") for k in required):
                return self._send_json({"error": "customer_id, title and value are required"}, HTTPStatus.BAD_REQUEST)
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO opportunities(customer_id,title,value,stage,expected_close_date,created_at) VALUES(?,?,?,?,?,?)",
                    (
                        int(payload["customer_id"]),
                        payload["title"],
                        float(payload["value"]),
                        payload.get("stage", "prospecting"),
                        payload.get("expected_close_date"),
                        now_iso(),
                    ),
                )
                opportunity = dict(conn.execute("SELECT * FROM opportunities WHERE id = ?", (cur.lastrowid,)).fetchone())
            return self._send_json(opportunity, HTTPStatus.CREATED)

        if path == "/api/tasks":
            required = ["title", "owner"]
            if any(not payload.get(k) for k in required):
                return self._send_json({"error": "title and owner are required"}, HTTPStatus.BAD_REQUEST)
            with get_conn() as conn:
                cur = conn.execute(
                    "INSERT INTO tasks(title,owner,due_date,completed,created_at) VALUES(?,?,?,?,?)",
                    (payload["title"], payload["owner"], payload.get("due_date"), int(bool(payload.get("completed", False))), now_iso()),
                )
                task = dict(conn.execute("SELECT * FROM tasks WHERE id = ?", (cur.lastrowid,)).fetchone())
            return self._send_json(task, HTTPStatus.CREATED)

        self.send_error(HTTPStatus.NOT_FOUND, "Not Found")


def run(host: str = "0.0.0.0", port: int = 8000) -> None:
    init_db()
    server = ThreadingHTTPServer((host, port), CRMHandler)
    print(f"CRM server running at http://{host}:{port}")
    server.serve_forever()


if __name__ == "__main__":
    run()
