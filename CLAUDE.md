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

# Build standalone dist\BDVAlert.exe (PyInstaller onefile) + copy .env/bancos.txt next to it
.\build.ps1
```

`config.BASE_DIR` is the exe's folder when frozen, and the source folder otherwise.
`.env`, `bancos.txt` and the `.session` file are always resolved against it, never against
the CWD or PyInstaller's temp `_MEIPASS` dir.

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

## Roadmap

This project evolves in phases. Each phase is additive — earlier phases keep working,
selected via `ALERT_MODE` in `.env` once Phase 1 lands.

### Phase 0 — Windows personal alert (current, shipped)
What exists today: `main.py` logs in as a personal Telegram user account (Telethon) to
monitor one chat, and on a match shows a Windows toast, plays a repeating system sound,
and optionally opens `BDV_URL` in the default browser. Single operator, runs on their own
Windows PC, no server, no other subscribers.

### Phase 1 — Telegram bot alert via self-hosted n8n (next)
Goal: let other people subscribe (by email) and get a push notification on their phone
that they can tap to open the bank, without building a mobile app. Scope for the MVP: one
subscriber, one bank (BDV).

- The Phase 0 Telethon listener keeps running (unchanged matching logic), but moves to a
  systemd service on the KVM4 VPS instead of a Windows desktop.
- A new `ALERT_MODE` setting in `.env` (`windows` | `mobile`) selects the reaction path in
  `main.py`, so Phase 0's behavior is preserved and selectable, not removed:
  - `ALERT_MODE=windows` (default): today's Windows toast + sound + browser open.
  - `ALERT_MODE=mobile`: POST the match (bank + message) to an n8n webhook instead, with a
    shared-secret header.
- n8n owns everything past the webhook: a `subscribers` Data table (chat_id, email,
  created_at), a single Telegram Trigger workflow on the notify bot that handles signup
  end-to-end (`/start` creates the row and asks for an email; the subscriber's next message
  fills it in), and a Webhook workflow that messages each subscriber with an inline "Open
  bank" URL button pointing at `BDV_URL`.
- Two distinct Telegram identities, never shared: the existing user account only reads the
  source chat; a new bot (via @BotFather) only sends outbound alerts — this split is
  required because Telegram inline buttons are a bot-only feature.
- See `plan-migration-to-hosting.md` for the detailed implementation plan.

**Note — multi-bank support (future):** Phase 1 above is scoped to one bank (BDV). When
more banks are added (the matching logic already supports this via `TARGET_BANK_CODES`),
keep one shared notify bot rather than one bot per bank: each subscriber picks which banks
they care about (a field on their `subscribers` row), and the alert message states which
bank triggered plus the right URL button. A bot per bank means a new bot token + n8n
credential + separate subscription per bank for every bank added — linear complexity for
no technical benefit. The only argument for a dedicated bot per bank is branding/
co-ownership, which is a business call, not a technical one.

### Phase 2 — Native mobile app (future)
Goal: a dedicated app with native push notifications (FCM/APNs) and, if the bank ever
exposes one, a true in-app deep link instead of a website URL. Not started — this is a
materially larger effort (app build/signing/distribution, device-token registration,
notification handling) than Phase 1, and is deliberately deferred until Phase 1 validates
that people actually want to subscribe.

### Phase 3 — Scale (future, not started)
Goal: handle subscriber counts where Phase 1's design breaks down — written down now so
it isn't rediscovered from scratch later, not because it's needed yet (Phase 1 is one
subscriber). Known limits, in order of what bites first:
- Workflow count never scales with subscribers — "Subscribe" and "Alert" stay as two fixed
  n8n workflows at any scale. What has to scale is the data/queue layer behind them, never
  one-workflow-per-user.
- Looping over every subscriber inside a single webhook execution breaks down well before
  very large subscriber counts — n8n needs **queue mode** (Redis + multiple worker
  processes) so "Alert" enqueues a fan-out job instead of iterating inline.
- The real ceiling isn't n8n — it's the **Telegram Bot API's own rate limit** (~30
  messages/sec per bot). Sequentially notifying a very large subscriber base through one
  bot would take hours; fixing that means sharding across bots and/or leaning on Phase 2's
  native-app push (FCM/APNs multicast), which is built for mass delivery.
- The `subscribers` store moves from an n8n Data table (fine at Phase 1's scale) to a real
  database (e.g. Postgres), with n8n orchestrating rather than storing.

## Configuration

All secrets and per-deployment settings live in `.env` (see `.env.example` for the
template), never hardcoded: `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` (from
https://my.telegram.org), `TELEGRAM_CHAT_ID` (numeric ID or `@username`, found via
`--list-chats`), `TELEGRAM_SESSION_NAME`, `TARGET_BANK_CODES`, and `BDV_URL`. `.env` is
gitignored; only `.env.example` should ever be committed.
