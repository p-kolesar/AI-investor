import hashlib
import json
import os
import uuid

import azure.functions as func

from bot import handle_update
from places import get_places
from storage import blob_read, blob_write, blob_write_bytes

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)

_STORAGE_ACCOUNT = os.environ.get("STORAGE_ACCOUNT_NAME", "")


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


# ---- Admin: create / update property ----

@app.route(route="admin/property", methods=["GET"])
def admin_property(req: func.HttpRequest) -> func.HttpResponse:
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

@app.route(route="admin/upload/{id}", methods=["POST"])
def admin_upload(req: func.HttpRequest) -> func.HttpResponse:
    property_id = req.route_params["id"]
    admin_token = req.params.get("adminToken", "")
    prop = blob_read("properties", f"{property_id}.json")
    if not prop:
        return _err("Property not found", 404)
    if prop.get("adminTokenHash") != _hash(admin_token):
        return _err("Invalid admin token", 403)

    content_type = req.headers.get("Content-Type", "image/png")
    ext = "jpg" if "jpeg" in content_type else "png"
    blob_name = f"{property_id}.{ext}"
    blob_write_bytes("logos", blob_name, req.get_body(), content_type)

    logo_url = f"https://{_STORAGE_ACCOUNT}.blob.core.windows.net/logos/{blob_name}"
    prop.setdefault("branding", {})["logoUrl"] = logo_url
    blob_write("properties", f"{property_id}.json", prop)
    return _ok({"logoUrl": logo_url})


# ---- Telegram webhook ----

@app.route(route="telegram/webhook", methods=["POST"])
def telegram_webhook(req: func.HttpRequest) -> func.HttpResponse:
    try:
        handle_update(req.get_json())
    except Exception:
        pass  # always 200 — Telegram retries on non-200
    return func.HttpResponse(status_code=200)
