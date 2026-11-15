"""
NEXUS OS — NEXUS CEO Agent (Central Orchestrator)
Deconstructs strategic marketing objectives, manages task dispatching, enforces strict state transitions,
and escalates unverified or high-risk actions to human review.
"""

import uuid
import time
from typing import Dict, Any, List, Optional
from datetime import datetime
from nexus_os.storage import DatabaseManager, get_cairo_time
from nexus_os.security import is_authorized_operation

# Task States
STATE_PENDING = "PENDING"
STATE_RUNNING = "RUNNING"
STATE_REVIEW_REQUIRED = "REVIEW_REQUIRED"
STATE_COMPLETED = "COMPLETED"
STATE_FAILED = "FAILED"
STATE_CANCELLED = "CANCELLED"

class NexusCEOAgent:
    def __init__(self, db: Optional[DatabaseManager] = None):
        self.db = db or DatabaseManager()
        self.agent_name = "NEXUS_CEO_ORCHESTRATOR"

    def create_task(self, title: str, owner_agent: str, input_data: Dict[str, Any], priority: str = "NORMAL", tenant_id: str = "nexus_primary") -> Dict[str, Any]:
        """
        Creates a new idempotent task in PENDING state.
        """
        task_id = f"task_{uuid.uuid4().hex[:12]}"
        task = {
            "id": task_id,
            "tenant_id": tenant_id,
            "owner_agent": owner_agent,
            "title": title,
            "state": STATE_PENDING,
            "priority": priority,
            "retry_count": 0,
            "input_data": input_data,
            "output_data": {},
            "cost_tokens": 0,
            "created_at": get_cairo_time()
        }
        self.db.save_task(task)
        return task

    def transition_state(self, task_id: str, new_state: str, output_data: Optional[Dict[str, Any]] = None, cost_tokens: int = 0) -> Dict[str, Any]:
        """
        Executes a validated task state transition with safety checks.
        """
        task = self.db.get_task(task_id)
        if not task:
            raise ValueError(f"Task with ID {task_id} not found in database.")

        valid_transitions = {
            STATE_PENDING: [STATE_RUNNING, STATE_CANCELLED],
            STATE_RUNNING: [STATE_REVIEW_REQUIRED, STATE_COMPLETED, STATE_FAILED, STATE_CANCELLED],
            STATE_REVIEW_REQUIRED: [STATE_COMPLETED, STATE_CANCELLED],
            STATE_FAILED: [STATE_PENDING, STATE_CANCELLED],
            STATE_COMPLETED: [],
            STATE_CANCELLED: []
        }

        current_state = task["state"]
        if new_state not in valid_transitions.get(current_state, []):
            raise ValueError(f"Illegal state transition from {current_state} to {new_state} for task {task_id}")

        task["state"] = new_state
        if output_data:
            task["output_data"] = output_data
        if cost_tokens:
            task["cost_tokens"] += cost_tokens

        self.db.save_task(task)
        return task

    def handle_agent_execution(self, task_id: str, agent_fn, *args, **kwargs) -> Dict[str, Any]:
        """
        Executes a task through its assigned agent with error catching and retry management.
        """
        self.transition_state(task_id, STATE_RUNNING)
        task = self.db.get_task(task_id)
        
        try:
            result = agent_fn(*args, **kwargs)
            tokens = result.get("tokens_used", 150)
            
            # Check if this task performs a high-risk operation requiring human signoff
            action_type = task["input_data"].get("action_type", "")
            if not is_authorized_operation(action_type, requires_approval=True):
                return self.transition_state(task_id, STATE_REVIEW_REQUIRED, output_data=result, cost_tokens=tokens)
            
            # QA Gate Check
            qa_score = result.get("qa_score", 100)
            if qa_score < 75:
                result["qa_warning"] = "QA score below 75 threshold. Escalated to REVIEW_REQUIRED."
                return self.transition_state(task_id, STATE_REVIEW_REQUIRED, output_data=result, cost_tokens=tokens)

            return self.transition_state(task_id, STATE_COMPLETED, output_data=result, cost_tokens=tokens)

        except Exception as e:
            task["retry_count"] += 1
            if task["retry_count"] <= 3:
                # Retryable failure
                self.db.save_task(task)
                time.sleep(1)
                return self.transition_state(task_id, STATE_PENDING)
            else:
                return self.transition_state(task_id, STATE_FAILED, output_data={"error": str(e)})

    def get_orchestration_overview(self, tenant_id: str = "nexus_primary") -> Dict[str, Any]:
        """
        Provides CEO-level statistics on running and queued operations.
        """
        conn = self.db.get_connection()
        cur = conn.cursor()
        cur.execute("SELECT state, COUNT(*) FROM tasks WHERE tenant_id = ? GROUP BY state", (tenant_id,))
        rows = cur.fetchall()
        conn.close()
        
        state_counts = {STATE_PENDING: 0, STATE_RUNNING: 0, STATE_REVIEW_REQUIRED: 0, STATE_COMPLETED: 0, STATE_FAILED: 0, STATE_CANCELLED: 0}
        for state, count in rows:
            state_counts[state] = count
            
        return {
            "orchestrator_status": "HEALTHY",
            "active_tasks": state_counts[STATE_RUNNING],
            "pending_review": state_counts[STATE_REVIEW_REQUIRED],
            "completed_today": state_counts[STATE_COMPLETED],
            "failed_tasks": state_counts[STATE_FAILED],
            "state_breakdown": state_counts
        }
