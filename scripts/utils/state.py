# scripts/utils/state.py
"""
All state file I/O, IST time helpers, and git helpers.

Timezone policy:
    Stored → UTC (ISO 8601 Z suffix)
    Displayed → IST (UTC+5:30) with explicit "IST" label
"""

import json, os, subprocess, datetime

LAST_UPLOADED_FILE = "state/last_uploaded.txt"
QUEUE_FILE         = "state/pending_queue.json"
STATUS_FILE        = "state/uploader_status.txt"
HISTORY_FILE       = "state/upload_history.md"
BOT_OFFSET_FILE    = "state/bot_offset.txt"

IST_OFFSET = datetime.timedelta(hours=5, minutes=30)

_EMPTY_QUEUE: dict = {
    "batch_id": None, "total": 0,
    "detected_at_utc": None, "batch_started_at_utc": None, "items": [],
}


# ── Time helpers ───────────────────────────────────────────────────────────────

def utc_now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


def to_ist(dt: datetime.datetime) -> datetime.datetime:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone(IST_OFFSET))


def midnight_ist_next_day(detection_utc: datetime.datetime) -> datetime.datetime:
    """
    Returns UTC datetime of 00:00 IST on the next IST calendar day.
    e.g. Apr 6 03:30 UTC (= Apr 6 09:00 IST) → Apr 6 18:30 UTC (= Apr 7 00:00 IST)
    """
    ist_now       = to_ist(detection_utc)
    next_ist_date = ist_now.date() + datetime.timedelta(days=1)
    ist_tz        = datetime.timezone(IST_OFFSET)
    midnight      = datetime.datetime(
        next_ist_date.year, next_ist_date.month, next_ist_date.day,
        0, 0, 0, tzinfo=ist_tz
    )
    return midnight.astimezone(datetime.timezone.utc)


def format_date_ist(dt: datetime.datetime) -> str:
    return to_ist(dt).strftime("%d/%m/%Y")


def format_time_ist(dt: datetime.datetime) -> str:
    return to_ist(dt).strftime("%H:%M:%S")


def format_hhmm_ist(dt: datetime.datetime) -> str:
    return to_ist(dt).strftime("%H:%M")


def format_duration(seconds: float) -> str:
    s = int(seconds)
    if s < 60:
        return f"{s}s"
    m, s = divmod(s, 60)
    return f"{m:02d}m {s:02d}s"


def parse_utc(s: str) -> datetime.datetime:
    return datetime.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=datetime.timezone.utc
    )


# ── Readers ────────────────────────────────────────────────────────────────────

def read_last_uploaded() -> str:
    with open(LAST_UPLOADED_FILE, "r", encoding="utf-8") as f:
        return f.read().strip()


def read_queue() -> dict:
    if not os.path.exists(QUEUE_FILE):
        return dict(_EMPTY_QUEUE)
    with open(QUEUE_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return json.loads(content) if content else dict(_EMPTY_QUEUE)


def read_status() -> str:
    if not os.path.exists(STATUS_FILE):
        return "active"
    with open(STATUS_FILE, "r", encoding="utf-8") as f:
        first_line = f.readline().strip().lower()
    word = first_line.split()[0] if first_line else "active"
    return word if word in ("active", "paused") else "active"


def read_bot_offset() -> int:
    if not os.path.exists(BOT_OFFSET_FILE):
        return 0
    with open(BOT_OFFSET_FILE, "r", encoding="utf-8") as f:
        content = f.read().strip()
    return int(content) if content.isdigit() else 0


def get_effective_last(last_uploaded: str, queue: dict) -> str:
    items = queue.get("items", [])
    return items[-1]["filename_orig"] if items else last_uploaded


# ── Writers ────────────────────────────────────────────────────────────────────

def write_last_uploaded(fname: str):
    with open(LAST_UPLOADED_FILE, "w", encoding="utf-8") as f:
        f.write(fname)


def write_queue(q: dict):
    with open(QUEUE_FILE, "w", encoding="utf-8") as f:
        json.dump(q, f, ensure_ascii=False, indent=2)


def write_status(status: str, comment: str = ""):
    if not comment:
        comment = "# Edit to 'active' or 'paused'. Commit to apply, or use /pause /resume bot command."
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        f.write(f"{status}\n{comment}\n")


def write_bot_offset(offset: int):
    with open(BOT_OFFSET_FILE, "w", encoding="utf-8") as f:
        f.write(str(offset))


def append_history(text: str):
    with open(HISTORY_FILE, "a", encoding="utf-8") as f:
        f.write(text)


# ── Git helpers ─────────────────────────────────────────────────────────────────

def _run(cmd: list):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.stdout.strip():
        print(f"[GIT] {result.stdout.strip()}")
    if result.returncode != 0 and result.stderr.strip():
        print(f"[GIT ERR] {result.stderr.strip()}")
    result.check_returncode()
    return result


def git_pull():
    try:
        _run(["git", "pull", "--rebase", "origin", "main"])
    except Exception as e:
        print(f"[GIT] pull warning (non-fatal): {e}")


def git_commit_and_push(commit_message: str, files: list):
    _run(["git", "config", "--global", "user.name",  "kishor-publisher-bot"])
    _run(["git", "config", "--global", "user.email", "kishor-publisher@github.com"])
    for f in files:
        _run(["git", "add", f])
    diff = subprocess.run(["git", "diff", "--cached", "--exit-code"], capture_output=True)
    if diff.returncode == 0:
        print("[GIT] Nothing to commit.")
        return
    _run(["git", "commit", "-m", commit_message])
    _run(["git", "push"])
    print(f"[GIT] Pushed: {commit_message}")
