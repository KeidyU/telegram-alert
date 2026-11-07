# Phase 1 implementation plan: Telegram bot alert via n8n

See `CLAUDE.md` → "Roadmap" for how this phase fits with Phase 0 (current Windows alert,
kept working) and Phase 2 (future native app).

## Architecture

    [Telethon script, VPS, systemd service]
       reads the monitored chat as the user account (unchanged matching logic)
       on message_matches() == True:
         if ALERT_MODE=windows: today's toast + sound + browser open (unchanged)
         if ALERT_MODE=mobile:
           POST https://<n8n-host>/webhook/bdv-alert   { bank, message }
           (shared-secret header)
                |
                v
    [n8n: "Alert" workflow — Webhook node]
       -> validate shared secret
       -> query Data table `subscribers` for rows with email set
       -> for each: Telegram node sendMessage (notify bot) with
          inline URL button -> BDV_URL

    [n8n: "Subscribe" workflow — Telegram Trigger node on the notify bot]
       -> on /start or first message from an unknown chat_id:
            create a `subscribers` row { chat_id, email: empty } -> ask for email
       -> on a later message from a chat_id with no email yet:
            store it as email -> confirm subscription
       -> on a message from an already-subscribed chat_id:
            reply "You're already subscribed."

Two distinct Telegram identities, never shared: the existing user account (Telethon
`.session`) only ever reads the source chat; a new bot (created via @BotFather) only ever
sends outbound alerts. This split is required because Telegram inline keyboard buttons
only render for bot-sent messages — sending from the user account instead would mean
dropping the tappable button in favor of a plain text link. Flagging this here in case
that trade-off isn't acceptable and the plain-link route is preferred later.

## Changes to this repo (when Phase 1 is implemented)

- `main.py`: branch `handle_match()` on `config.get_alert_mode()` —
  `"windows"` keeps the existing `show_notification()`/`play_alert_sound()`/
  `webbrowser.open()` path untouched; `"mobile"` POSTs `{bank, message}` plus a
  shared-secret header to the n8n webhook (new `requests` dependency). Windows-only
  imports (`windows_toasts`, `winsound`) stay guarded so the script still runs on Linux
  when `ALERT_MODE=mobile`.
- `config.py`: add `get_alert_mode()` (default `"windows"`), `get_alert_webhook_url()`,
  `get_webhook_secret()` — same `_require`-backed pattern as the existing getters, only
  required when `ALERT_MODE=mobile`.
- `.env.example`: document `ALERT_MODE`, `N8N_ALERT_WEBHOOK_URL`, `N8N_WEBHOOK_SECRET`.
- `requirements.txt`: add `requests`; `windows-toasts`/Windows-only pieces stay since
  `ALERT_MODE=windows` must keep working.
- `README.md`: document both `ALERT_MODE` values and add a "Deploying on the VPS" section
  (systemd unit, first interactive login over SSH to produce `.session` on the VPS itself,
  log location).

## n8n side (built in the n8n editor, not in this repo)

1. **Data table `subscribers`**: columns `chat_id`, `email`, `created_at`.
2. **Notify bot**: create via @BotFather; store its token as an n8n Telegram credential.
3. **Workflow "Subscribe"**: Telegram Trigger (notify bot) -> branch on whether a
   `subscribers` row exists for the incoming `chat_id` and whether `email` is set ->
   create row / store email / reply accordingly, per the flow in the diagram above.
4. **Workflow "Alert"**: Webhook (POST, header-auth secret matching `N8N_WEBHOOK_SECRET`)
   -> query `subscribers` where `email` is set -> Telegram `sendMessage` per row with the
   bank + message text and an inline URL button "Abrir Banco de Venezuela 🏦" -> `BDV_URL`.

## Deployment on the KVM4

- Copy the repo to the VPS; create a venv; `pip install -r requirements.txt`.
- Run `python main.py --list-chats` **interactively over SSH once** to complete the
  phone/code/2FA login and produce `.session` directly on the VPS; `chmod 600` it.
- Create a systemd unit (`telegram-alert.service`) running `main.py` under the venv,
  `Restart=on-failure`.
- Confirm the Telethon process can reach the n8n webhook URL (verify whether the reverse
  proxy routes localhost or only the public domain).

## Verification

1. `python -m py_compile main.py config.py` after edits.
2. Re-run `message_matches()` against `message-examples.txt` — confirm unchanged.
3. With `ALERT_MODE=windows`, confirm the existing toast/sound/browser behavior still
   works exactly as before (regression check).
4. With `ALERT_MODE=mobile` and the service stopped, manually `curl -X POST` the n8n
   webhook with a sample payload + correct secret header -> confirm the notify bot message
   arrives with a working "Abrir Banco de Venezuela" button.
5. Full signup loop: message the notify bot for the first time -> confirm a `subscribers`
   row is created and the bot asks for an email -> reply with an email -> confirm the row
   is updated and the bot confirms the subscription -> send another message -> confirm the
   bot replies "You're already subscribed."
6. End-to-end with `ALERT_MODE=mobile`: start the systemd service against the real
   monitored chat, trigger a matching message, confirm the push notification arrives and
   the button opens `BDV_URL`.
