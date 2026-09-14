"""TransactionCase tests for forecast agent config secrets and ACL isolation."""

import json
import logging
from unittest.mock import MagicMock, patch

from lxml import etree

from odoo import fields
from odoo.exceptions import AccessError, UserError, ValidationError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase, new_test_user

SECRET_API_KEY = "tfd-acl-api-key-c4e8a201"
SECRET_HMAC = "tfd-acl-hmac-secret-b7d3f019"
LOGGER_NAME = "odoo.addons.tommasi_forecast_demand.models.forecast_agent_config"


@tagged("post_install", "-at_install")
class TestForecastAgentAcl(TransactionCase):
    """Secrets stay out of errors, exports, and logs; manager-only company ACL."""

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

    def test_secrets_absent_from_usererror(self):
        """Validation errors must not echo api_key or hmac_secret."""
        Config = self._model()
        leaky_url = "http://%s:%s@edge.example.test" % (SECRET_API_KEY, SECRET_HMAC)
        with patch.object(type(Config), "_https_required", return_value=True):
            with self.assertRaises(UserError) as ctx:
                Config.create(self._vals(edge_url=leaky_url))
        message = str(ctx.exception)
        self.assertNotIn(SECRET_API_KEY, message)
        self.assertNotIn(SECRET_HMAC, message)

    def test_secrets_absent_from_export_data(self):
        """Export data must omit stored api_key and hmac_secret values."""
        rec = self._model().create(self._vals())
        exported = rec.export_data(["edge_url", "api_key", "hmac_secret"])
        rows = exported.get("datas") or []
        self.assertTrue(rows)
        row = rows[0]
        self.assertEqual(row[0], rec.edge_url)
        self.assertFalse(row[1])
        self.assertFalse(row[2])
        blob = str(exported)
        self.assertNotIn(SECRET_API_KEY, blob)
        self.assertNotIn(SECRET_HMAC, blob)

    def test_secrets_absent_from_logs(self):
        """Logger output during a rejected save must not contain secrets."""
        Config = self._model()
        leaky_url = "http://%s:%s@edge.example.test" % (SECRET_API_KEY, SECRET_HMAC)
        captured = []

        class _Handler(logging.Handler):
            def emit(self, record):
                captured.append(record.getMessage())

        handler = _Handler()
        handler.setLevel(logging.DEBUG)
        odoo_logger = logging.getLogger("odoo")
        addon_logger = logging.getLogger(LOGGER_NAME)
        odoo_logger.addHandler(handler)
        addon_logger.addHandler(handler)
        try:
            with patch.object(type(Config), "_https_required", return_value=True):
                with self.assertRaises(ValidationError):
                    Config.create(self._vals(edge_url=leaky_url))
        finally:
            odoo_logger.removeHandler(handler)
            addon_logger.removeHandler(handler)
        combined = "\n".join(captured)
        self.assertNotIn(SECRET_API_KEY, combined)
        self.assertNotIn(SECRET_HMAC, combined)

    def test_manager_crud_allowed(self):
        """LLM managers can create, read, write, and unlink their company config."""
        manager = new_test_user(
            self.env,
            login="tfd_forecast_mgr",
            groups="llm.group_llm_manager",
            company_id=self.env.company.id,
            company_ids=[(6, 0, [self.env.company.id])],
        )
        Config = self._model().with_user(manager)
        rec = Config.create(self._vals())
        found = Config.search([("id", "=", rec.id)])
        self.assertEqual(found, rec)
        rec.write({"edge_url": "https://edge-updated.example.test"})
        self.assertEqual(rec.edge_url, "https://edge-updated.example.test")
        rec.unlink()
        self.assertFalse(Config.search([("id", "=", rec.id)]))

    def test_non_manager_denied(self):
        """Users without llm.group_llm_manager cannot search or read config."""
        user = new_test_user(
            self.env,
            login="tfd_forecast_user",
            groups="base.group_user",
        )
        rec = self._model().create(self._vals())
        Config = self._model().with_user(user)
        with self.assertRaises(AccessError):
            Config.search([])
        with self.assertRaises(AccessError):
            rec.with_user(user).read(["edge_url"])

    def test_other_company_isolated(self):
        """Managers must not see another company's forecast agent config."""
        company_b = self.env["res.company"].create({"name": "Forecast Isolated Co"})
        manager_a = new_test_user(
            self.env,
            login="tfd_forecast_mgr_a",
            groups="llm.group_llm_manager",
            company_id=self.env.company.id,
            company_ids=[(6, 0, [self.env.company.id])],
        )
        config_a = self._model().create(self._vals())
        config_b = self._model().create(
            self._vals(
                company_id=company_b.id,
                edge_url="https://edge-b.example.test",
            )
        )
        Config = self._model().with_user(manager_a)
        found = Config.search([])
        self.assertIn(config_a, found)
        self.assertNotIn(config_b, found)
        with self.assertRaises(AccessError):
            config_b.with_user(manager_a).read(["edge_url"])

    def _run_model(self):
        return self.env["tommasi.forecast.agent.run"]

    def _assert_readonly_field(self, root, name):
        nodes = root.xpath("//field[@name='%s']" % name)
        self.assertTrue(nodes, "form is missing field %s" % name)
        node = nodes[0]
        readonly_attr = (node.get("readonly") or "").lower()
        modifiers = json.loads(node.get("modifiers") or "{}")
        self.assertTrue(
            readonly_attr in ("1", "true") or modifiers.get("readonly"),
            "%s must be read-only on the manager form" % name,
        )

    def test_manager_run_form_sanitized(self):
        """Manager form shows read-only sanitized diagnostics and no prompt."""
        manager = new_test_user(
            self.env,
            login="tfd_forecast_run_mgr",
            groups="llm.group_llm_manager",
            company_id=self.env.company.id,
            company_ids=[(6, 0, [self.env.company.id])],
        )
        config = self._model().create(self._vals())
        run = self._run_model()._enqueue(config)
        run.write(
            {
                "state": "running",
                "attempt_count": 1,
                "started_at": fields.Datetime.now(),
            }
        )
        leaky = json.dumps(
            {"ok": True, "api_key": SECRET_API_KEY, "hmac_secret": SECRET_HMAC}
        )
        response = MagicMock()
        response.status_code = 200
        response.headers = {}
        response.text = leaky
        response.content = leaky.encode("utf-8")
        post_path = (
            "odoo.addons.tommasi_forecast_demand.models.forecast_agent_hmac."
            "requests.post"
        )
        with patch(post_path, return_value=response):
            run._process_run()
        Run = self._run_model().with_user(manager)
        data = Run.browse(run.id).read(
            [
                "state",
                "response_payload",
                "request_payload",
                "last_error",
                "started_at",
                "finished_at",
                "last_http_status",
                "last_request_id",
            ]
        )[0]
        blob = str(data)
        self.assertNotIn(SECRET_API_KEY, blob)
        self.assertNotIn(SECRET_HMAC, blob)
        self.assertEqual(data["state"], "completed")
        fv = Run.fields_view_get(view_type="form")
        arch = fv["arch"]
        self.assertNotIn('name="prompt"', arch)
        self.assertNotIn('name="input"', arch)
        root = etree.fromstring(
            arch if isinstance(arch, bytes) else arch.encode("utf-8")
        )
        for fname in (
            "state",
            "response_payload",
            "request_payload",
            "last_error",
            "last_http_status",
            "last_request_id",
            "started_at",
            "finished_at",
        ):
            self._assert_readonly_field(root, fname)
        self.env.ref(
            "tommasi_forecast_demand.action_server_tommasi_forecast_agent_run_forecast"
        )
        menu = self.env.ref("tommasi_forecast_demand.menu_tommasi_forecast_agent_run")
        self.assertEqual(
            menu.parent_id,
            self.env.ref("stock.menu_warehouse_report"),
        )

    def test_run_other_company_and_non_manager_denied(self):
        """Other-company managers and non-managers cannot search or read runs."""
        company_b = self.env["res.company"].create({"name": "Forecast Run Isolated Co"})
        manager_a = new_test_user(
            self.env,
            login="tfd_forecast_run_mgr_a",
            groups="llm.group_llm_manager",
            company_id=self.env.company.id,
            company_ids=[(6, 0, [self.env.company.id])],
        )
        user = new_test_user(
            self.env,
            login="tfd_forecast_run_user",
            groups="base.group_user",
        )
        config_a = self._model().create(self._vals())
        config_b = self._model().create(
            self._vals(
                company_id=company_b.id,
                edge_url="https://edge-run-b.example.test",
            )
        )
        run_a = self._run_model()._enqueue(config_a)
        run_b = self._run_model()._enqueue(config_b)
        Run = self._run_model().with_user(manager_a)
        found = Run.search([])
        self.assertIn(run_a, found)
        self.assertNotIn(run_b, found)
        with self.assertRaises(AccessError):
            run_b.with_user(manager_a).read(["state"])
        RunUser = self._run_model().with_user(user)
        with self.assertRaises(AccessError):
            RunUser.search([])
        with self.assertRaises(AccessError):
            run_a.with_user(user).read(["state"])
