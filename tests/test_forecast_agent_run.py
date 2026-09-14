"""TransactionCase tests for forecast agent run enqueue, claim, and worker."""

import json
from datetime import timedelta
from unittest.mock import MagicMock, call, patch

from odoo import SUPERUSER_ID, fields
from odoo.exceptions import UserError
from odoo.tests import tagged
from odoo.tests.common import TransactionCase

SECRET_API_KEY = "tfd-run-api-key-41c8e0aa"
SECRET_HMAC = "tfd-run-hmac-secret-90b2d11c"
POST_PATH = "odoo.addons.tommasi_forecast_demand.models.forecast_agent_hmac.requests.post"
ENVIRONMENT_PATH = (
    "odoo.addons.tommasi_forecast_demand.models.forecast_agent_run.api.Environment"
)


@tagged("post_install", "-at_install")
class TestForecastAgentRun(TransactionCase):
    """Enqueue without HTTP, claim/stale/cancel, sanitize, and patched POST."""

    def _vals(self, **overrides):
        vals = {
            "company_id": self.env.company.id,
            "edge_url": "https://edge.example.test",
            "api_key": SECRET_API_KEY,
            "hmac_secret": SECRET_HMAC,
        }
        vals.update(overrides)
        return vals

    def _config(self, **overrides):
        return self.env["tommasi.forecast.agent.config"].create(self._vals(**overrides))

    def _run_model(self):
        return self.env["tommasi.forecast.agent.run"]

    def _response(self, status_code=200, text="{}"):
        response = MagicMock()
        response.status_code = status_code
        response.headers = {}
        response.text = text
        response.content = text.encode("utf-8")
        return response

    def test_enqueue_does_not_call_http(self):
        """Run Forecast must queue a run without waiting on edge HTTP."""
        self._config()
        with patch(POST_PATH) as mock_post:
            run = self._run_model().action_run_forecast()
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(run.state, "queued")
        self.assertTrue(run.idempotency_key.startswith("odoo-tfd-"))
        self.assertEqual(run.attempt_count, 0)
        self.assertEqual(run.company_id, self.env.company)

    def test_missing_config_raises_user_error(self):
        """Missing active config must raise UserError and must not create a run."""
        Run = self._run_model()
        before = Run.search_count([])
        with patch(POST_PATH) as mock_post:
            with self.assertRaises(UserError) as ctx:
                Run.action_run_forecast()
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(Run.search_count([]), before)
        self.assertNotIn(SECRET_API_KEY, str(ctx.exception))
        self.assertNotIn(SECRET_HMAC, str(ctx.exception))

    def _wizard(self, **vals):
        return self.env["tommasi.forecast.agent.run.wizard"].create(vals)

    def test_wizard_create_does_not_enqueue(self):
        """Opening the confirmation wizard must not queue a run."""
        self._config()
        Run = self._run_model()
        before = Run.search_count([])
        self._wizard()
        self.assertEqual(Run.search_count([]), before)

    def test_wizard_confirm_enqueues_and_opens_run(self):
        """Confirming the wizard must queue a run and open its form."""
        self._config()
        Run = self._run_model()
        before = Run.search_count([])
        with patch(POST_PATH) as mock_post:
            action = self._wizard().action_confirm()
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(Run.search_count([]), before + 1)
        self.assertEqual(action["type"], "ir.actions.act_window")
        self.assertEqual(action["res_model"], "tommasi.forecast.agent.run")
        self.assertEqual(action["view_mode"], "form")
        self.assertEqual(action["target"], "current")
        run = Run.browse(action["res_id"])
        self.assertTrue(run.exists())
        self.assertEqual(run.state, "queued")
        self.assertEqual(run.company_id, self.env.company)

    def test_wizard_confirm_missing_config_raises_user_error(self):
        """Confirm without an active config must raise and must not create a run."""
        Run = self._run_model()
        before = Run.search_count([])
        with patch(POST_PATH) as mock_post:
            with self.assertRaises(UserError):
                self._wizard().action_confirm()
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(Run.search_count([]), before)

    def test_claim_queued_run(self):
        """SKIP LOCKED claim marks due queued rows running and skips the rest."""
        config = self._config()
        Run = self._run_model()
        due = [Run._enqueue(config) for _index in range(6)]
        later = Run._enqueue(config)
        later.write(
            {"next_attempt_at": fields.Datetime.now() + timedelta(minutes=10)}
        )
        claimed = Run._claim_due_runs(limit=5)
        self.assertEqual(len(claimed), 5)
        self.assertEqual(set(claimed.ids), set(run.id for run in due[:5]))
        for run in claimed:
            self.assertEqual(run.state, "running")
            self.assertEqual(run.attempt_count, 1)
            self.assertTrue(run.started_at)
        self.assertEqual(due[5].state, "queued")
        self.assertEqual(later.state, "queued")
        claimed_again = Run._claim_due_runs(limit=5)
        self.assertEqual(claimed_again, due[5])
        self.assertEqual(due[5].state, "running")

    def test_cron_processes_claimed_runs_on_committed_cursors(self):
        """Cron must not process side-cursor claims through its old snapshot."""
        Run = self._run_model()
        with patch.object(
            type(Run),
            "_claim_due_runs_committed",
            return_value=[41, 42],
        ) as mock_claim, patch.object(
            type(Run),
            "_process_run_committed",
        ) as mock_process:
            Run._cron_process_forecast_runs()

        mock_claim.assert_called_once_with(limit=5)
        self.assertEqual(mock_process.call_args_list, [call(41), call(42)])

    def test_process_run_committed_uses_fresh_cursor(self):
        """The processor must read the claimed running state after its commit."""
        Run = self._run_model()
        cr = MagicMock()
        fresh_run = MagicMock()
        fresh_model = MagicMock()
        fresh_model.browse.return_value.exists.return_value = fresh_run
        fresh_env = MagicMock()
        fresh_env.__getitem__.return_value = fresh_model

        with patch.object(
            self.env.registry,
            "cursor",
            return_value=cr,
        ) as mock_cursor, patch(
            ENVIRONMENT_PATH,
            return_value=fresh_env,
        ) as mock_environment:
            Run._process_run_committed(178)

        mock_cursor.assert_called_once_with()
        environment_args = mock_environment.call_args.args
        self.assertIs(environment_args[0], cr)
        self.assertEqual(environment_args[1], SUPERUSER_ID)
        fresh_env.__getitem__.assert_called_once_with(Run._name)
        fresh_model.browse.assert_called_once_with(178)
        fresh_run._process_run.assert_called_once_with()
        cr.commit.assert_called_once_with()
        cr.rollback.assert_not_called()
        cr.close.assert_called_once_with()

    def test_stale_running_recovered(self):
        """Running past read_timeout+60s is recovered as retry or failed."""
        config = self._config()
        Run = self._run_model()
        retry_run = Run._enqueue(config)
        failed_run = Run._enqueue(config)
        stale_start = fields.Datetime.now() - timedelta(
            seconds=retry_run.read_timeout + 61
        )
        retry_run.write(
            {
                "state": "running",
                "attempt_count": 1,
                "started_at": stale_start,
            }
        )
        failed_run.write(
            {
                "state": "running",
                "attempt_count": failed_run.max_attempts,
                "started_at": stale_start,
            }
        )
        Run._recover_stale_running()
        self.assertEqual(retry_run.state, "retry")
        self.assertTrue(retry_run.next_attempt_at)
        self.assertEqual(failed_run.state, "failed")
        self.assertTrue(failed_run.finished_at)

    def test_cancel_queued(self):
        """Cancel on queued or retry must fail the run and block further invokes."""
        config = self._config()
        Run = self._run_model()
        queued = Run._enqueue(config)
        retry_run = Run._enqueue(config)
        retry_run.write({"state": "retry"})
        queued.action_cancel()
        retry_run.action_cancel()
        self.assertEqual(queued.state, "failed")
        self.assertEqual(retry_run.state, "failed")
        with patch(POST_PATH) as mock_post:
            queued._process_run()
            retry_run._process_run()
        self.assertEqual(mock_post.call_count, 0)
        self.assertEqual(queued.state, "failed")

    def test_reject_completed_retry_and_cancel(self):
        """Completed runs must not be retried or cancelled."""
        run = self._run_model()._enqueue(self._config())
        run.write({"state": "completed"})
        with self.assertRaises(UserError):
            run.action_cancel()
        with self.assertRaises(UserError):
            run.action_retry()
        self.assertEqual(run.state, "completed")

    def test_sanitize_payloads(self):
        """Stored request and response payloads must omit config secrets."""
        run = self._run_model()._enqueue(self._config())
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
        with patch(POST_PATH, return_value=self._response(status_code=200, text=leaky)):
            run._process_run()
        self.assertEqual(run.state, "completed")
        stored = "%s %s %s" % (
            run.request_payload or "",
            run.response_payload or "",
            run.last_error or "",
        )
        self.assertNotIn(SECRET_API_KEY, stored)
        self.assertNotIn(SECRET_HMAC, stored)

    def test_process_run_patched_post(self):
        """_process_run maps 200/503/401 from a patched HMAC POST."""
        config = self._config()
        Run = self._run_model()

        completed = Run._enqueue(config)
        completed.write(
            {
                "state": "running",
                "attempt_count": 1,
                "started_at": fields.Datetime.now(),
            }
        )
        with patch(
            POST_PATH, return_value=self._response(status_code=200, text='{"ok":true}')
        ) as mock_post:
            completed._process_run()
        self.assertEqual(mock_post.call_count, 1)
        self.assertEqual(completed.state, "completed")
        self.assertEqual(completed.last_http_status, 200)

        retry_run = Run._enqueue(config)
        retry_run.write(
            {
                "state": "running",
                "attempt_count": 1,
                "started_at": fields.Datetime.now(),
            }
        )
        with patch(POST_PATH, return_value=self._response(status_code=503)):
            retry_run._process_run()
        self.assertEqual(retry_run.state, "retry")
        self.assertEqual(retry_run.last_http_status, 503)
        self.assertTrue(retry_run.next_attempt_at)

        failed = Run._enqueue(config)
        failed.write(
            {
                "state": "running",
                "attempt_count": 1,
                "started_at": fields.Datetime.now(),
            }
        )
        with patch(POST_PATH, return_value=self._response(status_code=401)):
            failed._process_run()
        self.assertEqual(failed.state, "failed")
        self.assertEqual(failed.last_http_status, 401)
        self.assertNotIn(SECRET_API_KEY, failed.last_error or "")
        self.assertNotIn(SECRET_HMAC, failed.last_error or "")
