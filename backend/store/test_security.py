from django.test import Client, TestCase, override_settings

from .models import AuthThrottle


class AuthThrottleTests(TestCase):
    def test_manager_limit_shared_with_web_and_spoofed_header_ignored(self):
        with override_settings(ARAK_TRUST_REAL_IP=False):
            client = Client()
            for index in range(10):
                response = client.post("/api/admin/session", data="{}", content_type="application/json",
                                       REMOTE_ADDR="192.0.2.10", HTTP_X_REAL_IP=f"192.0.2.{index + 20}")
                self.assertEqual(response.status_code, 401)
            blocked = client.post("/manager/login/", REMOTE_ADDR="192.0.2.10")
            self.assertEqual(blocked.status_code, 429)
            self.assertGreater(int(blocked["Retry-After"]), 0)
            self.assertEqual(client.post("/api/admin/session", data="{}", content_type="application/json",
                                        REMOTE_ADDR="192.0.2.11").status_code, 401)
            self.assertEqual(AuthThrottle.objects.count(), 2)
            self.assertFalse(AuthThrottle.objects.filter(key__contains="192.0.2").exists())

    def test_non_auth_routes_not_throttled(self):
        for _ in range(12):
            self.assertEqual(self.client.get("/api/health").status_code, 200)
        self.assertFalse(AuthThrottle.objects.exists())
