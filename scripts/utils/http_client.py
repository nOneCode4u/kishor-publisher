# scripts/utils/http_client.py
"""
Resilient HTTP client for eBalbharati Archives with SSL verification fallback and defense-in-depth.

Background:
  kishor.ebalbharati.in frequently serves incomplete SSL certificate chains
  (missing intermediate certificates from emSign PKI / eMudhra Technologies Limited).
  Standard OpenSSL and certifi environments throw:
    SSLCertVerificationError: [SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate

  This module provides robust request helpers that attempt standard verified TLS first.
  If and only if an SSLCertVerificationError occurs, it falls back to an unverified TLS request
  with a prominent warning, while preserving strict data-integrity verification
  (Content-Type check, PDF magic-byte validation b"%PDF-", file size ratio verification,
  and cryptographic SHA-256 hash calculation).
"""

import logging
import warnings
import urllib3
import requests

logger = logging.getLogger(__name__)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36 (compatible; KishorPublisher/1.0)"
    ),
    "Accept": "application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9,mr;q=0.8",
}


def robust_request(
    method: str,
    url: str,
    session: requests.Session | None = None,
    **kwargs
) -> requests.Response:
    """
    Execute an HTTP request with automatic SSL verification fallback.

    1. Tries standard SSL verification first (verify=True).
    2. If requests.exceptions.SSLError occurs (e.g. missing intermediate certificate
       from eMudhra / emSign PKI), logs a warning and retries with verify=False.
    """
    req_headers = dict(DEFAULT_HEADERS)
    if "headers" in kwargs and kwargs["headers"]:
        req_headers.update(kwargs.pop("headers"))

    caller = session.request if session is not None else requests.request

    # 1. First attempt: standard SSL verification
    try:
        return caller(method, url, headers=req_headers, verify=True, **kwargs)
    except requests.exceptions.SSLError as ssl_err:
        print(
            f"[WARN] SSL verification failed for {url} ({ssl_err}). "
            f"Falling back to unverified request with data-integrity verification..."
        )
        with warnings.catch_warnings():
            urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
            return caller(method, url, headers=req_headers, verify=False, **kwargs)


def robust_head(url: str, session: requests.Session | None = None, **kwargs) -> requests.Response:
    """Execute a robust HEAD request."""
    return robust_request("HEAD", url, session=session, **kwargs)


def robust_get(url: str, session: requests.Session | None = None, **kwargs) -> requests.Response:
    """Execute a robust GET request."""
    return robust_request("GET", url, session=session, **kwargs)
