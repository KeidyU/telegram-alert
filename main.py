"""
Telegram BDV alert monitor.

Listens to one specific Telegram chat in real time (via Telethon, using your
own Telegram *user* account, not a bot) and fires a Windows toast
notification + an audible alert the instant a message matches the alert
rule (see message_matches() below and config.TARGET_BANK_CODES).

First-run: you'll be prompted in the terminal for your phone number and the
login code Telegram sends you (see README.md). After that, a .session file
stores your login so you won't be asked again -- keep that file private,
it grants full access to your Telegram account.

Usage:
    python main.py                 Start monitoring the configured chat.
    python main.py --list-chats    Print all your dialogs (name + numeric ID)
                                    so you can find the right TELEGRAM_CHAT_ID.
"""

import argparse
import re
import sys
import threading
import unicodedata
import webbrowser

from telethon import TelegramClient, events

import config
from windows_toasts import Toast, WindowsToaster

try:
    import winsound
except ImportError:  # pragma: no cover - this script is Windows-only
    winsound = None

# --- Behavior toggles -----------------------------------------------------
# Open the Banco de Venezuela site in your default browser when a match hits.
OPEN_BROWSER_ON_MATCH = True

# How many times to repeat the alert sound (extra loud/urgent on top of the
# toast's own notification sound).
ALERT_SOUND_REPEATS = 3


def normalize_text(text: str) -> str:
    """Lowercase and strip accents, so 'INTERVENCIÓN' and 'intervencion'
    compare equal."""
    text = text.lower()
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


# --- Alert rule ------------------------------------------------------------
# A message is an alert only if it contains ACTIVO/ACTIVA, contains
# INTERVENCION, and mentions one of the target banks (config.py ->
# TARGET_BANK_CODES, backed by bancos.txt) -- AND does NOT contain
# CERRADO/CERRADA anywhere (strict: that always disqualifies the message,
# no matter what else it says). All comparisons are case/accent-insensitive
# via normalize_text().
_ACTIVE_RE = re.compile(r"\bactiv[oa]\b")
_CLOSED_RE = re.compile(r"\bcerrad[oa]\b")
# Matches both "INTERVENCIÓN" and "INTERVENCION". normalize_text() already
# strips accents before this runs, but the [oó] alternative is kept as a
# belt-and-suspenders guard against any Unicode edge case.
_INTERVENCION_RE = re.compile(r"\bintervenci[oó]n\b")

_BANK_TERMS = [normalize_text(t) for t in config.get_target_bank_terms()]
_BANK_RE = re.compile(r"\b(?:" + "|".join(re.escape(t) for t in _BANK_TERMS) + r")\b") if _BANK_TERMS else None


def message_matches(text: str) -> bool:
    if not text or _BANK_RE is None:
        return False

    norm = normalize_text(text)

    if _CLOSED_RE.search(norm):
        return False  # strict: CERRADO/CERRADA anywhere disqualifies the message

    return bool(
        _ACTIVE_RE.search(norm)
        and _INTERVENCION_RE.search(norm)
        and _BANK_RE.search(norm)
    )


def play_alert_sound():
    """Play a loud, repeating system alert sound in a background thread so
    it doesn't block the Telethon event loop."""
    if winsound is None:
        return

    def _play():
        for _ in range(ALERT_SOUND_REPEATS):
            winsound.PlaySound("SystemExclamation", winsound.SND_ALIAS)

    threading.Thread(target=_play, daemon=True).start()


def show_notification(message_text: str):
    toaster = WindowsToaster("BDV Alert Monitor")
    toast = Toast()
    toast.text_fields = ["🚨 BDV ACTIVA — COMPRA YA", message_text]
    toaster.show_toast(toast)


def handle_match(message_text: str):
    print("\n=== MATCH ===")
    print(message_text)
    print("=============\n")

    show_notification(message_text)
    play_alert_sound()

    if OPEN_BROWSER_ON_MATCH:
        webbrowser.open(config.BDV_URL)


async def list_chats(client: TelegramClient):
    """Print every dialog (chat/group/channel) with its name and numeric ID,
    to help you find the right value for TELEGRAM_CHAT_ID in .env."""
    print(f"{'ID':>16}  Name")
    print("-" * 60)
    async for dialog in client.iter_dialogs():
        print(f"{dialog.id:>16}  {dialog.name}")


async def run_monitor(client: TelegramClient, chat_id):
    entity = await client.get_entity(chat_id)
    chat_name = getattr(entity, "title", None) or getattr(entity, "username", None) or str(chat_id)
    print(f"Monitoring chat: {chat_name} ({chat_id})")
    print(f"Watching banks: {', '.join(config.TARGET_BANK_CODES)}")
    print("Rule: (ACTIVO|ACTIVA) + INTERVENCION + <bank>, excluding CERRADO/CERRADA")
    print("Waiting for messages... (Ctrl+C to stop)\n")

    @client.on(events.NewMessage(chats=chat_id))
    async def _handler(event):
        text = event.raw_text or ""
        if message_matches(text):
            handle_match(text)

    await client.run_until_disconnected()


def main():
    parser = argparse.ArgumentParser(description="Telegram BDV alert monitor")
    parser.add_argument(
        "--list-chats",
        action="store_true",
        help="Print all your dialogs with their numeric IDs, then exit.",
    )
    args = parser.parse_args()

    api_id = config.get_api_id()
    api_hash = config.get_api_hash()

    client = TelegramClient(config.SESSION_NAME, api_id, api_hash)

    with client:
        if args.list_chats:
            client.loop.run_until_complete(list_chats(client))
        else:
            chat_id = config.get_chat_id()
            client.loop.run_until_complete(run_monitor(client, chat_id))


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nStopped.")
        sys.exit(0)
