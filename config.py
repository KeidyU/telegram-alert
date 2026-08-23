"""
Configuration for the Telegram BDV alert monitor.

Secrets (api_id, api_hash, chat id) are loaded from a local .env file so they
never get hardcoded or accidentally shared. See .env.example for the template.
"""

import os
import re
import sys

from dotenv import load_dotenv

load_dotenv()

# --- Matching rule ---------------------------------------------------------
# A message is treated as an alert only if ALL of these hold (see
# main.py:message_matches, matching is case/accent-insensitive):
#   - contains "ACTIVO" or "ACTIVA"
#   - contains "INTERVENCION"
#   - contains one of the target banks below (code or full name)
#   - does NOT contain "CERRADO" or "CERRADA" anywhere (strict exclusion,
#     regardless of the rest of the message)

# --- Target banks ------------------------------------------------------
# bancos.txt has one bank per line: "<CODE>  <Full name>" (2+ spaces
# between them), e.g. "BDV  BANCO DE VENEZUELA". Lines with no separate
# full name (e.g. "BANPLUS") use the same value for both.
BANCOS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "bancos.txt")


def load_bancos() -> dict:
    """Parses bancos.txt into {CODE: full_name}."""
    bancos = {}
    if not os.path.exists(BANCOS_FILE):
        return bancos
    with open(BANCOS_FILE, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            parts = re.split(r"\s{2,}", line, maxsplit=1)
            code = parts[0].strip()
            fullname = parts[1].strip() if len(parts) == 2 else code
            bancos[code.upper()] = fullname
    return bancos


BANCOS = load_bancos()

# Comma-separated bank codes to watch for (must match the first column of
# bancos.txt), case-insensitive. Change this in .env to watch other banks,
# e.g. TARGET_BANK_CODES=BDV,BBVA
TARGET_BANK_CODES = [
    c.strip().upper()
    for c in os.getenv("TARGET_BANK_CODES", "BDV").split(",")
    if c.strip()
]


def get_target_bank_terms() -> set:
    """Text fragments (codes + full names) to match against, for the
    configured TARGET_BANK_CODES."""
    terms = set()
    for code in TARGET_BANK_CODES:
        terms.add(code)
        fullname = BANCOS.get(code)
        if fullname:
            terms.add(fullname)
    return terms


# --- Telegram API credentials --------------------------------------------
# From https://my.telegram.org -> "API development tools"
API_ID_RAW = os.getenv("TELEGRAM_API_ID")
API_HASH = os.getenv("TELEGRAM_API_HASH")

# --- Target chat -----------------------------------------------------------
# Numeric chat/channel/group ID, or a @username string. Use
# `python main.py --list-chats` to find the right ID.
CHAT_ID_RAW = os.getenv("TELEGRAM_CHAT_ID")

# --- Session file name ---------------------------------------------------
SESSION_NAME = os.getenv("TELEGRAM_SESSION_NAME", "bdv_monitor")

# --- Optional: link to open on a match ------------------------------------
BDV_URL = os.getenv("BDV_URL", "https://www.bancodevenezuela.com/")


def _require(value, name):
    if not value:
        print(
            f"ERROR: {name} is not set. Copy .env.example to .env and fill it in.",
            file=sys.stderr,
        )
        sys.exit(1)
    return value


def get_api_id() -> int:
    raw = _require(API_ID_RAW, "TELEGRAM_API_ID")
    try:
        return int(raw)
    except ValueError:
        print("ERROR: TELEGRAM_API_ID must be a number.", file=sys.stderr)
        sys.exit(1)


def get_api_hash() -> str:
    return _require(API_HASH, "TELEGRAM_API_HASH")


def get_chat_id():
    """Returns an int if the .env value is numeric, otherwise the raw string
    (so a @username also works)."""
    raw = _require(CHAT_ID_RAW, "TELEGRAM_CHAT_ID")
    try:
        return int(raw)
    except ValueError:
        return raw
