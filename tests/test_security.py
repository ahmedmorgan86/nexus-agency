import unittest
from nexus_os.security import mask_phone, mask_email, sanitize_input, check_tenant_access, is_authorized_operation

class TestSecurityModule(unittest.TestCase):
    def test_mask_phone(self):
        masked = mask_phone("+201210237652")
        self.assertEqual(masked, "+2012****652")
        self.assertNotIn("10237", masked)

    def test_mask_email(self):
        masked = mask_email("ahmed.morgan2009@gmail.com")
        self.assertIn("@gmail.com", masked)
        self.assertNotIn("morgan", masked)

    def test_sanitize_input(self):
        dirty = "<script>alert('xss')</script>"
        clean = sanitize_input(dirty)
        self.assertNotIn("<script>", clean)
        self.assertIn("&lt;script&gt;", clean)

    def test_tenant_isolation(self):
        self.assertTrue(check_tenant_access("tenant_a", "tenant_a"))
        self.assertFalse(check_tenant_access("tenant_a", "tenant_b"))
        self.assertFalse(check_tenant_access("", "tenant_a"))

    def test_authorized_operations_gating(self):
        # High risk actions must require approval
        self.assertFalse(is_authorized_operation("OUTREACH_SEND_WHATSAPP", requires_approval=True))
        self.assertFalse(is_authorized_operation("PUBLISH_CAMPAIGN_PAID", requires_approval=True))
        # Normal research actions are permitted autonomously
        self.assertTrue(is_authorized_operation("RESEARCH_MARKET", requires_approval=True))

if __name__ == "__main__":
    unittest.main()
