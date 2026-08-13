"""
Daily Flower Prompt — Webhook Poster
------------------------------------
Posts one flower (name + photo + fun fact) to a Discord channel via a webhook.
Designed to be run once a day by GitHub Actions — no always-on server needed.

It cycles through the 50 flowers in flowers.json without repeating any until all
have been used (state tracked in remaining_flowers.json), then reshuffles.

Environment variables (set as GitHub Actions secrets):
  DISCORD_WEBHOOK_URL  (required)  the channel webhook URL
  ROLE_ID              (optional)  a role ID to ping on every post

Uses only the Python standard library — no pip install needed.
"""

import os
import json
import random
import urllib.parse
import urllib.request

FLOWERS_FILE = "flowers.json"
STATE_FILE = "remaining_flowers.json"
WIKI_API = "https://en.wikipedia.org/api/rest_v1/page/summary/"
USER_AGENT = "FlowerDrawingBot/3.0 (GitHub Actions daily poster)"

WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL", "").strip()
ROLE_ID = os.environ.get("ROLE_ID", "").strip()


def load_flowers():
    with open(FLOWERS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def load_state(valid_names):
    """Load names not yet drawn; reshuffle a full set if empty/invalid."""
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                remaining = json.load(f)
            remaining = [n for n in remaining if n in valid_names]
            if remaining:
                return remaining
        except (json.JSONDecodeError, OSError):
            pass
    pool = list(valid_names)
    random.shuffle(pool)
    return pool


def save_state(remaining):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(remaining, f, ensure_ascii=False, indent=2)


def fetch_image(wiki_title):
    """Return a photo URL from Wikipedia, or None on failure."""
    url = WIKI_API + urllib.parse.quote(wiki_title)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            data = json.load(resp)
    except Exception as exc:
        print(f"[warn] image fetch failed for '{wiki_title}': {exc!r}")
        return None
    original = data.get("originalimage") or {}
    thumb = data.get("thumbnail") or {}
    image_url = original.get("source") or thumb.get("source")
    print(f"[info] image for '{wiki_title}': {image_url}")
    return image_url


def post_to_webhook(payload):
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        WEBHOOK_URL,
        data=body,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=20) as resp:
        print(f"[info] webhook responded HTTP {resp.status}")


def main():
    if not WEBHOOK_URL:
        raise SystemExit("DISCORD_WEBHOOK_URL is not set.")

    flowers = load_flowers()
    by_name = {f["name"]: f for f in flowers}
    valid_names = list(by_name.keys())

    remaining = load_state(valid_names)
    name = remaining.pop()
    if not remaining:
        print("[info] cycle complete — reshuffling for a new round.")
        remaining = list(valid_names)
        random.shuffle(remaining)
    save_state(remaining)

    flower = by_name[name]
    image_url = fetch_image(flower["wiki"])

    embed = {
        "title": f"\U0001F338 Today's Flower: {flower['name']}",
        "description": f"*{flower['fact']}*\n\nDraw it however you like — "
                       f"your style, your way!",
        "color": 0xF7C5D9,
        "footer": {"text": f"{len(remaining)} flowers left this cycle • "
                           f"{len(flowers)} total"},
    }
    if image_url:
        embed["image"] = {"url": image_url}

    payload = {"embeds": [embed]}
    if ROLE_ID:
        payload["content"] = f"<@&{ROLE_ID}>"
        payload["allowed_mentions"] = {"roles": [ROLE_ID]}

    post_to_webhook(payload)
    print(f"[done] posted '{flower['name']}'. {len(remaining)} left this cycle.")


if __name__ == "__main__":
    main()
