import unittest
from unittest.mock import patch, MagicMock
import requests
from scripts.utils.http_client import robust_request, DEFAULT_HEADERS


class TestHttpClient(unittest.TestCase):
    @patch("scripts.utils.http_client.requests.request")
    def test_robust_request_success_first_try(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_request.return_value = mock_resp

        resp = robust_request("GET", "https://example.com/test.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_request.call_count, 1)
        _, kwargs = mock_request.call_args
        self.assertTrue(kwargs.get("verify"))

    @patch("scripts.utils.http_client.requests.request")
    def test_robust_request_ssl_fallback(self, mock_request):
        mock_resp = MagicMock()
        mock_resp.status_code = 200

        # First call raises SSLError, second succeeds with verify=False
        mock_request.side_effect = [
            requests.exceptions.SSLError("certificate verify failed: unable to get local issuer certificate"),
            mock_resp,
        ]

        resp = robust_request("GET", "https://kishor.ebalbharati.in/Archives/include/pdf/2026_06.pdf")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(mock_request.call_count, 2)
        _, kwargs2 = mock_request.call_args
        self.assertFalse(kwargs2.get("verify"))


if __name__ == "__main__":
    unittest.main()
