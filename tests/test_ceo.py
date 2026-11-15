import unittest
import os
from nexus_os.storage import DatabaseManager
from nexus_os.ceo import (
    NexusCEOAgent, 
    STATE_PENDING, 
    STATE_RUNNING, 
    STATE_REVIEW_REQUIRED, 
    STATE_COMPLETED, 
    STATE_FAILED
)

class TestCEOOrchestrator(unittest.TestCase):
    def setUp(self):
        self.test_db_path = "test_nexus.db"
        self.db = DatabaseManager(self.test_db_path)
        self.ceo = NexusCEOAgent(self.db)

    def tearDown(self):
        if os.path.exists(self.test_db_path):
            try:
                os.remove(self.test_db_path)
            except Exception:
                pass

    def test_task_lifecycle(self):
        task = self.ceo.create_task("Test Lead Audit", "INTEL_AGENT", {"target": "demo.com"})
        self.assertEqual(task["state"], STATE_PENDING)

        # Transition to RUNNING
        t_running = self.ceo.transition_state(task["id"], STATE_RUNNING)
        self.assertEqual(t_running["state"], STATE_RUNNING)

        # Transition to COMPLETED
        t_completed = self.ceo.transition_state(task["id"], STATE_COMPLETED, output_data={"verified": True})
        self.assertEqual(t_completed["state"], STATE_COMPLETED)
        self.assertTrue(t_completed["output_data"]["verified"])

    def test_illegal_state_transition(self):
        task = self.ceo.create_task("Test Error", "INTEL_AGENT", {})
        # Cannot jump from PENDING directly to COMPLETED without RUNNING
        with self.assertRaises(ValueError):
            self.ceo.transition_state(task["id"], STATE_COMPLETED)

if __name__ == "__main__":
    unittest.main()
