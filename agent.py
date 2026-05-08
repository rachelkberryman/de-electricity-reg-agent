"""
German Electricity Regulation Monitor
Uses the Claude Agent SDK to search for regulatory changes and sends Telegram notifications.
"""

import anyio
import json
import os
import urllib.request
import urllib.parse
from datetime import datetime, timedelta
from pathlib import Path

from claude_agent_sdk import query, ClaudeAgentOptions

# ─────────────────────────────────────────────
# Configuration — edit config.json or set env vars
# ─────────────────────────────────────────────

CONFIG_FILE = Path(__file__).parent / "config.json"


def load_config() -> dict:
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return {}


def get_cfg(key: str, default=None):
    cfg = load_config()
    return os.environ.get(key.upper(), cfg.get(key, default))


# ─────────────────────────────────────────────
# Agent prompt
# ─────────────────────────────────────────────

SYSTEM_PROMPT = """You are a specialist regulatory-intelligence agent for the German electricity market.

Your job:
1. Search the web for regulatory changes published in the LAST 7 DAYS.
2. Cover all of these sources / topics:
   - Bundesnetzagentur (BNetzA): grid tariffs, network codes, market surveillance decisions
   - BMWK (Bundesministerium für Wirtschaft und Klimaschutz): energy policy, EEG amendments
   - EnWG (Energiewirtschaftsgesetz): legislative amendments
   - EEG (Erneuerbare-Energien-Gesetz): feed-in tariff and RES support changes
   - KWKG (Kraft-Wärme-Kopplungsgesetz): CHP regulation updates
   - EU electricity market regulations with direct effect in Germany (ACER, ENTSO-E, Clean Energy Package)
   - Clearingstelle EEG|KWKG: new rulings or interpretations
   - BSI/KRITIS: cybersecurity rules for critical energy infrastructure
3. For each change found, produce a structured JSON entry with these fields:
   - title: short headline (max 15 words)
   - source: organisation that published it
   - url: direct link if available, else null
   - date: publication date (YYYY-MM-DD) if known, else null
   - category: one of [tariff, grid_code, renewable, cogeneration, market_design, cybersecurity, eu_directive, other]
   - impact: one of [high, medium, low]
   - summary: 2-3 sentence plain-language explanation of what changed and why it matters
4. If you find NO changes in any category, return an empty list.
5. Return ONLY a valid JSON array — no markdown, no preamble, no trailing text.

Example output format:
[
  {
    "title": "BNetzA raises gas network entry tariff by 3%",
    "source": "Bundesnetzagentur",
    "url": "https://www.bundesnetzagentur.de/...",
    "date": "2025-05-01",
    "category": "tariff",
    "impact": "high",
    "summary": "The BNetzA approved a 3% increase in gas network entry tariffs effective June 2025. This follows the annual cost review under ARegV. Consumers and industrial users can expect higher network charges on their bills from Q3 2025."
  }
]
"""

USER_PROMPT = (
    f"Today is {datetime.now().strftime('%Y-%m-%d')}. "
    "Search for German electricity regulation changes published in the last 7 days. "
    "Return only a JSON array as described."
)


# ─────────────────────────────────────────────
# Run the agent
# ─────────────────────────────────────────────

async def run_agent() -> list[dict]:
    print("🔍 Starting regulatory scan …")
    collected_text = []

    options = ClaudeAgentOptions(
        allowed_tools=["WebSearch", "WebFetch"],
        permission_mode="acceptEdits",
    )

    full_prompt = f"{SYSTEM_PROMPT}\n\n{USER_PROMPT}"

    async for message in query(
        prompt=full_prompt,
        options=options,
    ):
        # Collect any text output from the agent
        if hasattr(message, "content"):
            for block in message.content:
                if hasattr(block, "text"):
                    collected_text.append(block.text)
        elif hasattr(message, "text"):
            collected_text.append(message.text)

    raw = "\n".join(collected_text).strip()
    print(f"📄 Agent raw output ({len(raw)} chars)")

    # Parse JSON — strip any accidental markdown fences
    cleaned = raw.replace("```json", "").replace("```", "").strip()
    try:
        results = json.loads(cleaned)
        if not isinstance(results, list):
            results = []
    except json.JSONDecodeError as e:
        print(f"⚠️  Could not parse JSON: {e}\nRaw output:\n{raw[:500]}")
        results = []

    return results


# ─────────────────────────────────────────────
# Persistence — avoid duplicate notifications
# ─────────────────────────────────────────────

SEEN_FILE = Path(__file__).parent / ".seen_changes.json"


def load_seen() -> set[str]:
    if SEEN_FILE.exists():
        with open(SEEN_FILE) as f:
            return set(json.load(f))
    return set()


def save_seen(seen: set[str]):
    with open(SEEN_FILE, "w") as f:
        json.dump(sorted(seen), f, indent=2)


def dedup(changes: list[dict]) -> list[dict]:
    seen = load_seen()
    new = []
    for c in changes:
        key = f"{c.get('source','')}::{c.get('title','')}"
        if key not in seen:
            new.append(c)
            seen.add(key)
    save_seen(seen)
    return new


# ─────────────────────────────────────────────
# Notification — Telegram
# ─────────────────────────────────────────────

IMPACT_EMOJI = {"high": "🔴", "medium": "🟡", "low": "🟢"}
CATEGORY_LABEL = {
    "tariff": "Tariff",
    "grid_code": "Grid Code",
    "renewable": "Renewables (EEG)",
    "cogeneration": "Cogeneration (KWKG)",
    "market_design": "Market Design",
    "cybersecurity": "Cybersecurity",
    "eu_directive": "EU Directive",
    "other": "Other",
}

# Telegram Bot API caps a single message at 4096 chars.
TELEGRAM_MAX_CHARS = 4096


def build_telegram_messages(changes: list[dict]) -> list[str]:
    """
    Build one or more Telegram messages (MarkdownV2 format).
    Splits automatically if the digest exceeds the 4096-char limit.
    """
    week  = (datetime.now() - timedelta(days=7)).strftime("%d %b")
    today = datetime.now().strftime("%d %b %Y")

    def escape(text: str) -> str:
        """Escape special chars for Telegram MarkdownV2."""
        for ch in r"\_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    header = (
        f"⚡ *DE Electricity Regulation Digest*\n"
        f"{escape(week)} – {escape(today)}  \\|  {len(changes)} new item\\(s\\)\n"
        f"{'─' * 30}\n\n"
    )

    blocks: list[str] = []
    for c in changes:
        emoji = IMPACT_EMOJI.get(c.get("impact", "low"), "⚪")
        cat   = CATEGORY_LABEL.get(c.get("category", "other"), c.get("category", ""))
        title = escape(c.get("title", "—"))
        url   = c.get("url")
        date  = escape(c.get("date") or "date unknown")
        src   = escape(c.get("source", ""))
        summ  = escape(c.get("summary", ""))

        title_part = f"[{title}]({url})" if url else f"*{title}*"
        block = (
            f"{emoji} {title_part}\n"
            f"_{src} · {date} · {escape(cat)}_\n"
            f"{summ}\n\n"
        )
        blocks.append(block)

    # Pack blocks into messages that fit the Telegram limit
    messages: list[str] = []
    current = header
    for block in blocks:
        if len(current) + len(block) > TELEGRAM_MAX_CHARS:
            messages.append(current.rstrip())
            current = block
        else:
            current += block
    if current.strip():
        messages.append(current.rstrip())

    return messages


def telegram_send(bot_token: str, chat_id: str, text: str):
    """Send a single MarkdownV2 message via the Telegram Bot API."""
    url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2",
        "disable_web_page_preview": True,
    }).encode()
    req = urllib.request.Request(url, data=payload,
                                  headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")


def send_telegram(changes: list[dict]):
    bot_token = get_cfg("telegram_bot_token")
    chat_id   = get_cfg("telegram_chat_id")

    if not all([bot_token, chat_id]):
        print("⚠️  Telegram not configured — printing digest to stdout instead.\n")
        for c in changes:
            print(f"  [{c.get('impact','?').upper()}] {c.get('title')} — {c.get('source')}")
            print(f"         {c.get('summary')}\n")
        return

    messages = build_telegram_messages(changes)
    for i, msg in enumerate(messages, 1):
        telegram_send(bot_token, chat_id, msg)
        print(f"📨 Telegram message {i}/{len(messages)} sent to chat {chat_id}")
    print("✅ Telegram notification complete.")


# ─────────────────────────────────────────────
# Entrypoint
# ─────────────────────────────────────────────

async def main():
    changes = await run_agent()
    print(f"📋 Found {len(changes)} change(s) total")

    new_changes = dedup(changes)
    print(f"🆕 {len(new_changes)} are new (not previously notified)")

    if not new_changes:
        print("✅ Nothing new to report — no notification sent.")
        return

    # Sort by impact: high → medium → low
    order = {"high": 0, "medium": 1, "low": 2}
    new_changes.sort(key=lambda c: order.get(c.get("impact", "low"), 3))

    send_telegram(new_changes)
    print("✅ Done.")


if __name__ == "__main__":
    anyio.run(main)
