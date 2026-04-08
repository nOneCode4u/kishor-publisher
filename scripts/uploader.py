#!/usr/bin/env python3
# scripts/uploader.py
"""
Kishor Publisher — Uploader
Triggered ONLY by cron-job.org dispatch jobs created by checker.py.
One file per run. Zero runs when queue is empty.

Flow:
    1. If paused → exit silently.
    2. Find first pending item with scheduled_at_utc ≤ now.
    3. Nothing due → exit silently.
    4. >50 MB → send info notice (Pyrogram handles up to 2 GB).
    5. Download PDF with retry + SHA-256 check.
    6. Generate thumbnail (quality=100, Lanczos, no blur).
    7. Upload via Pyrogram → channel only (owner receives text notification).
    8. Delete cron-job.org dispatch job (cleanup).
    9. Update queue + last_uploaded + history → commit.
   10. Send success notification.
   Error → pause + notify + exit 1.
"""

import sys, os, hashlib, datetime, traceback, tempfile, time, requests

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.naming          import build_friendly_filename
from scripts.utils.state           import (
    read_status, read_queue, write_queue, write_status,
    write_last_uploaded, append_history,
    utc_now, format_date_ist, format_time_ist, format_duration,
    parse_utc, git_pull, git_commit_and_push,
    QUEUE_FILE, STATUS_FILE, LAST_UPLOADED_FILE, HISTORY_FILE,
)
from scripts.utils.thumbnail       import generate_thumbnail
from scripts.utils.telegram_client import upload_document
from scripts.utils.notifications   import (
    send_to_owner, msg_upload_success, msg_large_file_notice,
    msg_error_upload_failed, msg_error_download_failed,
    msg_error_verify_failed, msg_error_generic,
)

BASE_URL      = "https://kishor.ebalbharati.in/Archives/include/pdf/"
DL_HEADERS    = {"User-Agent": "Mozilla/5.0 (compatible; KishorPublisher/1.0)"}
MAX_RETRIES   = 3
RETRY_DELAY_S = 8
LARGE_FILE_MB = 50.0


def get_due_item(queue: dict) -> dict | None:
    now = utc_now()
    for item in queue.get("items", []):
        if item.get("status") != "pending":
            continue
        sched = item.get("scheduled_at_utc", "")
        if sched and parse_utc(sched) <= now:
            return item
    return None


def download_pdf(url: str, dest: str) -> str:
    for attempt in range(1, MAX_RETRIES + 1):
        print(f"[DOWNLOAD] Attempt {attempt}/{MAX_RETRIES}: {url}")
        try:
            resp = requests.get(url, headers=DL_HEADERS, timeout=180, stream=True)
            resp.raise_for_status()
            sha256 = hashlib.sha256()
            with open(dest, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    f.write(chunk)
                    sha256.update(chunk)
            digest  = sha256.hexdigest()
            size_kb = os.path.getsize(dest) / 1024
            print(f"[DOWNLOAD] OK: {size_kb:.1f} KB  SHA256: {digest[:16]}…")
            return digest
        except Exception as e:
            print(f"[DOWNLOAD] Attempt {attempt} failed: {e}")
            if attempt < MAX_RETRIES:
                time.sleep(RETRY_DELAY_S * attempt)
    raise RuntimeError(f"Download failed after {MAX_RETRIES} attempts: {url}")


def verify_download(path: str, expected_mb: float) -> None:
    if not os.path.isfile(path):
        raise RuntimeError(f"File missing: {path}")
    actual_mb = os.path.getsize(path) / (1024 * 1024)
    if actual_mb < 0.05:
        raise RuntimeError(f"File too small: {actual_mb:.2f} MB")
    if expected_mb > 0:
        ratio = actual_mb / expected_mb
        if not (0.90 <= ratio <= 1.10):
            raise RuntimeError(
                f"Size mismatch: expected ~{expected_mb:.2f} MB, got {actual_mb:.2f} MB"
            )
    with open(path, "rb") as f:
        magic = f.read(5)
    if magic != b"%PDF-":
        raise RuntimeError(f"Not a valid PDF (magic: {magic!r})")
    print(f"[VERIFY-DL] ✓ {actual_mb:.2f} MB, valid PDF")


def delete_cronjob(job_id):
    api_key = os.environ.get("CRON_JOB_ORG_API_KEY", "").strip()
    if not api_key or not job_id:
        return
    try:
        from scripts.utils.cronjob_api import delete_job
        delete_job(api_key, int(job_id))
    except Exception as e:
        print(f"[WARN] cron-job.org deletion failed for job #{job_id}: {e}")


def main():
    run_start  = utc_now()
    channel_id = os.environ["TELEGRAM_CHANNEL_ID"]
    print(f"[INFO] Uploader at {run_start.strftime('%Y-%m-%d %H:%M:%S')} UTC"
          f" ({format_time_ist(run_start)} IST)")

    if read_status() != "active":
        print("[INFO] Paused. Exiting."); return

    queue = read_queue()
    item  = get_due_item(queue)
    if item is None:
        print("[INFO] Nothing due. Exiting."); return

    print(f"[INFO] Due: {item['filename_orig']} ({item.get('scheduled_ist_display', '?')})")

    all_items = queue.get("items", [])
    total     = queue.get("total", len(all_items))
    uploaded  = sum(1 for i in all_items if i.get("status") == "uploaded")
    index     = uploaded + 1

    if index == 1 and not queue.get("batch_started_at_utc"):
        queue["batch_started_at_utc"] = run_start.strftime("%Y-%m-%dT%H:%M:%SZ")

    try:
        if item["size_mb"] > LARGE_FILE_MB:
            try: send_to_owner(msg_large_file_notice(item))
            except Exception: pass

        with tempfile.TemporaryDirectory() as tmp:
            pdf_path   = os.path.join(tmp, item["filename_orig"])
            thumb_path = os.path.join(tmp, "thumbnail.jpg")

            try:
                sha256 = download_pdf(item["url"], pdf_path)
            except Exception:
                tb = traceback.format_exc()
                _pause_and_notify(item, msg_error_download_failed(item, str(sys.exc_info()[1]), tb))
                sys.exit(1)

            try:
                verify_download(pdf_path, item["size_mb"])
            except RuntimeError as e:
                tb = traceback.format_exc()
                _pause_and_notify(item, msg_error_download_failed(item, str(e), tb))
                sys.exit(1)

            thumb_ok = generate_thumbnail(pdf_path, thumb_path)
            if not thumb_ok:
                print("[INFO] Thumbnail failed — uploading without it.")
                thumb_path = None

            upload_start = utc_now()
            print(f"[UPLOAD] {item['filename_friendly']}")

            try:
                result = upload_document(
                    channel_id=channel_id,
                    file_path=pdf_path,
                    filename=item["filename_friendly"],
                    caption=item["filename_friendly"],
                    thumb_path=thumb_path,
                )
            except Exception:
                tb = traceback.format_exc()
                _pause_and_notify(item, msg_error_upload_failed(item, str(sys.exc_info()[1]), tb))
                sys.exit(1)

            if not result.get("success"):
                _pause_and_notify(item, msg_error_upload_failed(item, str(result.get("error", "")), ""))
                sys.exit(1)

            upload_end = utc_now()
            print(f"[UPLOAD] Done in {format_duration((upload_end - upload_start).total_seconds())}")

        # Delete cron-job.org dispatch job
        delete_cronjob(item.get("cronjob_job_id"))

        # Update state
        for q in queue["items"]:
            if q["filename_orig"] == item["filename_orig"]:
                q["status"]          = "uploaded"
                q["uploaded_at_utc"] = upload_end.strftime("%Y-%m-%dT%H:%M:%SZ")
                q["cronjob_job_id"]  = None
                break

        git_pull()
        write_queue(queue)
        write_last_uploaded(item["filename_orig"])
        append_history(
            f"\n## {format_date_ist(upload_end)} {format_time_ist(upload_end)} IST"
            f" — {item['filename_friendly']}\n"
            f"Original: {item['filename_orig']} • {item['size_mb']:.2f} MB"
            f" • Channel msg_id: {result.get('channel_msg_id')}"
            f" • SHA256: {sha256[:16]}…\n"
        )
        git_commit_and_push(
            f"✅ Uploaded {item['filename_orig']}",
            files=[QUEUE_FILE, LAST_UPLOADED_FILE, HISTORY_FILE],
        )

        bs          = queue.get("batch_started_at_utc")
        batch_start = parse_utc(bs) if bs else upload_start

        send_to_owner(msg_upload_success(
            item=item, start=upload_start, end=upload_end,
            index=index, total=total, batch_start=batch_start,
        ))
        print(f"[INFO] Notification sent ({index}/{total}).")

    except SystemExit:
        raise
    except Exception:
        tb  = traceback.format_exc()
        exc = str(sys.exc_info()[1])
        print(f"[ERROR]\n{tb}")
        _pause_and_notify(item, msg_error_generic("Unexpected Uploader Error", exc, tb))
        sys.exit(1)


def _pause_and_notify(item: dict, message: str):
    try:
        git_pull()
        write_status("paused", "# Auto-paused: upload error. Send /resume to retry.")
        git_commit_and_push("❌ Auto-paused: upload error", files=[STATUS_FILE])
    except Exception as e:
        print(f"[ERROR] Failed to commit pause: {e}")
    try:
        send_to_owner(message)
    except Exception as e:
        print(f"[ERROR] Failed to send notification: {e}")


if __name__ == "__main__":
    main()
