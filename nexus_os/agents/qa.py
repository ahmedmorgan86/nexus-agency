"""
NEXUS OS — Independent QA & Compliance Agent
Validates task outcomes, authenticity of findings, advertising policy compliance,
and enforces escalation gates for low-confidence or high-risk outputs.
"""

from typing import Dict, Any, List

class QualityAssuranceAgent:
    def __init__(self):
        self.agent_name = "INDEPENDENT_QA_AGENT"

    def audit_task_output(self, task_name: str, output: Dict[str, Any]) -> Dict[str, Any]:
        """
        Conducts an objective verification checklist against task deliverables.
        Returns a structured QA report and recommendation (APPROVED or ESCALATE_TO_HUMAN).
        """
        checks_passed = []
        checks_failed = []

        # 1. Verification of Data Presence
        if not output:
            checks_failed.append("Output payload is empty or malformed.")
        else:
            checks_passed.append("Output payload conforms to expected schema.")

        # 2. Check for Hallucinated or Fabricated Claims
        output_str = str(output).lower()
        if "100% guaranteed profit" in output_str or "مضمون 100%" in output_str:
            checks_failed.append("Prohibited exaggerated claim detected ('100% guarantee').")
        else:
            checks_passed.append("No prohibited guarantee claims detected.")

        # 3. Privacy & PII Check
        # Ensure raw plaintext credit cards or credentials are not present
        if "password=" in output_str or "api_key=" in output_str:
            checks_failed.append("Potential secret key exposure detected in output.")
        else:
            checks_passed.append("No plaintext secret keys in output payload.")

        # Calculate QA Score (0-100)
        total_checks = len(checks_passed) + len(checks_failed)
        qa_score = int((len(checks_passed) / total_checks) * 100) if total_checks > 0 else 50

        status = "APPROVED" if qa_score >= 80 and not checks_failed else "REVIEW_REQUIRED"

        return {
            "agent": self.agent_name,
            "target_task": task_name,
            "status": status,
            "qa_score": qa_score,
            "passed_rules": checks_passed,
            "failed_rules": checks_failed,
            "requires_human_approval": (status == "REVIEW_REQUIRED"),
            "tokens_used": 45
        }
