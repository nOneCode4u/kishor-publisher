#!/usr/bin/env python3
# scripts/checker.py
"""
Kishor Publisher — Checker
Runs once daily at 07:00 IST (01:30 UTC) via GitHub Actions cron.

Flow:
    1. If paused → exit silently (~5 seconds, workflow listed but does nothing).
    2. Read effective last file (queue or last_uploaded).
    3. Scan website for ALL new issues. Stop after 3 consecutive misses.
    4. Nothing new → exit silently.
    5. New issues found:
         a. Build queue items with IST schedule (00:00 IST dd+1, +1h each).
         b. Commit queue to repo.
         c. Send detection notification to owner FIRST.
         d. Create cron-job.org dispatch jobs (1.5s gap between each to avoid 429).
         e. Commit updated job IDs back to queue.
    6. Hard error → pause + notify + exit 1.
"""

import sys, os, datetime, traceback, requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.naming   import build_friendly_filename, parse_orig_filename
from scripts.utils.state    import (
    read_last_uploaded, read_queue, read_status, write_status, write_queue,
    get_effective_last, utc_now, to_ist, format_date_ist, format_hhmm_ist,
    midnight_ist_next_day, git_pull, git_commit_and_push,
    QUEUE_FILE, STATUS_FILE,
)
from scripts.utils.notifications import (
    send_to_owner, msg_new_files_detected,
    msg_error_detection_failed, msg_error_cronjob_creation,
)

BASE_URL               = "https://kishor.ebalbharati.in/Archives/include/pdf/"
HEADERS                = {"User-Agent": "Mozilla/5.0 (compatible; KishorPublisher/1.0)"}
MAX_CONSECUTIVE_MISSES = 3
MAX_FUTURE_MONTHS      = 24


def probe_pdf(fname: str) -> tuple:
    url = BASE_URL + fname
    try:
        resp = requests.head(url, headers=HEADERS, timeout=12, allow_redirects=True)
        if resp.status_code != 200:
            print(f"[CHECK] {fname} → HTTP {resp.status_code}")
            return False, 0.0
        ctype = resp.headers.get("content-type", "").lower()
        if not any(t in ctype for t in ("pdf", "octet-stream", "application")):
            print(f"[CHECK] {fname} → unexpected Content-Type: {ctype!r}")
            return False, 0.0
        size_mb = round(int(resp.headers.get("content-length", 0)) / (1024 * 1024), 2)
        print(f"[CHECK] {fname} → ✓ {size_mb:.2f} MB")
        return True, size_mb
    except requests.RequestException as e:
        print(f"[CHECK] {fname} → error: {e}")
        return False, 0.0


def next_ym(year, mon):
    mon += 1
    if mon > 12:
        mon, year = 1, year + 1
    return year, mon


def scan_new_issues(effective_last: str) -> list:
    last_year, last_mon = parse_orig_filename(effective_last)
    now    = utc_now()
    found  = []
    misses = 0
    year, mon = next_ym(last_year, last_mon)
    while True:
        months_ahead = (year - now.year) * 12 + (mon - now.month)
        if months_ahead > MAX_FUTURE_MONTHS:
            print("[CHECK] Future limit reached. Stopping.")
            break
        fname = f"{year:04d}_{mon:02d}.pdf"
        exists, size_mb = probe_pdf(fname)
        if exists:
            found.append((fname, size_mb))
            misses = 0
        else:
            misses += 1
            if misses >= MAX_CONSECUTIVE_MISSES:
                print(f"[CHECK] {MAX_CONSECUTIVE_MISSES} consecutive misses. Done.")
                break
        year, mon = next_ym(year, mon)
    return found


def build_queue_items(new_issues: list, detection_utc: datetime.datetime):
    base_utc    = midnight_ist_next_day(detection_utc)
    queue_items = []
    notif_items = []
    for idx, (fname, size_mb) in enumerate(new_issues):
        sched_utc   = base_utc + datetime.timedelta(hours=idx)
        friendly    = build_friendly_filename(fname)
        ist_display = f"{format_hhmm_ist(sched_utc)} IST"
        queue_items.append({
            "index":                 idx,
            "filename_orig":         fname,
            "filename_friendly":     friendly,
            "url":                   BASE_URL + fname,
            "size_mb":               size_mb,
            "scheduled_at_utc":      sched_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "scheduled_ist_display": ist_display,
            "cronjob_job_id":        None,
            "status":                "pending",
            "uploaded_at_utc":       None,
        })
        notif_items.append({
            "filename_orig":     fname,
            "filename_friendly": friendly,
            "size_mb":           size_mb,
            "scheduled_at_utc":  sched_utc,
        })
    tomorrow_ist = format_date_ist(base_utc)
    return queue_items, notif_items, tomorrow_ist


def create_cronjob_jobs(queue_items: list):
    """Create cron-job.org dispatch jobs. Updates queue_items in place. 1.5s gap between calls."""
    api_key = os.environ.get("CRON_JOB_ORG_API_KEY", "").strip()
    gh_pat  = os.environ.get("GH_PAT", "").strip()
    gh_repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not (api_key and gh_pat and gh_repo):
        print("[WARN] CRON_JOB_ORG_API_KEY or GH_PAT not set — skipping job creation.")
        return
    from scripts.utils.cronjob_api import create_dispatch_job
    for item in queue_items:
        sched_ist = to_ist(
            datetime.datetime.strptime(item["scheduled_at_utc"], "%Y-%m-%dT%H:%M:%SZ")
            .replace(tzinfo=datetime.timezone.utc)
        )
        try:
            job_id = create_dispatch_job(
                api_key=api_key, gh_pat=gh_pat, gh_repo=gh_repo,
                workflow_file="uploader.yml",
                title=f"Kishor Upload — {item['filename_orig']}",
                ist_hour=sched_ist.hour, ist_minute=sched_ist.minute,
                ist_day=sched_ist.day,   ist_month=sched_ist.month,
            )
            item["cronjob_job_id"] = job_id
            print(f"[QUEUE] {item['filename_orig']} → {item['scheduled_ist_display']} (job #{job_id})")
        except Exception as e:
            print(f"[WARN] cron-job.org failed for {item['filename_orig']}: {e}")
            try:
                send_to_owner(msg_error_cronjob_creation(item["filename_orig"], str(e)))
            except Exception:
                pass


def main():
    run_start = utc_now()
    print(f"[INFO] Checker at {run_start.strftime('%Y-%m-%d %H:%M:%S')} UTC"
          f" ({format_hhmm_ist(run_start)} IST)")

    # Paused → exit silently (workflow still "runs" for ~5s, that is normal)
    if read_status() != "active":
        print("[INFO] Paused. Exiting.")
        return

    try:
        last_uploaded  = read_last_uploaded()
        queue          = read_queue()
        effective_last = get_effective_last(last_uploaded, queue)
        print(f"[INFO] Effective last: {effective_last}")

        new_issues = scan_new_issues(effective_last)
        run_end    = utc_now()

        if not new_issues:
            print("[INFO] Nothing new. Exiting silently.")
            return

        print(f"[INFO] Found {len(new_issues)} new issue(s).")

        # Step 1: Build queue items
        queue_items, notif_items, tomorrow_ist = build_queue_items(new_issues, run_start)
        batch_id   = run_start.strftime("%Y%m%d_%H%M")
        queue_dict = {
            "batch_id":             batch_id,
            "total":                len(queue_items),
            "detected_at_utc":      run_start.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "batch_started_at_utc": None,
            "items":                queue_items,
        }

        # Step 2: Commit queue first
        git_pull()
        write_queue(queue_dict)
        git_commit_and_push(
            f"[checker] Queue {len(new_issues)} issue(s) — batch {batch_id}",
            files=[QUEUE_FILE],
        )

        # Step 3: Notify owner FIRST (before creating cron jobs)
        send_to_owner(msg_new_files_detected(
            run_start, run_end, last_uploaded, notif_items, tomorrow_ist
        ))
        print("[INFO] Detection notification sent.")

        # Step 4: Create cron-job.org dispatch jobs (1.5s gap, non-fatal on failure)
        create_cronjob_jobs(queue_items)

        # Step 5: Commit updated job IDs if any were created
        if any(i.get("cronjob_job_id") for i in queue_items):
            git_pull()
            write_queue(queue_dict)
            git_commit_and_push(
                f"[checker] Save cron-job.org IDs — batch {batch_id}",
                files=[QUEUE_FILE],
            )

    except Exception:
        tb  = traceback.format_exc()
        exc = str(sys.exc_info()[1])
        print(f"[ERROR]\n{tb}")
        try:
            git_pull()
            write_status("paused", "# Auto-paused: detection error. Send /resume to restart.")
            git_commit_and_push("❌ Auto-paused: detection error", files=[STATUS_FILE])
        except Exception as e2:
            print(f"[ERROR] Failed to commit pause: {e2}")
        try:
            send_to_owner(msg_error_detection_failed(exc, tb))
        except Exception as e3:
            print(f"[ERROR] Failed to send notification: {e3}")
        sys.exit(1)


if __name__ == "__main__":
    main()
