# scripts/utils/notifications.py
"""
All Telegram notification message builders for Kishor Publisher.
Parse mode: HTML. All times shown in IST with "IST" suffix.
"""

import os, datetime, requests
from scripts.utils.naming import get_clock_emoji
from scripts.utils.state  import (
    to_ist, format_date_ist, format_time_ist, format_hhmm_ist, format_duration,
)

HEADER   = "🤖 <b>Kishor Publisher</b>"
BASE_URL = "https://kishor.ebalbharati.in/Archives/include/pdf/"


def send_to_owner(text: str):
    token   = os.environ["TELEGRAM_BOT_TOKEN"]
    chat_id = os.environ["TELEGRAM_OWNER_CHAT_ID"]
    resp    = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    print(f"[NOTIFY] HTTP {resp.status_code}")
    resp.raise_for_status()
    result = resp.json()
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result.get('description')}")
    print("[NOTIFY] Sent.")


# ── Detection report ───────────────────────────────────────────────────────────

def msg_new_files_detected(
    start: datetime.datetime, end: datetime.datetime,
    last_uploaded: str, items: list, tomorrow_ist: str,
) -> str:
    clock = get_clock_emoji(to_ist(start).hour)
    count = len(items)
    lines = [
        f"{HEADER}\n",
        f"⏰ Detection Report\n",
        (
            f"📆 <b>Date:</b> {format_date_ist(start)}\n"
            f"{clock} <b>Started:</b> {format_time_ist(start)} IST\n"
            f"{clock} <b>Ended:</b> {format_time_ist(end)} IST\n"
            f"⏱️ <b>Duration:</b> {format_duration((end - start).total_seconds())}\n"
        ),
        (
            f"📦 <b>{count} new magazine issue{'s' if count != 1 else ''} detected</b>\n"
            f"(after last uploaded <b>{last_uploaded}</b>)\n"
        ),
        f"📅 <b>Scheduled Uploads for Tomorrow ({tomorrow_ist})</b>",
    ]
    for item in items:
        sched_ist = to_ist(item["scheduled_at_utc"])
        lines.append(
            f"{get_clock_emoji(sched_ist.hour)} {sched_ist.strftime('%H:%M')} IST → "
            f"<code>{item['filename_friendly']}</code> "
            f"<b>({item['filename_orig']} • {item['size_mb']:.2f} MB)</b>"
        )
    lines.append("\n🔔 You will receive a notification after each upload.")
    return "\n".join(lines)


# ── Upload success ─────────────────────────────────────────────────────────────

def msg_upload_success(
    item: dict, start: datetime.datetime, end: datetime.datetime,
    index: int, total: int, batch_start: datetime.datetime,
) -> str:
    is_last   = (index == total)
    c_start   = get_clock_emoji(to_ist(start).hour)
    c_end     = get_clock_emoji(to_ist(end).hour)
    remaining = total - index
    tomorrow  = format_date_ist(end + datetime.timedelta(days=1))
    intro     = "🎉 <b>All Uploads Completed Successfully</b>\n" if is_last else ""

    body = (
        f"{HEADER}\n\n{intro}"
        f"📤 <b>{item['filename_orig']}</b> uploaded successfully\n"
        f"📁 <b>Uploaded Size:</b> {item['size_mb']:.2f} MB\n\n"
        f"📆 <b>Date:</b> {format_date_ist(start)}\n"
        f"{c_start} <b>Started:</b> {format_time_ist(start)} IST\n"
        f"{c_end} <b>Ended:</b> {format_time_ist(end)} IST\n"
        f"⏱️ <b>Duration:</b> {format_duration((end - start).total_seconds())}\n\n"
    )
    if is_last:
        body += (
            f"📊 <b>Progress:</b> {index}/{total} completed • Batch finished\n"
            f"⏱️ <b>Batch Duration:</b> {format_duration((end - batch_start).total_seconds())}\n\n"
            f"📅 Next detection check at <b>07:00 IST</b> tomorrow."
        )
    else:
        body += (
            f"📊 <b>Progress:</b> {index}/{total} completed • {remaining} remaining\n\n"
            f"⏲ Next upload scheduled in 60 minutes"
        )
    return body


# ── Large file notice ──────────────────────────────────────────────────────────

def msg_large_file_notice(item: dict) -> str:
    return (
        f"{HEADER}\n\n"
        f"📢 <b>Notice:</b> Large File (&gt;50 MB)\n\n"
        f"📂 <b>File:</b> <code>{item['filename_friendly']}</code>\n"
        f"📂 <b>Size:</b> {item['size_mb']:.2f} MB\n"
        f"🔗 <b>Source:</b> {BASE_URL}{item['filename_orig']}\n\n"
        f"✅ Pyrogram (MTProto) supports up to 2 GB. Proceeding…"
    )


# ── Error notifications ────────────────────────────────────────────────────────

def msg_error_upload_failed(item: dict, reason: str, tb: str) -> str:
    return (
        f"{HEADER}\n\n❌ <b>Error:</b> Upload Failed\n\n"
        f"📂 <b>File:</b> <code>{item['filename_friendly']}</code>\n"
        f"📂 <b>Size:</b> {item['size_mb']:.2f} MB\n"
        f"🔗 <b>Download:</b> {BASE_URL}{item['filename_orig']}\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"🧾 <b>Error Details:</b>\n<code>{_esc(tb[:1500])}</code>\n\n"
        f"⏸ Workflow <b>paused</b>\n\n"
        f"🛠 Send <b>/resume</b> to retry."
    )


def msg_error_detection_failed(reason: str, tb: str) -> str:
    return (
        f"{HEADER}\n\n❌ <b>Error:</b> Detection Failed\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"🧾 <b>Error Details:</b>\n<code>{_esc(tb[:1500])}</code>\n\n"
        f"⏸ Workflow <b>paused</b>\n\n"
        f"🛠 Send <b>/resume</b> to restart."
    )


def msg_error_download_failed(item: dict, reason: str, tb: str) -> str:
    return (
        f"{HEADER}\n\n❌ <b>Error:</b> Download / Verification Failed\n\n"
        f"📂 <b>File:</b> <code>{item['filename_friendly']}</code>\n"
        f"📂 <b>Size:</b> {item['size_mb']:.2f} MB\n"
        f"🔗 <b>Source:</b> {BASE_URL}{item['filename_orig']}\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"🧾 <b>Error Details:</b>\n<code>{_esc(tb[:1500])}</code>\n\n"
        f"⏸ Workflow <b>paused</b>\n\n"
        f"🛠 Send <b>/resume</b> to retry."
    )


def msg_error_verify_failed(item: dict, reason: str) -> str:
    return (
        f"{HEADER}\n\n❌ <b>Error:</b> Channel Verification Failed\n\n"
        f"📂 <b>File:</b> <code>{item['filename_friendly']}</code>\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"⏸ Workflow <b>paused</b>\n\n"
        f"🛠 Check your channel, then send <b>/resume</b>."
    )


def msg_error_generic(context: str, reason: str, tb: str) -> str:
    return (
        f"{HEADER}\n\n❌ <b>Error:</b> {_esc(context)}\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"🧾 <b>Error Details:</b>\n<code>{_esc(tb[:1500])}</code>\n\n"
        f"⏸ Workflow <b>paused</b>\n\n"
        f"🛠 Send <b>/resume</b> to restart."
    )


def msg_error_cronjob_creation(fname: str, reason: str) -> str:
    return (
        f"{HEADER}\n\n⚠️ <b>Warning:</b> cron-job.org Job Creation Failed\n\n"
        f"📂 <b>File:</b> <code>{fname}</code>\n\n"
        f"⚠️ <b>Reason:</b> {_esc(reason)}\n\n"
        f"📌 File is queued. Send <b>/resume</b> to re-schedule it,\n"
        f"   or manually trigger uploader from GitHub Actions."
    )


# ── Bot command replies ────────────────────────────────────────────────────────

def msg_cmd_status(status: str, last_uploaded: str, queue: dict) -> str:
    pending = sum(1 for i in queue.get("items", []) if i.get("status") == "pending")
    return (
        f"{HEADER}\n\n"
        f"📋 <b>Status:</b> {'✅ Active' if status == 'active' else '⏸ Paused'}\n"
        f"📂 <b>Last Uploaded:</b> <code>{last_uploaded}</code>\n"
        f"📦 <b>Queue:</b> {pending} item(s) pending"
    )


def msg_cmd_paused() -> str:
    return f"{HEADER}\n\n⏸ Workflow <b>paused</b> successfully."


def msg_cmd_resumed(overdue: int, scheduled: int) -> str:
    lines = [f"{HEADER}\n\n✅ Workflow <b>resumed</b> successfully."]
    if overdue:
        lines.append(f"\n⚡ {overdue} overdue item(s) → uploader triggered immediately.")
    if scheduled:
        lines.append(f"📅 {scheduled} future item(s) → cron-job.org jobs re-created.")
    return "\n".join(lines)


def msg_cmd_queue(queue: dict) -> str:
    items   = queue.get("items", [])
    pending = [i for i in items if i.get("status") == "pending"]
    if not pending:
        return f"{HEADER}\n\n📭 Upload queue is empty."
    uploaded = sum(1 for i in items if i.get("status") == "uploaded")
    lines    = [f"{HEADER}\n", f"📦 <b>Queue — {len(pending)} pending / {queue.get('total', len(items))} total</b>\n"]
    for item in pending:
        job_icon = "🔗" if item.get("cronjob_job_id") else "⚠️"
        lines.append(
            f"⏳ <code>{item['filename_friendly']}</code>\n"
            f"   📅 <b>{item.get('scheduled_ist_display', 'N/A')}</b>"
            f" • {item['size_mb']:.2f} MB {job_icon}"
        )
    if uploaded:
        lines.append(f"\n✅ {uploaded} already uploaded this batch.")
    lines.append("\n🔗 = cron-job.org scheduled  ⚠️ = needs /resume to reschedule")
    return "\n".join(lines)


def msg_cmd_history(text: str) -> str:
    return f"{HEADER}\n\n📜 <b>Recent Upload History</b>\n\n<code>{_esc(text)}</code>"


def msg_cmd_last(last_uploaded: str, friendly: str) -> str:
    return (
        f"{HEADER}\n\n📂 <b>Last Uploaded:</b>\n"
        f"<code>{last_uploaded}</code>\n→ <code>{friendly}</code>"
    )


def msg_cmd_help() -> str:
    return (
        f"{HEADER}\n\n📖 <b>Available Commands</b>\n\n"
        f"/status  — Status, last upload, queue size\n"
        f"/queue   — Full queue with IST schedule and trigger status\n"
        f"/last    — Last successfully uploaded issue\n"
        f"/history — Last 30 lines of upload history\n"
        f"/pause   — Pause checker and uploader\n"
        f"/resume  — Resume + re-trigger overdue uploads\n"
        f"/help    — Show this message"
    )


def msg_cmd_unknown(cmd: str) -> str:
    return (
        f"{HEADER}\n\n❓ Unknown command: <code>{_esc(cmd)}</code>\n\n"
        f"Send /help to see available commands."
    )


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
