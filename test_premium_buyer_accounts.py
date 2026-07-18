import json
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import server


class PremiumBuyerAccountTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        root = Path(self.temp_dir.name)
        self.paths = {
            "MEMBERS_FILE": root / "members.json",
            "ORDERS_FILE": root / "orders.json",
            "SALES_FILE": root / "sales.json",
            "PASSWORD_SETUP_TOKENS_FILE": root / "password_setup_tokens.json",
            "PAYMENT_CONFIG_FILE": root / "payment_config.json",
            "COUPONS_FILE": root / "coupons.json",
            "MEMBER_SESSIONS_FILE": root / "member_sessions.json",
            "COURSE_TOKENS_FILE": root / "course_tokens.json",
        }
        self.originals = {name: getattr(server, name) for name in self.paths}
        for name, path in self.paths.items():
            setattr(server, name, str(path))
            path.write_text("[]" if name != "PAYMENT_CONFIG_FILE" else "{}", encoding="utf-8")
        server._member_sessions = {}

    def tearDown(self):
        for name, value in self.originals.items():
            setattr(server, name, value)
        self.temp_dir.cleanup()

    def write(self, name, data):
        Path(getattr(server, name)).write_text(json.dumps(data), encoding="utf-8")

    def read(self, name):
        return json.loads(Path(getattr(server, name)).read_text(encoding="utf-8"))

    def paid_order(self, order_id="PA-TEST-1", email="buyer@example.com"):
        return {
            "order_id": order_id,
            "date": "2026-07-18T10:00:00+00:00",
            "name": "Buyer",
            "email": email,
            "amount": 99,
            "status": "paid",
            "gateway_status": "AUTHORIZED",
            "cybersource_id": "TEST",
        }

    def test_new_buyer_is_idempotent_premium_pending_member(self):
        order = self.paid_order()
        first = server._upsert_premium_buyer(order)
        second = server._upsert_premium_buyer(order)
        members = self.read("MEMBERS_FILE")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(len(members), 1)
        self.assertTrue(members[0]["premium"])
        self.assertTrue(members[0]["password_pending"])
        self.assertEqual(members[0]["source_order_ids"], ["PA-TEST-1"])

    def test_existing_password_is_preserved_and_premium_is_immediate(self):
        password_hash = server._hash_password("existing-password")
        self.write("MEMBERS_FILE", [{
            "email": "buyer@example.com",
            "name": "Buyer",
            "password": password_hash,
            "active": True,
            "premium": False,
            "premium_since": "",
        }])
        result = server._upsert_premium_buyer(self.paid_order())
        member = self.read("MEMBERS_FILE")[0]
        self.assertFalse(result["needs_password_setup"])
        self.assertEqual(member["password"], password_hash)
        self.assertTrue(member["premium"])

    def test_setup_token_is_hashed_single_use_and_sets_password(self):
        server._upsert_premium_buyer(self.paid_order())
        raw = server._create_password_setup_token("buyer@example.com", "PA-TEST-1")
        stored = self.read("PASSWORD_SETUP_TOKENS_FILE")[0]
        self.assertNotEqual(stored["token_hash"], raw)
        server._consume_password_setup_token(raw, "new-password")
        member = self.read("MEMBERS_FILE")[0]
        self.assertFalse(member["password_pending"])
        self.assertTrue(server._verify_password("new-password", member["password"]))
        with self.assertRaises(ValueError):
            server._consume_password_setup_token(raw, "another-password")

    def test_expired_setup_token_is_rejected(self):
        server._upsert_premium_buyer(self.paid_order())
        raw = server._create_password_setup_token("buyer@example.com", "PA-TEST-1")
        tokens = self.read("PASSWORD_SETUP_TOKENS_FILE")
        tokens[0]["expires_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=1)
        ).isoformat()
        self.write("PASSWORD_SETUP_TOKENS_FILE", tokens)
        with self.assertRaisesRegex(ValueError, "expired"):
            server._consume_password_setup_token(raw, "new-password")

    def test_disabled_member_cannot_use_setup_token_to_reactivate(self):
        server._upsert_premium_buyer(self.paid_order())
        raw = server._create_password_setup_token("buyer@example.com", "PA-TEST-1")
        members = self.read("MEMBERS_FILE")
        members[0]["active"] = False
        self.write("MEMBERS_FILE", members)

        with self.assertRaisesRegex(ValueError, "disabled"):
            server._consume_password_setup_token(raw, "new-password")

        member = self.read("MEMBERS_FILE")[0]
        self.assertFalse(member["active"])
        self.assertTrue(member["password_pending"])

    def test_new_setup_token_invalidates_previous_token_and_throttles_resend(self):
        server._upsert_premium_buyer(self.paid_order())
        first = server._create_password_setup_token("buyer@example.com", "PA-TEST-1")
        self.assertFalse(server._setup_resend_allowed("buyer@example.com"))
        tokens = self.read("PASSWORD_SETUP_TOKENS_FILE")
        tokens[0]["created_at"] = (
            datetime.now(timezone.utc) - timedelta(minutes=10)
        ).isoformat()
        self.write("PASSWORD_SETUP_TOKENS_FILE", tokens)
        self.assertTrue(server._setup_resend_allowed("buyer@example.com"))
        server._create_password_setup_token("buyer@example.com", "PA-TEST-1")
        with self.assertRaisesRegex(ValueError, "invalid"):
            server._consume_password_setup_token(first, "new-password")

    def test_legacy_course_token_still_grants_access(self):
        raw = server._generate_course_token("legacy@example.com", "PA-LEGACY")
        valid, entry = server._validate_course_token(raw, "127.0.0.1")
        self.assertTrue(valid)
        self.assertEqual(entry["order_id"], "PA-LEGACY")
        self.assertEqual(entry["access_count"], 1)

    def test_buyer_emails_include_welcome_copy_and_course_action(self):
        messages = []

        def capture(msg, recipients, include_notify_cc=False):
            messages.append(msg)
            return [recipients] if isinstance(recipients, str) else recipients

        with patch.object(server, "_smtp_send", side_effect=capture):
            server._send_password_setup_email(
                "Buyer",
                "buyer@example.com",
                "setup-token",
                "https://example.com",
                order_id="PA-TEST-1",
            )
            server._send_premium_access_email(
                "Buyer",
                "buyer@example.com",
                "https://example.com",
                order_id="PA-TEST-2",
            )

        self.assertEqual(len(messages), 2)
        for message in messages:
            rendered = "\n".join(
                part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
                for part in message.walk()
                if part.get_content_type() in {"text/plain", "text/html"}
            )
            self.assertIn("Welcome to the Cinematography Workshop!", rendered)
            self.assertIn("professional film sets", rendered)
            self.assertIn("contact@pierreazar.com", rendered)
        first_rendered = "\n".join(
            part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            for part in messages[0].walk()
            if part.get_content_type() in {"text/plain", "text/html"}
        )
        second_rendered = "\n".join(
            part.get_payload(decode=True).decode(part.get_content_charset() or "utf-8")
            for part in messages[1].walk()
            if part.get_content_type() in {"text/plain", "text/html"}
        )
        self.assertIn("member/set-password", first_rendered)
        self.assertIn("member-login.html?next=/course", second_rendered)

    def test_payment_finalization_deduplicates_sale_and_notifications(self):
        order = self.paid_order()
        order["status"] = "pending"
        self.write("ORDERS_FILE", [order])
        setup_calls = []
        owner_calls = []
        with patch.object(
            server,
            "_issue_password_setup_email",
            side_effect=lambda *args, **kwargs: setup_calls.append(args[0]["order_id"]),
        ), patch.object(
            server,
            "_send_purchase_notification_email",
            side_effect=lambda *args, **kwargs: owner_calls.append(args[0]["order_id"]),
        ):
            server._finalize_paid_order(
                "PA-TEST-1",
                {"course_name": "Test", "return_base_url": "https://example.com"},
                payment_meta={"cybersource_id": "TEST", "status": "AUTHORIZED"},
            )
            server._finalize_paid_order(
                "PA-TEST-1",
                {"course_name": "Test", "return_base_url": "https://example.com"},
                payment_meta={"cybersource_id": "TEST", "status": "AUTHORIZED"},
            )
        self.assertEqual(len(self.read("SALES_FILE")), 1)
        self.assertEqual(setup_calls, ["PA-TEST-1"])
        self.assertEqual(owner_calls, ["PA-TEST-1"])
        saved_order = self.read("ORDERS_FILE")[0]
        self.assertTrue(saved_order["buyer_access_emailed"])
        self.assertTrue(saved_order["merchant_notified"])


if __name__ == "__main__":
    unittest.main()
