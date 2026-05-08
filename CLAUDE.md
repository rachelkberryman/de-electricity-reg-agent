# DE Electricity Regulation Monitor

## What this project does
Monitors German electricity regulation sources weekly and emails a digest of new changes.

## Key files
- `agent.py` — main script; run with `python agent.py`
- `config.json` — SMTP + recipient configuration (or use env vars)
- `.seen_changes.json` — auto-generated cache to avoid duplicate notifications
- `.github/workflows/monitor.yml` — GitHub Actions schedule (Mondays 07:00 UTC)

## Architecture
1. **Claude Agent SDK** runs a sub-agent with WebSearch + WebFetch tools
2. Agent searches BNetzA, BMWK, EUR-Lex, Clearingstelle EEG|KWKG, ENTSO-E
3. Returns structured JSON array of regulatory changes
4. Deduplication via `.seen_changes.json`
5. HTML email digest sent via SMTP (Gmail / any provider)

## Regulatory sources covered
- Bundesnetzagentur (BNetzA) — tariffs, grid codes, market rules
- BMWK — energy policy, EEG/KWKG amendments
- EnWG amendments
- EU directives (ACER, ENTSO-E, Clean Energy Package)
- Clearingstelle EEG|KWKG — rulings and interpretations
- BSI/KRITIS — cybersecurity for critical infrastructure

## Configuration
Edit `config.json` or set environment variables:
| Env var | Purpose |
|---------|---------|
| `ANTHROPIC_API_KEY` | Anthropic API key |
| `TELEGRAM_BOT_TOKEN` | Bot token from @BotFather |
| `TELEGRAM_CHAT_ID` | Your personal, group, or channel chat ID |

## Running locally
```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py
```

## Deploying on GitHub Actions
1. Push this repo to GitHub
2. Add secrets: `ANTHROPIC_API_KEY`, `SMTP_USER`, `SMTP_PASS`, `NOTIFY_EMAIL`
3. The workflow runs automatically every Monday at 07:00 UTC
4. Or trigger manually via Actions → "Run workflow"
