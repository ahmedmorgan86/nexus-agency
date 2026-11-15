import unittest
from nexus_os.agents.creative import CreativeStudioAgent
from nexus_os.agents.content import ContentFactoryAgent
from nexus_os.agents.qa import QualityAssuranceAgent

class TestAgentWorkflows(unittest.TestCase):
    def test_reels_storyboard_generation(self):
        agent = CreativeStudioAgent()
        res = agent.produce_reels_storyboard("أورا ديزاين", "أثاث فاخر", "تصميمات معاصرة")
        self.assertEqual(res["format"], "9:16_VERTICAL_REELS")
        self.assertEqual(len(res["scenes"]), 3)
        self.assertTrue(len(res["hook"]) > 10)
        self.assertIn("aspect_9_16_vertical", res["generation_prompts"])

    def test_content_factory_pack(self):
        agent = ContentFactoryAgent()
        res = agent.generate_campaign_content_pack("كلاود فيلو", "حلول برمجية B2B")
        self.assertTrue(res["posts_count"] >= 3)
        self.assertTrue(res["bilingual_supported"])

    def test_qa_agent_approval_and_rejection(self):
        agent = QualityAssuranceAgent()
        # Clean output
        clean_res = agent.audit_task_output("Test Task", {"leads": [1, 2, 3]})
        self.assertEqual(clean_res["status"], "APPROVED")

        # Output with prohibited guarantee
        bad_res = agent.audit_task_output("Bad Task", {"claim": "100% guaranteed profit"})
        self.assertEqual(bad_res["status"], "REVIEW_REQUIRED")
        self.assertTrue(bad_res["requires_human_approval"])

if __name__ == "__main__":
    unittest.main()
