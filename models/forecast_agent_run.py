"""Queued forecast agent runs processed by ir.cron, never by the UI request."""

import json
import logging
import uuid
from datetime import timedelta

from odoo import SUPERUSER_ID, _, api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

CLAIM_LIMIT = 5
STALE_GRACE_SECONDS = 60
BACKOFF_CAP_SECONDS = 300
IDEMPOTENCY_PREFIX = "odoo-tfd-"
CANCELABLE_STATES = ("queued", "running", "retry")
STATES = [
    ("queued", "Queued"),
    ("running", "Running"),
    ("retry", "Retry"),
    ("completed", "Completed"),
    ("failed", "Failed"),
]


class TommasiForecastAgentRun(models.Model):
    _name = "tommasi.forecast.agent.run"
    _description = "Forecast Agent Run"
    _order = "id desc"

    _sql_constraints = [
        (
            "idempotency_key_uniq",
            "UNIQUE(idempotency_key)",
            "The forecast agent run idempotency key must be unique.",
        ),
    ]

    name = fields.Char(compute="_compute_name", store=True)
    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    config_id = fields.Many2one(
        "tommasi.forecast.agent.config",
        string="Config",
        required=True,
        ondelete="restrict",
        index=True,
    )
    state = fields.Selection(STATES, default="queued", required=True, index=True)
    idempotency_key = fields.Char(required=True, copy=False, index=True)
    attempt_count = fields.Integer(default=0)
    max_attempts = fields.Integer(required=True)
    retry_backoff_seconds = fields.Integer(required=True)
    read_timeout = fields.Integer(required=True)
    next_attempt_at = fields.Datetime(index=True)
    started_at = fields.Datetime()
    finished_at = fields.Datetime()
    last_http_status = fields.Integer()
    last_request_id = fields.Char()
    last_error = fields.Text()
    request_payload = fields.Text()
    response_payload = fields.Text()

    @api.depends("idempotency_key")
    def _compute_name(self):
        for run in self:
            run.name = run.idempotency_key or _("Forecast Run")

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            if not vals.get("idempotency_key"):
                vals["idempotency_key"] = "%s%s" % (IDEMPOTENCY_PREFIX, uuid.uuid4())
        return super().create(vals_list)

    def write(self, vals):
        if "idempotency_key" in vals:
            new_key = vals.get("idempotency_key")
            for run in self:
                if run.idempotency_key and run.idempotency_key != new_key:
                    raise UserError(_("The idempotency key cannot be changed."))
        return super().write(vals)

    @api.model
    def action_run_forecast(self):
        """Create a queued run for the current company without calling HTTP."""
        config = self.env["tommasi.forecast.agent.config"].search(
            [
                ("company_id", "=", self.env.company.id),
                ("active", "=", True),
            ],
            limit=1,
        )
        if not config:
            raise UserError(
                _("No active forecast agent configuration for this company.")
            )
        return self._enqueue(config)

    @api.model
    def _enqueue(self, config):
        """Insert a queued run from an active config; never POST."""
        config.ensure_one()
        return self.create(
            {
                "company_id": config.company_id.id,
                "config_id": config.id,
                "state": "queued",
                "idempotency_key": "%s%s" % (IDEMPOTENCY_PREFIX, uuid.uuid4()),
                "attempt_count": 0,
                "max_attempts": config.max_attempts,
                "retry_backoff_seconds": config.retry_backoff_seconds,
                "read_timeout": config.read_timeout,
                "next_attempt_at": fields.Datetime.now(),
            }
        )

    def action_cancel(self):
        """Stop further invokes; allowed only for queued, running, or retry."""
        now = fields.Datetime.now()
        for run in self:
            if run.state not in CANCELABLE_STATES:
                raise UserError(
                    _("Only queued, running, or retry runs can be cancelled.")
                )
            run.write(
                {
                    "state": "failed",
                    "finished_at": now,
                    "last_error": _("Cancelled by user."),
                }
            )
        return True

    def action_retry(self):
        """Requeue a failed run that still has an active company config."""
        now = fields.Datetime.now()
        for run in self:
            if run.state != "failed":
                raise UserError(_("Only failed runs can be retried."))
            config = self.env["tommasi.forecast.agent.config"].search(
                [
                    ("company_id", "=", run.company_id.id),
                    ("active", "=", True),
                ],
                limit=1,
            )
            if not config:
                raise UserError(
                    _("No active forecast agent configuration for this company.")
                )
            if run.attempt_count >= config.max_attempts:
                raise UserError(_("This run has no remaining attempts."))
            run.write(
                {
                    "state": "queued",
                    "config_id": config.id,
                    "max_attempts": config.max_attempts,
                    "retry_backoff_seconds": config.retry_backoff_seconds,
                    "read_timeout": config.read_timeout,
                    "next_attempt_at": now,
                    "finished_at": False,
                    "last_error": False,
                }
            )
        return True

    def _retry_delay_seconds(self):
        """Exponential backoff capped at 300 seconds."""
        self.ensure_one()
        base = self.retry_backoff_seconds or 30
        attempt = max(self.attempt_count, 1)
        return min(BACKOFF_CAP_SECONDS, base * (2 ** (attempt - 1)))

    def _sanitize_text(self, value, config):
        hmac = self.env["tommasi.forecast.agent.hmac"]
        if value is None:
            text = ""
        elif isinstance(value, (bytes, bytearray)):
            text = value.decode("utf-8", errors="replace")
        else:
            text = value if isinstance(value, str) else str(value)
        return hmac._redact(text, config)

    @api.model
    def _recover_stale_running(self):
        """Treat running rows past read_timeout+60s as a transport failure."""
        now = fields.Datetime.now()
        running = self.sudo().search(
            [("state", "=", "running"), ("started_at", "!=", False)]
        )
        for run in running:
            grace = timedelta(seconds=(run.read_timeout or 120) + STALE_GRACE_SECONDS)
            if run.started_at + grace >= now:
                continue
            run._apply_invoke_result(
                {
                    "status_code": None,
                    "retryable": True,
                    "error": _("Stale running recovered as transport failure."),
                    "request_id": run.last_request_id,
                    "body": b"",
                    "response_text": "",
                }
            )

    @api.model
    def _claim_due_runs(self, limit=CLAIM_LIMIT):
        """Lock due queued/retry rows with SKIP LOCKED and mark them running."""
        now = fields.Datetime.now()
        self.flush()
        self.env.cr.execute(
            """
            SELECT id
              FROM tommasi_forecast_agent_run
             WHERE state IN ('queued', 'retry')
               AND (next_attempt_at IS NULL OR next_attempt_at <= %s)
             ORDER BY id
               FOR UPDATE SKIP LOCKED
             LIMIT %s
            """,
            (now, limit),
        )
        ids = [row[0] for row in self.env.cr.fetchall()]
        self.invalidate_cache()
        claimed = self.browse(ids)
        for run in claimed:
            run.write(
                {
                    "state": "running",
                    "attempt_count": run.attempt_count + 1,
                    "started_at": now,
                    "finished_at": False,
                }
            )
        return claimed

    @api.model
    def _claim_due_runs_committed(self, limit=CLAIM_LIMIT):
        """Claim on a side cursor and commit so HTTP can proceed after lock.

        TransactionCase tests must call ``_claim_due_runs`` and ``_process_run``
        on the test cursor instead of this method.
        """
        cr = self.env.registry.cursor()
        try:
            env = api.Environment(cr, SUPERUSER_ID, dict(self.env.context))
            Run = env[self._name]
            Run._recover_stale_running()
            claimed = Run._claim_due_runs(limit=limit)
            ids = list(claimed.ids)
            cr.commit()
            return ids
        except Exception:
            cr.rollback()
            raise
        finally:
            cr.close()

    @api.model
    def _cron_process_forecast_runs(self):
        """Cron entry: commit claimed rows, then process each run in memory."""
        claimed_ids = self._claim_due_runs_committed(limit=CLAIM_LIMIT)
        for run in self.browse(claimed_ids).exists():
            run._process_run()

    def _process_run(self):
        """POST via the HMAC helper and map retryable vs terminal statuses."""
        self.ensure_one()
        if self.state != "running":
            return
        config = self.config_id
        hmac = self.env["tommasi.forecast.agent.hmac"]
        try:
            result = hmac._post_invoke(config, self.idempotency_key)
        except UserError as exc:
            self._apply_invoke_result(
                {
                    "status_code": None,
                    "retryable": False,
                    "error": hmac._format_error(config, str(exc)),
                    "request_id": False,
                    "body": b"",
                    "response_text": "",
                }
            )
            return
        self._apply_invoke_result(result)

    def _apply_invoke_result(self, result):
        """Persist sanitized payloads and the next state from a helper result."""
        self.ensure_one()
        self.invalidate_cache(["state"])
        if self.state == "failed":
            return
        config = self.config_id
        now = fields.Datetime.now()
        status = result.get("status_code")
        retryable = result.get("retryable")
        request_payload = self._sanitize_text(result.get("body"), config)
        response_payload = self._sanitize_text(result.get("response_text"), config)
        error = self._sanitize_text(result.get("error"), config)
        vals = {
            "last_http_status": status or 0,
            "last_request_id": result.get("request_id") or False,
            "request_payload": request_payload,
            "response_payload": response_payload,
            "last_error": error or False,
        }
        if status == 200:
            try:
                json.loads(result.get("response_text") or "")
            except (TypeError, ValueError):
                vals.update(
                    {
                        "state": "failed",
                        "finished_at": now,
                        "last_error": _("Forecast agent returned invalid JSON."),
                    }
                )
                self.write(vals)
                return
            vals.update(
                {
                    "state": "completed",
                    "finished_at": now,
                    "last_error": False,
                }
            )
            self.write(vals)
            return
        if retryable and self.attempt_count < self.max_attempts:
            delay = self._retry_delay_seconds()
            vals.update(
                {
                    "state": "retry",
                    "next_attempt_at": now + timedelta(seconds=delay),
                    "finished_at": False,
                }
            )
            self.write(vals)
            return
        vals.update({"state": "failed", "finished_at": now})
        self.write(vals)
        _logger.warning("Forecast agent run %s ended in state %s", self.id, "failed")
