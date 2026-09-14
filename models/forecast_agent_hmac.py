"""HMAC-SHA256 client for forecast agent edge invoke."""

import hashlib
import hmac
import json
import logging
import time
import uuid

import requests

from odoo import _, api, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

INVOKE_PATH = "/v1/agent/invoke"
TRIGGER_INPUT = "Run demand forecast."
CLIENT_SOURCE = "odoo.tommasi_forecast_demand"
CLIENT_VERSION = "15.0.5.0.0"
RETRYABLE_STATUS_CODES = frozenset({202, 429, 502, 503, 504})


class TommasiForecastAgentHmac(models.AbstractModel):
    _name = "tommasi.forecast.agent.hmac"
    _description = "Forecast Agent HMAC Client"

    @api.model
    def _compact_utf8(self, payload):
        """Serialize payload to compact UTF-8 JSON bytes exactly once."""
        return json.dumps(
            payload,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")

    @api.model
    def _invoke_payload(self, idempotency_key):
        """Return the fixed-key invoke dict; never include assistant_id."""
        return {
            "input": TRIGGER_INPUT,
            "response_mode": "sync",
            "metadata": {
                "source": CLIENT_SOURCE,
                "trace_id": idempotency_key,
                "client_version": CLIENT_VERSION,
            },
        }

    @api.model
    def _body_sha256_hex(self, body):
        return hashlib.sha256(body).hexdigest()

    @api.model
    def _canonical_string(self, timestamp, nonce, body):
        return "POST\n%s\n%s\n%s\n%s" % (
            INVOKE_PATH,
            timestamp,
            nonce,
            self._body_sha256_hex(body),
        )

    @api.model
    def _sign(self, hmac_secret, timestamp, nonce, body):
        canonical = self._canonical_string(timestamp, nonce, body)
        return hmac.new(
            hmac_secret.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

    @api.model
    def _new_nonce(self):
        return uuid.uuid4().hex

    @api.model
    def _new_request_id(self):
        return str(uuid.uuid4())

    @api.model
    def _new_timestamp(self):
        return str(int(time.time()))

    @api.model
    def _invoke_url(self, edge_url):
        return (edge_url or "").rstrip("/") + INVOKE_PATH

    @api.model
    def _redact(self, text, config):
        redacted = "" if text is None else text
        if not isinstance(redacted, str):
            redacted = str(redacted)
        for secret in (config.api_key, config.hmac_secret):
            if secret:
                redacted = redacted.replace(secret, "")
        return redacted

    @api.model
    def _classify(self, status_code, transport_error=False):
        if transport_error or status_code is None:
            return True
        return status_code in RETRYABLE_STATUS_CODES

    @api.model
    def _invoke_headers(
        self,
        config,
        timestamp,
        nonce,
        signature,
        idempotency_key,
        request_id,
    ):
        return {
            "Content-Type": "application/json",
            "X-API-Key": config.api_key or "",
            "X-Timestamp": timestamp,
            "X-Nonce": nonce,
            "X-Signature": signature,
            "X-Idempotency-Key": idempotency_key,
            "X-Request-Id": request_id,
        }

    @api.model
    def _format_error(self, config, message):
        return self._redact(message, config)

    @api.model
    def _post_invoke(
        self,
        config,
        idempotency_key,
        nonce=None,
        timestamp=None,
        request_id=None,
    ):
        """Sign compact body bytes once and POST them to edge invoke."""
        config.ensure_one()
        if not config.api_key or not config.hmac_secret:
            raise UserError(_("Forecast agent credentials are not configured."))
        body = self._compact_utf8(self._invoke_payload(idempotency_key))
        timestamp = timestamp or self._new_timestamp()
        nonce = nonce or self._new_nonce()
        request_id = request_id or self._new_request_id()
        signature = self._sign(config.hmac_secret, timestamp, nonce, body)
        headers = self._invoke_headers(
            config,
            timestamp,
            nonce,
            signature,
            idempotency_key,
            request_id,
        )
        timeout = (config.connect_timeout, config.read_timeout)
        try:
            response = requests.post(
                self._invoke_url(config.edge_url),
                data=body,
                headers=headers,
                timeout=timeout,
                verify=True,
                allow_redirects=False,
            )
        except requests.RequestException as exc:
            _logger.warning("Forecast agent transport error")
            return {
                "status_code": None,
                "retryable": True,
                "error": self._format_error(
                    config,
                    _("Forecast agent request failed: %s") % exc,
                ),
                "request_id": request_id,
                "body": body,
                "response_text": "",
            }
        status_code = response.status_code
        error = ""
        response_text = response.text or ""
        if status_code != 200:
            error = self._format_error(
                config,
                _("Forecast agent returned HTTP %s.") % status_code,
            )
            _logger.warning("Forecast agent HTTP %s", status_code)
        return {
            "status_code": status_code,
            "retryable": self._classify(status_code),
            "error": error,
            "request_id": request_id,
            "body": body,
            "response_text": response_text,
        }
