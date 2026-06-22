import hashlib
import json
import logging
import uuid

import azure.functions as func

logger = logging.getLogger(__name__)

from bot import handle_update
from places import get_places
from storage import blob_read, blob_write, blob_write_bytes, blob_read_bytes

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _ok(data, status: int = 200) -> func.HttpResponse:
    return func.HttpResponse(json.dumps(data), mimetype="application/json", status_code=status)


def _err(msg: str, status: int = 400) -> func.HttpResponse:
    return func.HttpResponse(json.dumps({"error": msg}), mimetype="application/json", status_code=status)


# ---- Hello world ----

@app.route(route="hello", methods=["GET"])
def hello(req: func.HttpRequest) -> func.HttpResponse:
    name = req.params.get("name", "World")
    return _ok({"message": f"Hello, {name}!"})


# ---- Health ----

@app.route(route="health", methods=["GET"])
def health(req: func.HttpRequest) -> func.HttpResponse:
    return _ok({"status": "ok"})


# ---- Property (public read) ----

@app.route(route="property/{id}", methods=["GET"])
def get_property(req: func.HttpRequest) -> func.HttpResponse:
    prop = blob_read("properties", f"{req.route_params['id']}.json")
    if not prop:
        return _err("Property not found", 404)
    return _ok({k: v for k, v in prop.items() if k != "adminTokenHash"})


# ---- Places (public read, 24 h cached) ----

@app.route(route="property/{id}/places", methods=["GET"])
def get_property_places(req: func.HttpRequest) -> func.HttpResponse:
    prop = blob_read("properties", f"{req.route_params['id']}.json")
    if not prop:
        return _err("Property not found", 404)
    loc = prop.get("location", {})
    if not loc.get("lat") or not loc.get("lng"):
        return _ok([])
    try:
        return _ok(get_places(loc["lat"], loc["lng"], prop["id"]))
    except Exception as e:
        return _err(str(e), 500)


# ---- Logo (public read, served via Function App) ----

@app.route(route="logos/{id}", methods=["GET"])
def get_logo(req: func.HttpRequest) -> func.HttpResponse:
    property_id = req.route_params["id"]
    for ext, mime in [("png", "image/png"), ("jpg", "image/jpeg")]:
        data = blob_read_bytes("logos", f"{property_id}.{ext}")
        if data is not None:
            return func.HttpResponse(data, mimetype=mime, status_code=200)
    return _err("Logo not found", 404)


# ---- Admin: create / update property ----

@app.route(route="admin-property", methods=["GET"])
def admin_property(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("admin-property called: id=%s", req.params.get("id", "<new>"))
    p = req.params
    property_id = p.get("id")
    admin_token = p.get("adminToken", "")

    if property_id:
        prop = blob_read("properties", f"{property_id}.json")
        if not prop:
            return _err("Property not found", 404)
        if prop.get("adminTokenHash") != _hash(admin_token):
            return _err("Invalid admin token", 403)
    else:
        if not admin_token:
            return _err("adminToken required when creating a property", 400)
        property_id = str(uuid.uuid4())[:8]
        prop = {"id": property_id, "adminTokenHash": _hash(admin_token)}

    if p.get("name"):
        prop["name"] = p["name"]
    if p.get("address") or p.get("lat"):
        prop["location"] = {
            "address": p.get("address", prop.get("location", {}).get("address", "")),
            "lat": float(p["lat"]) if p.get("lat") else prop.get("location", {}).get("lat"),
            "lng": float(p["lng"]) if p.get("lng") else prop.get("location", {}).get("lng"),
        }
    if p.get("wifiName") or p.get("wifiPassword"):
        prop["wifi"] = {
            "name": p.get("wifiName", prop.get("wifi", {}).get("name", "")),
            "password": p.get("wifiPassword", prop.get("wifi", {}).get("password", "")),
        }
    if p.get("accentColor"):
        prop.setdefault("branding", {})["accentColor"] = p["accentColor"]
    if p.get("tips") is not None:
        prop["tips"] = p["tips"]
    if p.get("ownerPicks"):
        try:
            prop["ownerPicks"] = json.loads(p["ownerPicks"])
        except json.JSONDecodeError:
            return _err("ownerPicks must be a JSON array", 400)

    blob_write("properties", f"{property_id}.json", prop)
    return _ok({"id": property_id, "saved": True})


# ---- Admin: logo upload ----

@app.route(route="admin-upload/{id}", methods=["POST"])
def admin_upload(req: func.HttpRequest) -> func.HttpResponse:
    logger.info("admin-upload called: id=%s", req.route_params.get("id"))
    property_id = req.route_params["id"]
    admin_token = req.params.get("adminToken", "")
    prop = blob_read("properties", f"{property_id}.json")
    if not prop:
        return _err("Property not found", 404)
    if prop.get("adminTokenHash") != _hash(admin_token):
        return _err("Invalid admin token", 403)

    content_type = req.headers.get("Content-Type", "image/png")
    ext = "jpg" if "jpeg" in content_type else "png"
    blob_write_bytes("logos", f"{property_id}.{ext}", req.get_body(), content_type)

    # Logo is served via /api/logos/{id} — no public blob URL needed
    prop.setdefault("branding", {})["hasLogo"] = True
    blob_write("properties", f"{property_id}.json", prop)
    return _ok({"logoPath": f"/logos/{property_id}"})


# ---- Telegram webhook ----

@app.route(route="telegram/webhook", methods=["POST"])
def telegram_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        handle_update(req.get_json())
    except Exception:
        pass  # always 200 — Telegram retries on non-200
    return func.HttpResponse(status_code=200)
