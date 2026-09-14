"""TransactionCase tests for the forecast agent HMAC invoke client."""

import hashlib
import hmac
import json
from unittest.mock import MagicMock, patch

import requests

from odoo.tests import tagged
from odoo.tests.common import TransactionCase

SECRET_API_KEY = "tfd-hmac-api-key-e2a91c04"
SECRET_HMAC = "tfd-hmac-secret-d8b17f33"
POST_PATH = "odoo.addons.tommasi_forecast_demand.models.forecast_agent_hmac.requests.post"
REDIRECT_LOCATION = "https://evil.example.test/catch"
IDEMPOTENCY_KEY = "odoo-tfd-00000000-0000-4000-8000-000000000001"


@tagged("post_install", "-at_install")
class TestForecastAgentHmac(TransactionCase):
    """Threat-matrix HTTPS POST flags and HMAC invoke contract."""

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

    def _hmac(self):
        return self.env["tommasi.forecast.agent.hmac"]

    def _response(self, status_code=200, headers=None, text="{}"):
        response = MagicMock()
        response.status_code = status_code
        response.headers = headers or {}
        response.text = text
        response.content = text.encode("utf-8")
        return response

    def test_post_verify_true_and_301_not_followed(self):
        """requests.post must pin TLS and refuse to follow a mock 301."""
        config = self._config()
        hmac_client = self._hmac()
        redirect = self._response(
            status_code=301,
            headers={"Location": REDIRECT_LOCATION},
            text="moved",
        )
        with patch(POST_PATH, return_value=redirect) as mock_post:
            result = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        self.assertEqual(mock_post.call_count, 1)
        kwargs = mock_post.call_args.kwargs
        self.assertTrue(kwargs["verify"])
        self.assertFalse(kwargs["allow_redirects"])
        self.assertEqual(
            kwargs["timeout"],
            (config.connect_timeout, config.read_timeout),
        )
        posted_url = mock_post.call_args.args[0]
        self.assertEqual(posted_url, "https://edge.example.test/v1/agent/invoke")
        self.assertNotEqual(posted_url, REDIRECT_LOCATION)
        self.assertFalse(result["retryable"])
        self.assertEqual(result["status_code"], 301)
        self.assertNotIn(SECRET_API_KEY, result.get("error") or "")
        self.assertNotIn(SECRET_HMAC, result.get("error") or "")

    def test_signed_bytes_match_posted_body(self):
        """HMAC must sign the same compact UTF-8 bytes that are posted."""
        config = self._config()
        hmac_client = self._hmac()
        timestamp = "1700000000"
        nonce = "a" * 32
        request_id = "11111111-1111-4111-8111-111111111111"
        with patch(POST_PATH, return_value=self._response()) as mock_post:
            result = hmac_client._post_invoke(
                config,
                IDEMPOTENCY_KEY,
                nonce=nonce,
                timestamp=timestamp,
                request_id=request_id,
            )
        posted_body = mock_post.call_args.kwargs["data"]
        self.assertEqual(posted_body, result["body"])
        self.assertIsNone(mock_post.call_args.kwargs.get("json"))
        expected_hash = hashlib.sha256(posted_body).hexdigest()
        canonical = "POST\n/v1/agent/invoke\n%s\n%s\n%s" % (
            timestamp,
            nonce,
            expected_hash,
        )
        expected_sig = hmac.new(
            SECRET_HMAC.encode("utf-8"),
            canonical.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        headers = mock_post.call_args.kwargs["headers"]
        self.assertEqual(headers["X-Signature"], expected_sig)
        self.assertEqual(headers["X-API-Key"], SECRET_API_KEY)
        self.assertEqual(headers["X-Timestamp"], timestamp)
        self.assertEqual(headers["X-Nonce"], nonce)
        self.assertEqual(headers["X-Idempotency-Key"], IDEMPOTENCY_KEY)
        self.assertEqual(headers["X-Request-Id"], request_id)
        self.assertEqual(headers["Content-Type"], "application/json")

    def test_retry_reuses_idempotency_not_nonce(self):
        """A second attempt must reuse the idempotency key and mint a new nonce."""
        config = self._config()
        hmac_client = self._hmac()
        time_path = (
            "odoo.addons.tommasi_forecast_demand.models.forecast_agent_hmac.time.time"
        )
        with patch(time_path, side_effect=[1700000000.1, 1700000001.2]):
            with patch(POST_PATH, return_value=self._response()) as mock_post:
                hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
                hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        self.assertEqual(mock_post.call_count, 2)
        headers_1 = mock_post.call_args_list[0].kwargs["headers"]
        headers_2 = mock_post.call_args_list[1].kwargs["headers"]
        self.assertEqual(headers_1["X-Idempotency-Key"], IDEMPOTENCY_KEY)
        self.assertEqual(headers_2["X-Idempotency-Key"], IDEMPOTENCY_KEY)
        self.assertNotEqual(headers_1["X-Nonce"], headers_2["X-Nonce"])
        self.assertNotEqual(headers_1["X-Signature"], headers_2["X-Signature"])
        self.assertNotEqual(headers_1["X-Request-Id"], headers_2["X-Request-Id"])
        self.assertNotEqual(headers_1["X-Timestamp"], headers_2["X-Timestamp"])
        self.assertEqual(headers_1["X-Timestamp"], "1700000000")
        self.assertEqual(headers_2["X-Timestamp"], "1700000001")
        self.assertLessEqual(len(headers_1["X-Nonce"]), 128)
        self.assertLessEqual(len(headers_2["X-Nonce"]), 128)

    def test_fixed_trigger_body_omits_assistant_id(self):
        """Invoke JSON is the fixed trigger body without assistant_id or session_id."""
        config = self._config(assistant_id="asst_must_not_be_sent")
        hmac_client = self._hmac()
        with patch(POST_PATH, return_value=self._response()) as mock_post:
            result = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        expected = (
            '{"input":"Run demand forecast.","response_mode":"sync",'
            '"metadata":{"source":"odoo.tommasi_forecast_demand",'
            '"trace_id":"%s","client_version":"15.0.5.0.0"}}' % IDEMPOTENCY_KEY
        ).encode("utf-8")
        self.assertEqual(result["body"], expected)
        self.assertEqual(mock_post.call_args.kwargs["data"], expected)
        payload = json.loads(result["body"].decode("utf-8"))
        self.assertEqual(payload["input"], "Run demand forecast.")
        self.assertEqual(payload["response_mode"], "sync")
        self.assertEqual(
            set(payload["metadata"]),
            {"source", "trace_id", "client_version"},
        )
        self.assertNotIn("assistant_id", payload)
        self.assertNotIn("session_id", payload)
        self.assertNotIn("attachments", payload)
        self.assertNotIn("command", payload)
        self.assertNotIn("timeout", payload)

    def test_503_retryable_versus_401_terminal(self):
        """HTTP 503 is retryable; HTTP 401 is terminal."""
        config = self._config()
        hmac_client = self._hmac()
        with patch(POST_PATH, return_value=self._response(status_code=503)):
            retryable = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        with patch(POST_PATH, return_value=self._response(status_code=401)):
            terminal = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        self.assertEqual(retryable["status_code"], 503)
        self.assertTrue(retryable["retryable"])
        self.assertEqual(terminal["status_code"], 401)
        self.assertFalse(terminal["retryable"])
        self.assertTrue(hmac_client._classify(None, transport_error=True))

    def test_errors_omit_secrets(self):
        """Transport and HTTP errors must not echo api_key or hmac_secret."""
        config = self._config()
        hmac_client = self._hmac()
        leak = "boom %s %s" % (SECRET_API_KEY, SECRET_HMAC)
        with patch(POST_PATH, side_effect=requests.RequestException(leak)):
            transport = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        with patch(POST_PATH, return_value=self._response(status_code=401)):
            denied = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        for result in (transport, denied):
            message = result.get("error") or ""
            self.assertNotIn(SECRET_API_KEY, message)
            self.assertNotIn(SECRET_HMAC, message)
            self.assertNotIn(SECRET_API_KEY, str(result))
            self.assertNotIn(SECRET_HMAC, str(result))
        self.assertTrue(transport["retryable"])
        self.assertIsNone(transport["status_code"])
        self.assertFalse(denied["retryable"])

    def test_retryable_failure_logs_omit_secrets(self):
        """Retryable transport and HTTP 503 logs must not contain secrets."""
        config = self._config()
        hmac_client = self._hmac()
        logger_name = (
            "odoo.addons.tommasi_forecast_demand.models.forecast_agent_hmac"
        )
        leak = "timeout %s %s" % (SECRET_API_KEY, SECRET_HMAC)
        with patch(POST_PATH, side_effect=requests.RequestException(leak)):
            with self.assertLogs(logger_name, level="WARNING") as captured:
                transport = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        self.assertTrue(transport["retryable"])
        transport_logs = "\n".join(captured.output)
        self.assertTrue(captured.output)
        self.assertNotIn(SECRET_API_KEY, transport_logs)
        self.assertNotIn(SECRET_HMAC, transport_logs)
        leaky_body = "upstream %s %s" % (SECRET_API_KEY, SECRET_HMAC)
        with patch(
            POST_PATH,
            return_value=self._response(status_code=503, text=leaky_body),
        ):
            with self.assertLogs(logger_name, level="WARNING") as captured:
                retryable = hmac_client._post_invoke(config, IDEMPOTENCY_KEY)
        self.assertEqual(retryable["status_code"], 503)
        self.assertTrue(retryable["retryable"])
        http_logs = "\n".join(captured.output)
        self.assertTrue(captured.output)
        self.assertNotIn(SECRET_API_KEY, http_logs)
        self.assertNotIn(SECRET_HMAC, http_logs)
        self.assertNotIn(SECRET_API_KEY, retryable.get("error") or "")
        self.assertNotIn(SECRET_HMAC, retryable.get("error") or "")
