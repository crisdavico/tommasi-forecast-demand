"""Per-company HMAC client settings for the forecast agent edge."""

import os
from urllib.parse import urlparse

from odoo import _, api, fields, models
from odoo.exceptions import ValidationError
from odoo.tools import config

SECRET_FIELDS = ("api_key", "hmac_secret")
CONNECT_TIMEOUT_MIN = 1
CONNECT_TIMEOUT_MAX = 30
READ_TIMEOUT_MIN = 5
READ_TIMEOUT_MAX = 900
MAX_ATTEMPTS_MIN = 1
MAX_ATTEMPTS_MAX = 10
RETRY_BACKOFF_MIN = 5
RETRY_BACKOFF_MAX = 300
DOODBA_HTTP_ENVIRONMENTS = ("devel", "test")


class TommasiForecastAgentConfig(models.Model):
    _name = "tommasi.forecast.agent.config"
    _description = "Forecast Agent Config"
    _rec_name = "company_id"

    _sql_constraints = [
        (
            "company_id_uniq",
            "UNIQUE(company_id)",
            "A forecast agent configuration already exists for this company.",
        ),
    ]

    company_id = fields.Many2one(
        "res.company",
        string="Company",
        required=True,
        index=True,
        default=lambda self: self.env.company,
        ondelete="cascade",
    )
    active = fields.Boolean(default=True)
    edge_url = fields.Char(string="Edge URL", required=True)
    assistant_id = fields.Char(string="Assistant ID")
    api_key = fields.Char(string="API Key", copy=False)
    hmac_secret = fields.Char(string="HMAC Secret", copy=False)
    connect_timeout = fields.Integer(default=5)
    read_timeout = fields.Integer(default=120)
    max_attempts = fields.Integer(default=5)
    retry_backoff_seconds = fields.Integer(default=30)

    @api.model
    def _https_required(self):
        """Return True when the stored edge URL must use HTTPS."""
        if config.get("test_enable"):
            return False
        doodba_env = os.environ.get("DOODBA_ENVIRONMENT", "")
        if doodba_env in DOODBA_HTTP_ENVIRONMENTS:
            return False
        return True

    def _raise_duplicate_company(self):
        raise ValidationError(
            _("A forecast agent configuration already exists for this company.")
        )

    def _assert_companies_available(self, company_ids, exclude_ids=None):
        company_ids = [cid for cid in company_ids if cid]
        if not company_ids:
            return
        if len(company_ids) != len(set(company_ids)):
            self._raise_duplicate_company()
        domain = [("company_id", "in", company_ids)]
        if exclude_ids:
            domain.append(("id", "not in", exclude_ids))
        if self.search(domain, limit=1):
            self._raise_duplicate_company()

    @api.model_create_multi
    def create(self, vals_list):
        company_ids = [
            vals.get("company_id") or self.env.company.id for vals in vals_list
        ]
        self._assert_companies_available(company_ids)
        return super().create(vals_list)

    def write(self, vals):
        if "company_id" in vals:
            self._assert_companies_available(
                [vals.get("company_id")],
                exclude_ids=self.ids,
            )
        return super().write(vals)

    @api.constrains("company_id")
    def _check_company_id_unique(self):
        for rec in self:
            if not rec.company_id:
                continue
            duplicate = self.search(
                [
                    ("company_id", "=", rec.company_id.id),
                    ("id", "!=", rec.id),
                ],
                limit=1,
            )
            if duplicate:
                self._raise_duplicate_company()

    @api.constrains("edge_url")
    def _check_edge_url(self):
        for rec in self:
            parsed = urlparse(rec.edge_url or "")
            if parsed.username or parsed.password:
                raise ValidationError(
                    _("The edge URL must not include user credentials.")
                )
            if parsed.scheme not in ("http", "https") or not parsed.netloc:
                raise ValidationError(
                    _("The edge URL must be an HTTP or HTTPS address.")
                )
            if rec._https_required() and parsed.scheme != "https":
                raise ValidationError(_("The edge URL must use HTTPS."))

    @api.constrains(
        "connect_timeout",
        "read_timeout",
        "max_attempts",
        "retry_backoff_seconds",
    )
    def _check_timeout_bounds(self):
        for rec in self:
            if not CONNECT_TIMEOUT_MIN <= rec.connect_timeout <= CONNECT_TIMEOUT_MAX:
                raise ValidationError(
                    _("Connect timeout must be between %s and %s seconds.")
                    % (CONNECT_TIMEOUT_MIN, CONNECT_TIMEOUT_MAX)
                )
            if not READ_TIMEOUT_MIN <= rec.read_timeout <= READ_TIMEOUT_MAX:
                raise ValidationError(
                    _("Read timeout must be between %s and %s seconds.")
                    % (READ_TIMEOUT_MIN, READ_TIMEOUT_MAX)
                )
            if not MAX_ATTEMPTS_MIN <= rec.max_attempts <= MAX_ATTEMPTS_MAX:
                raise ValidationError(
                    _("Max attempts must be between %s and %s.")
                    % (MAX_ATTEMPTS_MIN, MAX_ATTEMPTS_MAX)
                )
            if not RETRY_BACKOFF_MIN <= rec.retry_backoff_seconds <= RETRY_BACKOFF_MAX:
                raise ValidationError(
                    _("Retry backoff must be between %s and %s seconds.")
                    % (RETRY_BACKOFF_MIN, RETRY_BACKOFF_MAX)
                )

    def export_data(self, fields_to_export):
        result = super().export_data(fields_to_export)
        secret_indexes = [
            index
            for index, name in enumerate(fields_to_export)
            if name in SECRET_FIELDS
        ]
        if not secret_indexes:
            return result
        for row in result.get("datas") or []:
            for index in secret_indexes:
                if index < len(row):
                    row[index] = ""
        return result
