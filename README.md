# ⚡ DE Electricity Regulation Monitor

A Claude Agent SDK-powered script that **automatically searches for German electricity regulation changes** each week and emails you a structured digest.

## What it monitors

| Source | Coverage |
|--------|----------|
| **Bundesnetzagentur (BNetzA)** | Grid tariffs, network codes, market surveillance |
| **BMWK** | Energy policy, EEG/KWKG amendments |
| **EUR-Lex** | EU directives affecting Germany |
| **Clearingstelle EEG\|KWKG** | Legal interpretations and rulings |
| **ENTSO-E / ACER** | Grid operation rules |
| **BSI/KRITIS** | Cybersecurity for energy infrastructure |

## Quick start

### 1. Install

```bash
git clone <your-repo>
cd de-electricity-reg-agent
pip install -r requirements.txt
```

### 2. Create a Telegram bot

1. Open Telegram and message **@BotFather**
2. Send `/newbot` and follow the prompts → copy the **bot token**
3. Start a chat with your new bot (or add it to a group/channel)
4. Get your **chat ID**:
   - Personal chat: message `@userinfobot` → it replies with your ID
   - Group/channel: add `@userinfobot` to the group, it will show the group ID (starts with `-`)

### 3. Configure

Edit `config.json`:

```json
{
  "telegram_bot_token": "123456789:ABCdefGhIJKlmNoPQRsTUVwxyZ",
  "telegram_chat_id": "your-chat-id"
}
```

Or use environment variables: `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`.

### 4. Run

```bash
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py
```

If Telegram is not configured, the digest prints to stdout instead.

---

## Automated weekly schedule (GitHub Actions)

1. Push this repo to GitHub.
2. Add these **repository secrets** (`Settings → Secrets and variables → Actions`):
   - `ANTHROPIC_API_KEY`
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
3. The workflow (`.github/workflows/monitor.yml`) runs **every Monday at 07:00 UTC**.
4. You can also trigger it manually from the **Actions** tab → **Run workflow**.

---

## Sample Telegram message

```
⚡ DE Electricity Regulation Digest
01 May – 08 May 2025  |  2 new item(s)
──────────────────────────────

🔴 BNetzA updates balancing energy procurement rules
Bundesnetzagentur · 2025-05-06 · Market Design
The BNetzA issued new guidance on balancing ...

🟡 EEG 2025 amendment: new repowering bonus for onshore wind
BMWK · 2025-05-03 · Renewables (EEG)
A draft amendment to the EEG introduces a ...
```

---

## Customisation

- **Change frequency:** Edit the cron expression in `.github/workflows/monitor.yml`
- **Focus on specific topics:** Narrow the `SYSTEM_PROMPT` in `agent.py`
- **Add Slack notifications:** Replace / extend `send_email()` with a Slack webhook call
- **Widen to EU:** Expand the prompt to cover other member states

---

## Requirements

- Python 3.10+
- Claude subscription or Anthropic Console account with billing
- Claude Agent SDK (`pip install claude-agent-sdk`)
