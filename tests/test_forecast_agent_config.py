"""TransactionCase tests for ``tommasi.forecast.agent.config`` HTTPS and uniqueness."""

from unittest.mock import patch

from odoo.exceptions import ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase
from odoo.tools import config

SECRET_API_KEY = "tfd-test-api-key-9f3c2e1b"
SECRET_HMAC = "tfd-test-hmac-secret-7a1b4d8e"


@tagged("post_install", "-at_install")
class TestForecastAgentConfig(TransactionCase):
    """HTTPS pin, unique company, optional assistant, and copy of secrets."""

    def _vals(self, **overrides):
        vals = {
            "company_id": self.env.company.id,
            "edge_url": "https://edge.example.test",
            "api_key": SECRET_API_KEY,
            "hmac_secret": SECRET_HMAC,
        }
        vals.update(overrides)
        return vals

    def _model(self):
        return self.env["tommasi.forecast.agent.config"]

    def test_http_save_rejected_when_https_required(self):
        """HTTP edge URLs must be rejected when HTTPS is required."""
        Config = self._model()
        with patch.object(type(Config), "_https_required", return_value=True):
            with self.assertRaises(ValidationError) as ctx:
                Config.create(self._vals(edge_url="http://edge.example.test"))
        self.assertNotIn(SECRET_API_KEY, str(ctx.exception))
        self.assertNotIn(SECRET_HMAC, str(ctx.exception))

    def test_http_allowed_under_test_enable(self):
        """HTTP edge URLs are accepted when Odoo ``test_enable`` is active."""
        self.assertTrue(config.get("test_enable"))
        rec = self._model().create(self._vals(edge_url="http://edge.example.test"))
        self.assertEqual(rec.edge_url, "http://edge.example.test")
        self.assertEqual(rec.api_key, SECRET_API_KEY)
        self.assertEqual(rec.hmac_secret, SECRET_HMAC)

    def test_duplicate_company_rejected(self):
        """A second config for the same company must be rejected."""
        Config = self._model()
        Config.create(self._vals())
        with self.assertRaises(ValidationError) as ctx:
            Config.create(self._vals())
        self.assertNotIn(SECRET_API_KEY, str(ctx.exception))
        self.assertNotIn(SECRET_HMAC, str(ctx.exception))

    def test_assistant_id_is_optional(self):
        """Configs without assistant_id remain valid; stored ids stay on the row."""
        Config = self._model()
        rec = Config.create(self._vals())
        self.assertFalse(rec.assistant_id)
        rec.write({"assistant_id": "asst_stored_only"})
        self.assertEqual(rec.assistant_id, "asst_stored_only")

    def test_copy_omits_secrets(self):
        """Duplicating a config must not copy api_key or hmac_secret."""
        rec = self._model().create(self._vals())
        other_company = self.env["res.company"].create({"name": "Forecast Copy Co"})
        copied = rec.copy({"company_id": other_company.id})
        self.assertFalse(copied.api_key)
        self.assertFalse(copied.hmac_secret)
        self.assertEqual(copied.company_id, other_company)
        self.assertEqual(copied.edge_url, rec.edge_url)
