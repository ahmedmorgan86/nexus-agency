import unittest
from nexus_os.agents.scoring import LeadScoringAgent

class TestLeadScoring(unittest.TestCase):
    def setUp(self):
        self.agent = LeadScoringAgent()

    def test_high_priority_scoring(self):
        lead = {
            "name": "متجر لومينوس",
            "sector": "تجارة إلكترونية وعناية فاخرة",
            "phone": "+971501234567",
            "website": "https://luminousbotanicals.com",
            "benchmark_price": "$5,200 USD"
        }
        audit = {
            "findings": [
                {"severity": "HIGH", "remedy": "Fix checkout dropoff"},
                {"severity": "HIGH", "remedy": "Deploy video reels"}
            ]
        }
        res = self.agent.score_lead(lead, audit)
        self.assertGreaterEqual(res["total_score"], 80)
        self.assertIn("PRIORITY_TIER_A", res["tier"])
        self.assertEqual(len(res["breakdown"]), 4)

    def test_score_breakdown_math(self):
        lead = {"name": "شركة عامة", "sector": "خدمات عامة"}
        audit = {"findings": []}
        res = self.agent.score_lead(lead, audit)
        calculated_sum = sum(res["breakdown"].values())
        self.assertEqual(res["total_score"], calculated_sum)
        self.assertLessEqual(res["total_score"], 100)
        self.assertGreaterEqual(res["total_score"], 0)

if __name__ == "__main__":
    unittest.main()
