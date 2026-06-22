import json
import os
import time
import urllib.parse
import urllib.request

from storage import blob_read, blob_write

_API_KEY = os.environ.get("GOOGLE_PLACES_API_KEY", "")
_TTL = 86400  # 24 h

_TYPES = ["parking", "restaurant", "cafe", "tourist_attraction", "supermarket"]


def get_places(lat: float, lng: float, property_id: str) -> list:
    cached = blob_read("places-cache", f"{property_id}.json")
    if cached and time.time() - cached.get("ts", 0) < _TTL:
        return cached["places"]

    places = []
    for ptype in _TYPES:
        params = urllib.parse.urlencode({
            "location": f"{lat},{lng}",
            "radius": 1000,
            "type": ptype,
            "key": _API_KEY,
        })
        url = f"https://maps.googleapis.com/maps/api/place/nearbysearch/json?{params}"
        with urllib.request.urlopen(url) as resp:
            results = json.loads(resp.read()).get("results", [])
        for p in results[:3]:
            places.append({
                "name": p["name"],
                "type": ptype,
                "rating": p.get("rating"),
                "address": p.get("vicinity", ""),
                "mapsUrl": f"https://www.google.com/maps/search/?api=1&query={urllib.parse.quote(p['name'])}",
            })

    blob_write("places-cache", f"{property_id}.json", {"ts": time.time(), "places": places})
    return places
