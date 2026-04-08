# scripts/utils/telegram_client.py
"""
Telegram uploader using Pyrogram (MTProto API).
Supports files up to 2 GB in bot mode.

Policy:
  - Files are uploaded to the PUBLIC CHANNEL only.
  - Owner receives TEXT notifications only (via Bot API HTTP, not Pyrogram).
  - No file copies are sent to the owner's private chat.

Confirmed Telegram filename storage behaviour (from real upload runs):
  1. Spaces → underscores:         'A B.pdf'   → 'A_B.pdf'
  2. ' - ' separator → removed:   'A - B.pdf' → 'A_B.pdf'
     (dash and surrounding spaces collapse to a single underscore)

Verification: _norm() collapses any run of non-word/non-Devanagari characters
to a single underscore, then lowercases. Handles both behaviours correctly.
"""

import asyncio, os, re
from pyrogram import Client, enums


def _make_client() -> Client:
    return Client(
        name="kishor_publisher_bot",
        workdir="/tmp",
        api_id=int(os.environ["TELEGRAM_API_ID"]),
        api_hash=os.environ["TELEGRAM_API_HASH"],
        bot_token=os.environ["TELEGRAM_BOT_TOKEN"],
    )


def _parse_chat_id(value: str):
    try: return int(value)
    except ValueError: return value


def _norm(filename: str) -> str:
    """
    Normalise filename for comparison against what Telegram stores.
    Collapses all runs of non-alphanumeric/non-Devanagari characters
    (spaces, dashes, dots, etc.) to a single underscore, then lowercases.

    Examples (all verified against real Telegram upload logs):
      'किशोर डिसेंबर २०२५ - Kishor December 2025.pdf'
        → 'किशोर_डिसेंबर_२०२५_kishor_december_2025_pdf'
      'किशोर_डिसेंबर_२०२५_Kishor_December_2025.pdf'   (stored by Telegram)
        → 'किशोर_डिसेंबर_२०२५_kishor_december_2025_pdf'
      Both match ✓
    """
    s = re.sub(r'[^\w\u0900-\u097F]+', '_', filename.strip())
    return s.strip('_').lower()


async def _do_upload(channel_id, file_path, filename, caption, thumb_path):
    """Upload document to the channel only. Returns result dict."""
    result = {"channel_msg_id": None, "file_id": None, "success": False}

    ch    = _parse_chat_id(channel_id)
    thumb = thumb_path if (thumb_path and os.path.isfile(thumb_path)) else None

    async with _make_client() as app:
        print(f"[UPLOAD] Sending to channel: {filename}")
        channel_msg = await app.send_document(
            chat_id=ch,
            document=file_path,
            file_name=filename,
            caption=caption,
            thumb=thumb,
            parse_mode=enums.ParseMode.DISABLED,
        )

        actual        = channel_msg.document.file_name if channel_msg.document else ""
        norm_expected = _norm(filename)
        norm_actual   = _norm(actual)

        print(f"[UPLOAD] Filename sent  : {filename!r}")
        print(f"[UPLOAD] Filename stored: {actual!r}")
        print(f"[UPLOAD] Norm expected  : {norm_expected!r}")
        print(f"[UPLOAD] Norm actual    : {norm_actual!r}")
        print(f"[UPLOAD] Match          : {norm_expected == norm_actual}")

        if norm_actual != norm_expected:
            raise RuntimeError(
                f"Filename mismatch after upload.\n"
                f"  Expected (normalised): {norm_expected!r}\n"
                f"  Got      (normalised): {norm_actual!r}\n"
                f"  This suggests the wrong file was uploaded."
            )

        result["channel_msg_id"] = channel_msg.id
        result["file_id"]        = channel_msg.document.file_id
        result["success"]        = True
        print(f"[UPLOAD] Channel OK — msg_id={channel_msg.id}")

    return result


def upload_document(channel_id, file_path, filename, caption, thumb_path=None):
    """Synchronous entry point. Uploads to channel only."""
    return asyncio.run(
        _do_upload(channel_id, file_path, filename, caption, thumb_path)
    )
