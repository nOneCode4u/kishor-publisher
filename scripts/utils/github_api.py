# scripts/utils/github_api.py
"""GitHub REST API helpers for state file updates and workflow dispatch."""

import os, base64, requests


def _headers() -> dict:
    return {
        "Authorization":        f"Bearer {os.environ['GITHUB_TOKEN']}",
        "Accept":               "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _repo() -> str:
    return os.environ["GITHUB_REPOSITORY"]


def get_file(path: str) -> tuple:
    resp = requests.get(
        f"https://api.github.com/repos/{_repo()}/contents/{path}",
        headers=_headers(), timeout=10,
    )
    resp.raise_for_status()
    data = resp.json()
    return base64.b64decode(data["content"]).decode("utf-8"), data["sha"]


def update_file(path: str, new_content: str, commit_message: str):
    _, sha = get_file(path)
    resp   = requests.put(
        f"https://api.github.com/repos/{_repo()}/contents/{path}",
        headers=_headers(),
        json={
            "message": commit_message,
            "content": base64.b64encode(new_content.encode()).decode("ascii"),
            "sha":     sha,
        },
        timeout=15,
    )
    resp.raise_for_status()
    print(f"[GHAPI] Updated: {path}")


def trigger_workflow_dispatch(workflow_file: str, gh_pat: str, ref: str = "main") -> bool:
    """Trigger workflow_dispatch using GH_PAT (GITHUB_TOKEN cannot trigger other workflows)."""
    resp = requests.post(
        f"https://api.github.com/repos/{_repo()}/actions/workflows/{workflow_file}/dispatches",
        headers={
            "Authorization":        f"Bearer {gh_pat}",
            "Accept":               "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "Content-Type":         "application/json",
        },
        json={"ref": ref},
        timeout=15,
    )
    if resp.status_code == 204:
        print(f"[GHAPI] Dispatched: {workflow_file}")
        return True
    print(f"[GHAPI] Dispatch failed: HTTP {resp.status_code} — {resp.text[:200]}")
    return False
