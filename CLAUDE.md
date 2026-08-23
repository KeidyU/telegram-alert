# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Windows-only Python script that logs into Telegram as a user account (via Telethon,
not a bot) to monitor one specific chat in real time. When a message matches the alert
rule, it fires a Windows toast notification, plays a repeating system alert sound, and
optionally opens a URL in the browser.

## Commands

```powershell
# Setup (venv already exists at venv/)
venv\Scripts\pip install -r requirements.txt

# Find a chat's numeric ID (prints all dialogs: name + ID)
venv\Scripts\python main.py --list-chats

# Run the monitor
venv\Scripts\python main.py

# Compile-check after edits (no test suite exists)
venv\Scripts\python -m py_compile main.py config.py
```

There is no test suite, linter, or build step configured. To sanity-check changes to the
matching logic, run `message_matches()` from `main.py` against the sample messages in
`message-examples.txt` (see the verification pattern used when the matcher was last
changed: split the file on `example N:` blocks and check each one).

First run (`--list-chats` or `main.py`) prompts interactively in the terminal for phone
number, login code, and 2FA password if enabled; this creates `bdv_monitor.session` (or
whatever `TELEGRAM_SESSION_NAME` is set to). That `.session` file is a live login
credential for the Telegram account — never read its contents out, commit it, or send it
anywhere; it's already in `.gitignore`.

## Architecture

Three files carry all the logic:

- **`config.py`** — loads `.env` (via `python-dotenv`) and exposes typed getters
  (`get_api_id()`, `get_api_hash()`, `get_chat_id()`, etc.) that call `sys.exit(1)` with a
  clear message if a required value is missing, rather than raising deep in Telethon. Also
  parses `bancos.txt` into a `{CODE: full_name}` dict (`BANCOS`) and reads
  `TARGET_BANK_CODES` from `.env` (comma-separated bank codes to watch, default `BDV`).
  `get_target_bank_terms()` returns the set of text fragments (codes + full names) for the
  currently configured target banks.

- **`bancos.txt`** — the bank reference list, one bank per line as `CODE  Full Name`
  (2+ spaces as the separator). A line with no separate full name (e.g. `BANPLUS`) uses the
  same value for both code and name in the parsed dict. This file is the single source of
  truth for valid bank codes — add a line here before referencing a new code in
  `TARGET_BANK_CODES`.

- **`main.py`** — the Telethon client, the matching rule, and notification/sound logic.
  - `normalize_text()` lowercases and strips accents (NFKD decompose + drop combining
    marks) so all text comparisons are case- and accent-insensitive.
  - `message_matches()` is the alert rule: a message matches only if it contains
    `ACTIVO`/`ACTIVA` (`\bactiv[oa]\b`) **and** `INTERVENCION` **and** one of the target
    bank terms — **and** does NOT contain `CERRADO`/`CERRADA` anywhere. The CERRADO/CERRADA
    check is a strict, unconditional veto: if present, the message never matches regardless
    of what else it contains. The bank regex (`_BANK_RE`) is built once at import time from
    `config.get_target_bank_terms()`, so changing `TARGET_BANK_CODES` in `.env` requires a
    restart, not a code change.
  - `run_monitor()` registers a single `events.NewMessage(chats=chat_id)` handler scoped to
    one chat ID from config; `list_chats()` (the `--list-chats` flag) iterates all dialogs
    to help find that ID.
  - On a match: `show_notification()` (via `windows_toasts`) shows a toast titled
    `"🚨 BDV ACTIVA — COMPRA YA"` with the message body; `play_alert_sound()` loops
    `winsound.PlaySound("SystemExclamation", ...)` in a background thread (kept off the
    asyncio loop so it doesn't block Telethon); `OPEN_BROWSER_ON_MATCH` (top-of-file toggle
    in `main.py`) optionally opens `config.BDV_URL`.

## Configuration

All secrets and per-deployment settings live in `.env` (see `.env.example` for the
template), never hardcoded: `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` (from
https://my.telegram.org), `TELEGRAM_CHAT_ID` (numeric ID or `@username`, found via
`--list-chats`), `TELEGRAM_SESSION_NAME`, `TARGET_BANK_CODES`, and `BDV_URL`. `.env` is
gitignored; only `.env.example` should ever be committed.
