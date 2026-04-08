# Kishor Publisher

Automated Telegram channel uploader for [Kishor monthly magazine](https://kishor.ebalbharati.in/Archives/).

Detects new issues, schedules uploads with 1-hour gaps, and publishes each as a properly named PDF to your Telegram channel — with Marathi+English filename, caption, and cover thumbnail.

---

## How It Works

| Workflow | What it does |
|---|---|
| `checker.yml` | Runs once daily. Scans the website for new issues. If found, builds the upload queue and creates scheduled upload jobs. Silent if nothing new. |
| `uploader.yml` | Uploads one queued file per run. Triggered automatically at the scheduled time. No cron — zero runs when queue is empty. |
| `bot.yml` | Polls Telegram for owner commands. |

**Upload schedule:** Files found on day D → first upload at 00:00 IST on day D+1, one file per hour.

> To change run times, edit the `cron:` lines in `.github/workflows/checker.yml` and `.github/workflows/bot.yml`.

---

## Repository Structure

```
kishor-publisher/
├── .github/workflows/
│   ├── checker.yml          # Daily detection + queue building
│   ├── uploader.yml         # Per-file upload (dispatch-only, no cron)
│   └── bot.yml              # Telegram command polling
├── scripts/
│   ├── checker.py           # Website scanner + dynamic job scheduler
│   ├── uploader.py          # Download + upload + cleanup
│   ├── bot.py               # Command handler + smart /resume
│   └── utils/
│       ├── naming.py        # Marathi/English filename builder
│       ├── state.py         # State I/O + IST helpers + git
│       ├── notifications.py # All Telegram message templates
│       ├── thumbnail.py     # PDF → JPEG thumbnail (quality=100)
│       ├── telegram_client.py  # Pyrogram MTProto uploader (up to 2 GB)
│       ├── github_api.py    # GitHub REST API + workflow dispatch
│       └── cronjob_api.py   # cron-job.org REST API (create/delete jobs)
├── state/
│   ├── last_uploaded.txt    # Last successfully uploaded filename
│   ├── pending_queue.json   # Upload queue with scheduled times
│   ├── uploader_status.txt  # active / paused
│   ├── upload_history.md    # Full upload log (auto-appended)
│   └── bot_offset.txt       # Telegram update offset (auto-managed)
└── requirements.txt
```

---

## Requirements

**GitHub Secrets** (repo → Settings → Secrets and variables → Actions):

| Secret | Description |
|---|---|
| `TELEGRAM_API_ID` | From https://my.telegram.org/apps |
| `TELEGRAM_API_HASH` | From https://my.telegram.org/apps |
| `TELEGRAM_BOT_TOKEN` | From @BotFather |
| `TELEGRAM_OWNER_CHAT_ID` | Your personal Telegram chat ID |
| `TELEGRAM_CHANNEL_ID` | Your channel's numeric ID |
| `GH_PAT` | GitHub Personal Access Token (Actions: read+write) |
| `CRON_JOB_ORG_API_KEY` | API key from cron-job.org (free account) |

**External service:** One job on [cron-job.org](https://cron-job.org) (free) to trigger the bot workflow every minute.

---

## Bot Commands

| Command | What it does |
|---|---|
| `/status` | Current status, last uploaded file, queue size |
| `/queue` | Full upload queue with IST schedule |
| `/last` | Last successfully uploaded issue |
| `/history` | Last 30 lines of upload history |
| `/pause` | Pause checker and uploader |
| `/resume` | Resume + re-trigger any overdue uploads |
| `/help` | List all commands |

---

## Checking Logs

Repo → **Actions** tab → click any run → click the job name → expand steps.

---

## Resuming After an Error

The bot sends a detailed error notification with full traceback. Send `/resume` to your bot after fixing the issue. It automatically re-dispatches overdue uploads and re-creates any missing scheduled jobs.

---

## Notes

- All uploads go to the **channel only**. The bot sends text notifications to the owner's private chat.
- Thumbnail is generated from the first PDF page at quality=100 (no compression, no blur).
- Pyrogram (MTProto) supports files up to 2 GB, bypassing the Bot API 50 MB limit.
- SHA-256 hash verified for every download and logged in `state/upload_history.md`.

---

## License

MIT
