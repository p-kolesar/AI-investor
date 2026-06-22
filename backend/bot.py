import json
import os
import urllib.request

import anthropic

from places import get_places
from storage import blob_read, blob_write

_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
_CLAUDE_KEY = os.environ.get("CLAUDE_API_KEY", "")
_TG = f"https://api.telegram.org/bot{_TOKEN}"


def _send(chat_id: str, text: str) -> None:
    payload = json.dumps({"chat_id": chat_id, "text": text, "parse_mode": "HTML"}).encode()
    req = urllib.request.Request(
        f"{_TG}/sendMessage",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    urllib.request.urlopen(req)


def _load_property(property_id: str):
    return blob_read("properties", f"{property_id}.json")


def _get_session(chat_id: str):
    return blob_read("sessions", f"{chat_id}.json")


def _save_session(chat_id: str, property_id: str) -> None:
    blob_write("sessions", f"{chat_id}.json", {"propertyId": property_id})


def _build_system(prop: dict) -> str:
    loc = prop.get("location", {})
    wifi = prop.get("wifi", {})
    picks = prop.get("ownerPicks", [])

    places = []
    if loc.get("lat") and loc.get("lng"):
        try:
            places = get_places(loc["lat"], loc["lng"], prop["id"])
        except Exception:
            pass

    picks_text = "\n".join(
        f"- {p['name']}: {p.get('note', '')} {p.get('mapsUrl', '')}" for p in picks
    ) or "none set"

    places_text = "\n".join(
        f"- [{p['type']}] {p['name']} | {p.get('address', '')} | rated {p.get('rating', '?')}/5 | {p['mapsUrl']}"
        for p in places
    ) or "unavailable"

    return f"""You are a helpful local guide for guests at {prop['name']}.

WiFi network: {wifi.get('name', 'not set')}
WiFi password: {wifi.get('password', 'not set')}
Check-in tips: {prop.get('tips', 'none')}

Owner's picks:
{picks_text}

Nearby places (Google):
{places_text}

Answer concisely. Share WiFi details directly when asked. Prefer owner picks over generic nearby results. Never invent information not listed above."""


def handle_update(body: dict) -> None:
    message = body.get("message", {})
    chat_id = str(message.get("chat", {}).get("id", ""))
    text = (message.get("text") or "").strip()
    if not chat_id or not text:
        return

    if text.startswith("/start"):
        parts = text.split(maxsplit=1)
        property_id = parts[1].strip() if len(parts) > 1 else None
        if property_id:
            prop = _load_property(property_id)
            if prop:
                _save_session(chat_id, property_id)
                _send(chat_id, f"Welcome to <b>{prop['name']}</b>! 🏨\nAsk me anything — WiFi, parking, restaurants, local tips.")
            else:
                _send(chat_id, "Property not found. Please check the link with your host.")
        else:
            _send(chat_id, "Please tap the link your host sent you to get started.")
        return

    session = _get_session(chat_id)
    if not session:
        _send(chat_id, "Please use the link your host sent you to get started. 🔗")
        return

    prop = _load_property(session["propertyId"])
    if not prop:
        _send(chat_id, "Property data not found. Please contact your host.")
        return

    client = anthropic.Anthropic(api_key=_CLAUDE_KEY)
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=400,
        system=_build_system(prop),
        messages=[{"role": "user", "content": text}],
    )
    _send(chat_id, response.content[0].text)
