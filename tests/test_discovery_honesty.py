"""Honesty tests: unconfigured providers must say so, and must never invent results."""
import os
import unittest
from unittest import mock

from nexus_os.agents.discovery import LeadDiscoveryAgent
from nexus_os.providers import GeminiImageProvider, GeminiVideoProvider, provider_status


class TestDiscoveryHonesty(unittest.TestCase):
    def test_missing_key_returns_not_configured_without_leads(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": ""}, clear=False):
            res = LeadDiscoveryAgent().discover_leads()
        self.assertEqual(res["status"], "NOT_CONFIGURED")
        self.assertEqual(res["leads"], [])
        self.assertEqual(res["count"], 0)
        self.assertIsNone(res["qa_score"])
        self.assertEqual(res["qa_score_basis"], "NOT_COMPUTED")
        self.assertIn("fabricated", res["message"].lower())

    def test_provider_error_is_reported_not_swallowed(self):
        agent = LeadDiscoveryAgent(api_key="fake-key-for-test")

        def boom(_prompt):
            raise RuntimeError("network down")

        with mock.patch.object(agent, "_grounded_call", side_effect=boom):
            res = agent.discover_leads()
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["leads"], [])
        self.assertIn("network down", res["message"])
        self.assertIsNone(res["qa_score"])

    def test_grounding_sources_are_extracted(self):
        payload = {"candidates": [{"groundingMetadata": {"groundingChunks": [
            {"web": {"uri": "https://a.example"}}, {"web": {"uri": "https://b.example"}},
            {"web": {"uri": "https://a.example"}},
        ]}}]}
        self.assertEqual(LeadDiscoveryAgent._sources_from_grounding(payload),
                         ["https://a.example", "https://b.example"])

    def test_leads_carry_no_fabricated_confidence(self):
        agent = LeadDiscoveryAgent(api_key="fake-key-for-test")
        response = {
            "candidates": [{"content": {"parts": [{
                "text": '[{"name":"Real Co","sector":"Retail","website":"https://real.example",'
                        '"phone":"","observations":"thin IG presence","source_url":"https://real.example/about"}]',
            }]}}],
            "usageMetadata": {"totalTokenCount": 42},
        }
        with mock.patch.object(agent, "_grounded_call", return_value=response):
            res = agent.discover_leads()
        self.assertEqual(res["status"], "SUCCESS")
        lead = res["leads"][0]
        self.assertIsNone(lead["confidence_score"])
        self.assertFalse(lead["phone_verified"])
        self.assertEqual(lead["verification_status"], "DISCOVERED")
        self.assertEqual(res["tokens_used"], 42)


class TestProviderStatus(unittest.TestCase):
    def test_unconfigured_media_providers(self):
        with mock.patch.dict(os.environ, {
            "GEMINI_API_KEY": "", "IMAGE_PROVIDER_URL": "", "IMAGE_PROVIDER_API_KEY": "",
            "VIDEO_PROVIDER_URL": "", "VIDEO_PROVIDER_API_KEY": "", "GEMINI_VIDEO_MODEL": "",
        }, clear=False):
            self.assertEqual(GeminiImageProvider().generate("x")["status"], "NOT_CONFIGURED")
            self.assertEqual(GeminiVideoProvider().generate("x")["status"], "NOT_CONFIGURED")
            status = provider_status()
        self.assertFalse(status["image"]["configured"])
        self.assertFalse(status["video"]["configured"])
        self.assertEqual(status["image"]["status"], "NOT_CONFIGURED")

    def test_gemini_image_reports_configured_from_key(self):
        with mock.patch.dict(os.environ, {"GEMINI_API_KEY": "k", "GEMINI_IMAGE_MODEL": "m"}, clear=False):
            status = provider_status()
        self.assertTrue(status["image"]["configured"])
        self.assertEqual(status["image"]["model"], "m")


if __name__ == "__main__":
    unittest.main()
