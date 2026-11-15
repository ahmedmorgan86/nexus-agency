"""
NEXUS OS — Durable Relational Storage & Multi-Tenant Database
Manages persistent records for Tasks, Leads, CRM Pipelines, Campaigns, and Financial Logs.
"""

import sqlite3
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

DB_FILE = os.environ.get("NEXUS_DB_PATH", os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "nexus_agency.db"))

def get_cairo_time() -> str:
    tz = timezone(timedelta(hours=2))
    return datetime.now(tz).strftime("%Y-%m-%d %I:%M:%S %p")

def init_db(db_path: str = DB_FILE):
    """
    Initializes database tables with strict multi-tenant isolation and indexing.
    """
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()

    # 1. Tenants Table
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tenants (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        plan TEXT DEFAULT 'ENTERPRISE',
        created_at TEXT NOT NULL,
        status TEXT DEFAULT 'ACTIVE'
    )
    """)

    # 2. Tasks Table (CEO Orchestrator Queue)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS tasks (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        owner_agent TEXT NOT NULL,
        title TEXT NOT NULL,
        state TEXT NOT NULL,
        priority TEXT DEFAULT 'NORMAL',
        retry_count INTEGER DEFAULT 0,
        input_data TEXT,
        output_data TEXT,
        cost_tokens INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    )
    """)

    # 3. Leads Table (Protected CRM & Prospect Sourcing)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS leads (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        name TEXT NOT NULL,
        sector TEXT NOT NULL,
        market TEXT,
        website TEXT,
        phone TEXT,
        benchmark_price TEXT,
        score INTEGER DEFAULT 0,
        score_breakdown TEXT,
        crm_status TEXT DEFAULT 'DISCOVERED',
        audit_notes TEXT,
        custom_pitch TEXT,
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    )
    """)

    # 4. Campaigns & Client Projects
    cur.execute("""
    CREATE TABLE IF NOT EXISTS campaigns (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        lead_id TEXT,
        title TEXT NOT NULL,
        status TEXT DEFAULT 'PLANNING',
        budget_usd REAL DEFAULT 0.0,
        target_roas REAL DEFAULT 4.0,
        metrics_json TEXT,
        created_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id),
        FOREIGN KEY(lead_id) REFERENCES leads(id)
    )
    """)

    # 5. Creative Assets & Reels Production
    cur.execute("""
    CREATE TABLE IF NOT EXISTS creative_assets (
        id TEXT PRIMARY KEY,
        tenant_id TEXT NOT NULL,
        lead_id TEXT,
        asset_type TEXT NOT NULL,
        hook TEXT,
        storyboard_json TEXT,
        prompt TEXT NOT NULL,
        qa_status TEXT DEFAULT 'PENDING',
        qa_score INTEGER DEFAULT 0,
        created_at TEXT NOT NULL,
        FOREIGN KEY(tenant_id) REFERENCES tenants(id)
    )
    """)

    # 6. Financial & Token Consumption Logs
    cur.execute("""
    CREATE TABLE IF NOT EXISTS cost_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        task_id TEXT,
        agent_name TEXT NOT NULL,
        prompt_tokens INTEGER DEFAULT 0,
        completion_tokens INTEGER DEFAULT 0,
        cost_usd REAL DEFAULT 0.0,
        timestamp TEXT NOT NULL
    )
    """)

    # 7. Security & Audit Trail
    cur.execute("""
    CREATE TABLE IF NOT EXISTS audit_logs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tenant_id TEXT NOT NULL,
        actor TEXT NOT NULL,
        action TEXT NOT NULL,
        details TEXT,
        timestamp TEXT NOT NULL
    )
    """)

    # Default Enterprise Tenant Seed
    cur.execute("SELECT id FROM tenants WHERE id = 'nexus_primary'")
    if not cur.fetchone():
        cur.execute("""
        INSERT INTO tenants (id, name, plan, created_at, status)
        VALUES ('nexus_primary', 'NEXUS Global Operations', 'ENTERPRISE_UNLIMITED', ?, 'ACTIVE')
        """, (get_cairo_time(),))

    conn.commit()
    conn.close()

class DatabaseManager:
    def __init__(self, db_path: str = DB_FILE):
        self.db_path = db_path
        init_db(self.db_path)

    def get_connection(self):
        return sqlite3.connect(self.db_path)

    # TASK MANAGEMENT
    def save_task(self, task: Dict[str, Any]):
        conn = self.get_connection()
        cur = conn.cursor()
        now = get_cairo_time()
        cur.execute("""
        INSERT OR REPLACE INTO tasks 
        (id, tenant_id, owner_agent, title, state, priority, retry_count, input_data, output_data, cost_tokens, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            task["id"],
            task.get("tenant_id", "nexus_primary"),
            task["owner_agent"],
            task["title"],
            task["state"],
            task.get("priority", "NORMAL"),
            task.get("retry_count", 0),
            json.dumps(task.get("input_data", {}), ensure_ascii=False),
            json.dumps(task.get("output_data", {}), ensure_ascii=False),
            task.get("cost_tokens", 0),
            task.get("created_at", now),
            now
        ))
        conn.commit()
        conn.close()

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM tasks WHERE id = ?", (task_id,))
        row = cur.fetchone()
        conn.close()
        if not row:
            return None
        return {
            "id": row[0],
            "tenant_id": row[1],
            "owner_agent": row[2],
            "title": row[3],
            "state": row[4],
            "priority": row[5],
            "retry_count": row[6],
            "input_data": json.loads(row[7]) if row[7] else {},
            "output_data": json.loads(row[8]) if row[8] else {},
            "cost_tokens": row[9],
            "created_at": row[10],
            "updated_at": row[11]
        }

    # LEAD & CRM MANAGEMENT
    def save_lead(self, lead: Dict[str, Any], tenant_id: str = "nexus_primary"):
        conn = self.get_connection()
        cur = conn.cursor()
        now = get_cairo_time()
        cur.execute("""
        INSERT OR REPLACE INTO leads
        (id, tenant_id, name, sector, market, website, phone, benchmark_price, score, score_breakdown, crm_status, audit_notes, custom_pitch, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            lead["id"],
            tenant_id,
            lead["name"],
            lead.get("sector", "تجارة وخدمات"),
            lead.get("market", "إقليمي"),
            lead.get("website", ""),
            lead.get("phone", ""),
            lead.get("benchmark_price", "$3,500"),
            lead.get("score", 0),
            json.dumps(lead.get("score_breakdown", {}), ensure_ascii=False),
            lead.get("crm_status", "DISCOVERED"),
            lead.get("audit_notes", ""),
            lead.get("custom_pitch", ""),
            lead.get("created_at", now),
            now
        ))
        conn.commit()
        conn.close()

    def get_all_leads(self, tenant_id: str = "nexus_primary") -> List[Dict[str, Any]]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT * FROM leads WHERE tenant_id = ? ORDER BY score DESC", (tenant_id,))
        rows = cur.fetchall()
        conn.close()
        leads = []
        for r in rows:
            leads.append({
                "id": r[0],
                "tenant_id": r[1],
                "name": r[2],
                "sector": r[3],
                "market": r[4],
                "website": r[5],
                "phone": r[6],
                "benchmark_price": r[7],
                "score": r[8],
                "score_breakdown": json.loads(r[9]) if r[9] else {},
                "crm_status": r[10],
                "audit_notes": r[11],
                "custom_pitch": r[12],
                "created_at": r[13],
                "updated_at": r[14]
            })
        return leads

    # FINANCIAL AUDITING
    def log_cost(self, agent_name: str, prompt_tokens: int, completion_tokens: int, task_id: Optional[str] = None, tenant_id: str = "nexus_primary"):
        # Pricing model: $0.15 per 1M prompt tokens, $0.60 per 1M completion tokens (Gemini Flash standard)
        cost = (prompt_tokens / 1_000_000 * 0.15) + (completion_tokens / 1_000_000 * 0.60)
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
        INSERT INTO cost_logs (tenant_id, task_id, agent_name, prompt_tokens, completion_tokens, cost_usd, timestamp)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (tenant_id, task_id, agent_name, prompt_tokens, completion_tokens, cost, get_cairo_time()))
        conn.commit()
        conn.close()

    def get_financial_summary(self, tenant_id: str = "nexus_primary") -> Dict[str, Any]:
        conn = self.get_connection()
        cur = conn.cursor()
        cur.execute("""
        SELECT SUM(prompt_tokens), SUM(completion_tokens), SUM(cost_usd), COUNT(*)
        FROM cost_logs WHERE tenant_id = ?
        """, (tenant_id,))
        row = cur.fetchone()
        conn.close()
        return {
            "total_prompt_tokens": row[0] or 0,
            "total_completion_tokens": row[1] or 0,
            "total_cost_usd": round(row[2] or 0.0, 4),
            "operations_count": row[3] or 0
        }
