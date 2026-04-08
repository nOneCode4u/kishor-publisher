# scripts/utils/cronjob_api.py
"""
cron-job.org REST API wrapper.

Rate limit: cron-job.org free tier ~5 requests/second.
We sleep 1.5 seconds between consecutive create_dispatch_job calls
to prevent 429 Too Many Requests errors when creating multiple jobs at once.
"""

import time, requests

_BASE                    = "https://api.cron-job.org"
_SLEEP_BETWEEN_CREATES   = 1.5   # seconds


def _headers(api_key: str) -> dict:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type":  "application/json",
    }


def create_dispatch_job(
    api_key: str, gh_pat: str, gh_repo: str, workflow_file: str,
    title: str, ist_hour: int, ist_minute: int, ist_day: int, ist_month: int,
) -> int:
    """
    Create a cron-job.org job that POSTs to GitHub workflow_dispatch
    at the given IST date and time.
    Returns integer job_id. Raises on failure.
    Sleeps 1.5s after creation to respect rate limits.
    """
    payload = {
        "job": {
            "url":           f"https://api.github.com/repos/{gh_repo}/actions/workflows/{workflow_file}/dispatches",
            "enabled":       True,
            "title":         title,
            "saveResponses": True,
            "schedule": {
                "timezone": "Asia/Kolkata",
                "hours":    [ist_hour],
                "minutes":  [ist_minute],
                "mdays":    [ist_day],
                "months":   [ist_month],
                "wdays":    [-1],
            },
            "extendedData": {
                "headers": {
                    "Authorization":        f"Bearer {gh_pat}",
                    "Accept":               "application/vnd.github+json",
                    "X-GitHub-Api-Version": "2022-11-28",
                    "Content-Type":         "application/json",
                },
                "body": '{"ref":"main"}',
            },
            "requestMethod": 1,  # POST
        }
    }
    resp = requests.put(f"{_BASE}/jobs", headers=_headers(api_key), json=payload, timeout=15)
    resp.raise_for_status()
    job_id = resp.json().get("jobId")
    if not job_id:
        raise RuntimeError(f"cron-job.org returned no jobId. Response: {resp.json()}")
    print(f"[CRONJOB] Created job #{job_id}: {title}")
    time.sleep(_SLEEP_BETWEEN_CREATES)   # respect rate limit
    return int(job_id)


def delete_job(api_key: str, job_id: int) -> bool:
    """Delete job. Returns True on success or 404 (already gone)."""
    resp = requests.delete(f"{_BASE}/jobs/{job_id}", headers=_headers(api_key), timeout=15)
    if resp.status_code == 404:
        print(f"[CRONJOB] Job #{job_id} already gone — OK")
        return True
    resp.raise_for_status()
    print(f"[CRONJOB] Deleted job #{job_id}")
    return True


def get_last_execution_status(api_key: str, job_id: int) -> dict:
    resp = requests.get(f"{_BASE}/jobs/{job_id}/history", headers=_headers(api_key), timeout=15)
    if resp.status_code == 404:
        return {}
    resp.raise_for_status()
    history = resp.json().get("history", [])
    return history[0] if history else {}
