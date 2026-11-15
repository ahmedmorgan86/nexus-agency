"""
NEXUS OS — Financial Intelligence & Unit Economics Agent
Tracks API token consumption, calculates Cost Per Task and Estimated CAC,
and enforces automated daily spending caps to prevent runaway expenses.
"""

from typing import Dict, Any
from nexus_os.storage import DatabaseManager

class FinancialIntelligenceAgent:
    def __init__(self, db: DatabaseManager, daily_budget_cap_usd: float = 25.0):
        self.db = db
        self.daily_budget_cap_usd = daily_budget_cap_usd
        self.agent_name = "FINANCIAL_INTELLIGENCE_AGENT"

    def record_usage(self, agent_name: str, prompt_tokens: int, completion_tokens: int, task_id: str = None) -> Dict[str, Any]:
        """
        Records token consumption and validates against spending thresholds.
        """
        self.db.log_cost(agent_name, prompt_tokens, completion_tokens, task_id)
        summary = self.db.get_financial_summary()
        current_spend = summary["total_cost_usd"]

        budget_alert = False
        pause_operations = False

        if current_spend >= self.daily_budget_cap_usd:
            budget_alert = True
            pause_operations = True
        elif current_spend >= (self.daily_budget_cap_usd * 0.8):
            budget_alert = True

        return {
            "agent": self.agent_name,
            "current_spend_usd": current_spend,
            "budget_cap_usd": self.daily_budget_cap_usd,
            "budget_alert": budget_alert,
            "pause_operations": pause_operations,
            "total_tokens_consumed": summary["total_prompt_tokens"] + summary["total_completion_tokens"],
            "summary": summary
        }
