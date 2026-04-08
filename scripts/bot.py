#!/usr/bin/env python3
# scripts/bot.py
"""
Kishor Publisher — Bot Command Handler
Triggered every 1 minute by cron-job.org (primary) or every 5 min GitHub cron (fallback).

Smart /resume:
  - Overdue pending items → triggers uploader.yml immediately via GH_PAT
  - Future items without cron-job.org job → re-creates missing jobs
"""

import sys, os, requests, traceback, datetime

sys.stdout.reconfigure(encoding="utf-8")
sys.stderr.reconfigure(encoding="utf-8")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from scripts.utils.state      import (
    read_status, read_queue, read_last_uploaded, read_bot_offset,
    write_bot_offset, write_status, git_commit_and_push,
    utc_now, to_ist, parse_utc,
    BOT_OFFSET_FILE, STATUS_FILE,
)
from scripts.utils.naming     import build_friendly_filename
from scripts.utils.github_api import update_file, trigger_workflow_dispatch
from scripts.utils.notifications import (
    msg_cmd_status, msg_cmd_paused, msg_cmd_resumed,
    msg_cmd_queue, msg_cmd_history, msg_cmd_last,
    msg_cmd_help, msg_cmd_unknown,
)


def get_updates(token: str, offset: int) -> list:
    resp = requests.get(
        f"https://api.telegram.org/bot{token}/getUpdates",
        params={"offset": offset, "timeout": 0, "limit": 100},
        timeout=15,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data.get("ok"):
        raise RuntimeError(f"getUpdates failed: {data.get('description')}")
    return data.get("result", [])


def send_reply(token: str, chat_id: int, text: str):
    resp = requests.post(
        f"https://api.telegram.org/bot{token}/sendMessage",
        json={"chat_id": chat_id, "text": text, "parse_mode": "HTML"},
        timeout=15,
    )
    resp.raise_for_status()


def _handle_resume() -> str:
    api_key = os.environ.get("CRON_JOB_ORG_API_KEY", "").strip()
    gh_pat  = os.environ.get("GH_PAT", "").strip()
    repo    = os.environ.get("GITHUB_REPOSITORY", "")

    update_file(STATUS_FILE, "active\n# Resumed via /resume bot command.\n",
                "✅ Resumed via /resume")

    now     = utc_now()
    queue   = read_queue()
    pending = [i for i in queue.get("items", []) if i.get("status") == "pending"]
    overdue = [i for i in pending if parse_utc(i["scheduled_at_utc"]) <= now]
    future  = [i for i in pending if parse_utc(i["scheduled_at_utc"]) >  now]

    if overdue and gh_pat and repo:
        print(f"[BOT] {len(overdue)} overdue — dispatching uploader…")
        trigger_workflow_dispatch("uploader.yml", gh_pat)

    scheduled = 0
    if future and api_key and gh_pat and repo:
        try:
            from scripts.utils.cronjob_api import create_dispatch_job
            from scripts.utils.state       import write_queue
            needs_job = [i for i in future if not i.get("cronjob_job_id")]
            for item in needs_job:
                sched_ist = to_ist(parse_utc(item["scheduled_at_utc"]))
                try:
                    job_id = create_dispatch_job(
                        api_key=api_key, gh_pat=gh_pat, gh_repo=repo,
                        workflow_file="uploader.yml",
                        title=f"Kishor Upload — {item['filename_orig']}",
                        ist_hour=sched_ist.hour, ist_minute=sched_ist.minute,
                        ist_day=sched_ist.day,   ist_month=sched_ist.month,
                    )
                    item["cronjob_job_id"] = job_id
                    scheduled += 1
                except Exception as e:
                    print(f"[BOT] Failed to re-create job for {item['filename_orig']}: {e}")
            if scheduled:
                write_queue(queue)
                git_commit_and_push(
                    f"[bot] Re-created {scheduled} cron-job.org job(s) on /resume",
                    files=["state/pending_queue.json"]
                )
        except Exception as e:
            print(f"[BOT] /resume scheduling error: {e}")

    return msg_cmd_resumed(len(overdue), scheduled)


def handle(cmd: str) -> str:
    word = cmd.strip().lower().split()[0].split("@")[0]

    if word == "/status":
        return msg_cmd_status(read_status(), read_last_uploaded(), read_queue())
    elif word == "/pause":
        update_file(STATUS_FILE, "paused\n# Paused via /pause bot command.\n", "⏸ Paused via /pause")
        return msg_cmd_paused()
    elif word == "/resume":
        return _handle_resume()
    elif word == "/queue":
        return msg_cmd_queue(read_queue())
    elif word == "/history":
        try:
            with open("state/upload_history.md", "r", encoding="utf-8") as f:
                lines = f.readlines()
            text = "".join(lines[-30:]).strip() or "(No history yet)"
        except FileNotFoundError:
            text = "(History file not found)"
        return msg_cmd_history(text)
    elif word == "/last":
        last = read_last_uploaded()
        try:    friendly = build_friendly_filename(last)
        except: friendly = last
        return msg_cmd_last(last, friendly)
    elif word == "/help":
        return msg_cmd_help()
    else:
        return msg_cmd_unknown(cmd.split()[0] if cmd.strip() else cmd)


def main():
    token    = os.environ["TELEGRAM_BOT_TOKEN"]
    owner_id = int(os.environ["TELEGRAM_OWNER_CHAT_ID"])
    offset   = read_bot_offset()

    print(f"[BOT] Polling offset={offset}")
    try:
        updates = get_updates(token, offset)
    except Exception as e:
        print(f"[BOT] getUpdates failed: {e}"); return

    if not updates:
        print("[BOT] No new updates."); return

    print(f"[BOT] {len(updates)} update(s).")
    new_offset = offset

    for update in updates:
        new_offset = max(new_offset, update["update_id"] + 1)
        message    = update.get("message") or update.get("edited_message")
        if not message: continue

        chat_id = message.get("chat", {}).get("id")
        text    = message.get("text", "").strip()
        if chat_id != owner_id:
            print(f"[BOT] Ignored non-owner {chat_id}"); continue
        if not text.startswith("/"): continue

        print(f"[BOT] Command: {text!r}")
        try:
            reply = handle(text)
        except Exception:
            tb    = traceback.format_exc()
            reply = (
                f"🤖 <b>Kishor Publisher</b>\n\n"
                f"❌ <b>Command error</b>\n<code>{tb[:800]}</code>"
            )
            print(f"[BOT] Error:\n{tb}")

        send_reply(token, chat_id, reply)
        print(f"[BOT] Replied to {text!r}")

    if new_offset != offset:
        try:
            update_file(BOT_OFFSET_FILE, str(new_offset), f"[bot] Offset → {new_offset}")
            print(f"[BOT] Offset saved: {new_offset}")
        except Exception as e:
            print(f"[BOT] GitHub API offset save failed: {e}")
            try:
                write_bot_offset(new_offset)
                git_commit_and_push(f"[bot] Offset → {new_offset}", files=[BOT_OFFSET_FILE])
            except Exception as e2:
                print(f"[BOT] Fallback commit failed: {e2}")


if __name__ == "__main__":
    main()
