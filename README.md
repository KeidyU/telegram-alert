# Telegram BDV Alert Monitor

Watches one specific Telegram chat in real time and fires a Windows toast
notification + an audible alert the instant a message matching a trigger
phrase (default: "INTERVENCIÓN DIGITAL", accent/case-insensitive) arrives.

It logs in as **your own Telegram user account** (via Telethon), not a bot,
so it can watch any chat/group/channel you're a member of, including ones
where you can't add a bot.

## 1. Get your Telegram API credentials

1. Go to https://my.telegram.org and log in with the phone number of the
   Telegram account you want to monitor with.
2. Click **API development tools**.
3. Fill in the short form (app title/short name can be anything, e.g.
   "BDV Monitor"). Platform: Desktop.
4. You'll be given an **api_id** (a number) and an **api_hash** (a long
   hex string). Keep these private — they identify your app to Telegram.

## 2. Set up the project

A virtual environment has already been created at `venv/` and the files
below are already in place. If you ever need to redo it from scratch:

```powershell
cd C:\Projects\Telegram-Alert
python -m venv venv
venv\Scripts\pip install -r requirements.txt
```

## 3. Configure

1. Copy `.env.example` to `.env`:
   ```powershell
   copy .env.example .env
   ```
2. Open `.env` and fill in:
   - `TELEGRAM_API_ID` / `TELEGRAM_API_HASH` — from step 1.
   - `TELEGRAM_CHAT_ID` — leave the placeholder for now, you'll get the
     real value in step 4.

`.env` is listed in `.gitignore` and should never be committed or shared.

## 4. Find the BDV chat's numeric ID

Run:

```powershell
venv\Scripts\python main.py --list-chats
```

The **first time** you run any command, Telethon will ask for:
- Your phone number (international format, e.g. `+58...`)
- The login code Telegram sends you (via the Telegram app itself, or SMS)
- Your 2FA password, if you have one enabled

This creates a `bdv_monitor.session` file so you won't be asked again.

`--list-chats` prints every chat/group/channel you're in with its name and
numeric ID, e.g.:

```
              ID  Name
------------------------------------------------------------
   -1001234567890  BDV Señales Oficiales
       123456789  Some Other Chat
```

Copy the ID of the correct chat into `TELEGRAM_CHAT_ID` in `.env` (keep the
minus sign if there is one — negative IDs are groups/channels).

## 5. Alert rule and target banks

A message triggers an alert only when **all** of these hold (case- and
accent-insensitive, so "ACTIVO"/"activo"/"Activó" etc. all count):

- contains **ACTIVO** or **ACTIVA**
- contains **INTERVENCIÓN**
- mentions one of your target banks (code or full name)
- does **not** contain **CERRADO** or **CERRADA** anywhere — if it does,
  the message is skipped, no matter what else it says (strict exclusion)

Banks are defined in `bancos.txt` (one per line: `CODE  Full Name`). To
choose which banks you care about, set `TARGET_BANK_CODES` in `.env`:

```
TARGET_BANK_CODES=BDV
```

Comma-separate multiple codes to watch more than one bank, e.g.
`TARGET_BANK_CODES=BDV,BBVA,BNC`. Codes must match the first column of
`bancos.txt`. Add new banks by adding a line to `bancos.txt`.

## 6. Run the monitor

```powershell
venv\Scripts\python main.py
```

You should see:

```
Monitoring chat: BDV Señales Oficiales (-1001234567890)
Trigger phrase: 'INTERVENCION DIGITAL' (case/accent-insensitive)
Waiting for messages... (Ctrl+C to stop)
```

Leave this running. When a matching message arrives you'll get:
- A Windows toast titled **"🚨 BDV ACTIVA — COMPRA YA"** showing the message
  text.
- A repeated system alert sound.
- Your default browser opening the Banco de Venezuela site (set
  `OPEN_BROWSER_ON_MATCH = False` at the top of `main.py` to disable this).

Stop it any time with `Ctrl+C`.

## 7. Running on another PC (standalone .exe)

Build a single exe that doesn't need Python on the target machine:

```powershell
.\build.ps1
```

This produces `dist\` with `BDVAlert.exe`, `bancos.txt`, `.env.example` and
your `.env` (if present). It never copies the `.session` file. The exe always reads
`.env`, `bancos.txt` and the session file from its own folder.

On the other PC:

1. Copy the `dist\` folder. Make sure `.env` has that account's
   `TELEGRAM_API_ID` / `TELEGRAM_API_HASH`.
2. Open a terminal in that folder and run `BDVAlert.exe --list-chats`. Log in
   (phone, code, 2FA) and copy the right chat ID.
3. Put that ID in `TELEGRAM_CHAT_ID` in `.env`.
4. Run `BDVAlert.exe` (from a terminal or by double-click).

## Security notes

- **Never share or commit `bdv_monitor.session` (or `.env`).** The session
  file is equivalent to being logged into your Telegram account — anyone
  with it can read your chats and send messages as you.
- If you ever suspect the session file leaked, go to Telegram
  Settings → Devices and terminate that session.

## Files

| File              | Purpose                                            |
|-------------------|-----------------------------------------------------|
| `main.py`         | The monitor script (and `--list-chats` helper).     |
| `config.py`       | Loads settings from `.env`; matching rule setup lives here.|
| `bancos.txt`      | Bank code → full name list, used to build the bank regex. |
| `.env.example`    | Template for your local `.env` (secrets).           |
| `.env`            | Your real secrets — created by you, never committed.|
| `requirements.txt`| Python dependencies.                                |
| `venv/`           | Local virtual environment.                          |
