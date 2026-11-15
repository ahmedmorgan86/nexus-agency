import unittest
from nexus_os.learning import LearningEngine
from nexus_os.self_healing import SelfHealingEngine
from nexus_os.providers import ImageProvider, VideoProvider

class TestLearningAndHealing(unittest.TestCase):
    def test_learning_records_lesson(self):
        engine = LearningEngine.__new__(LearningEngine)
        engine.db = None
        engine.agent_name = "LEARNING_ENGINE"
        # bypass db by calling method directly if db not needed
        from nexus_os.learning import LearningEngine as LE
        le = LE.__new__(LE)
        le.agent_name = "LEARNING_ENGINE"
        res = le.record_lesson("t1", "AGENT", "done", "lesson")
        self.assertEqual(res["auto_code_change"], False)
        self.assertEqual(res["lesson"], "lesson")

    def test_self_healing(self):
        sh = SelfHealingEngine()
        res = sh.check_services({"db": True, "smtp": False})
        self.assertFalse(res["healthy"])
        self.assertIn("smtp", res["failed_services"])

    def test_providers_honest(self):
        ip = ImageProvider()
        vp = VideoProvider()
        # Without keys, should be NOT_CONFIGURED
        if not ip.api_key:
            self.assertEqual(ip.generate("x")["status"], "NOT_CONFIGURED")
        if not vp.api_key:
            self.assertEqual(vp.generate("x")["status"], "NOT_CONFIGURED")

if __name__ == "__main__":
    unittest.main()
