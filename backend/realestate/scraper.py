"""Real-estate scraper helpers for the /scrape-realestate route.

Captures structured FACTS only (price, area, rooms, address) from
nehnutelnosti.sk list pages — not the listing description prose, which is the
agencies' copyright. The page-fetch loop and HTTP budget live in
function_app.py; this module is the parsing + storage library it calls.

Storage config (any one of):
  DATAIN_STORAGE                    -> a full storage connection string, OR
  AzureWebJobsStorage               -> reused if it's a connection string, OR
  AzureWebJobsStorage__accountName  -> managed-identity path (Flex default)
"""

import csv
import io
import os
import re
from urllib.parse import urljoin, urlparse
from urllib import robotparser

from bs4 import BeautifulSoup
from azure.storage.blob import BlobServiceClient

UA = "workshop-realestate-probe/0.1 (educational; contact: you@example.com)"
CONTAINER = "datain"
BASE = "https://www.nehnutelnosti.sk"

RE_PRICE  = re.compile(r"(\d[\d\s ]{2,})\s*€(?!\s*/?\s*m)")
RE_PPM2   = re.compile(r"([\d\s ]+[,.]?\d*)\s*€\s*/\s*m²")
RE_AREA   = re.compile(r"([\d]+(?:[.,]\d+)?)\s*m²")
RE_ROOMS  = re.compile(r"(\d+)\s*izbov")
RE_OKRES  = re.compile(r".*okres\s+[^\n]+", re.IGNORECASE)
RE_DETAIL = re.compile(r"^/detail/([^/]+)/")


def _num(s):
    if not s:
        return None
    s = s.replace(" ", "").replace(" ", "").replace(",", ".")
    if s.count(".") > 1:                       # "1.234.56" -> "1234.56"
        head, _, tail = s.rpartition(".")
        s = head.replace(".", "") + "." + tail
    try:
        return float(s)
    except ValueError:
        return None


def _robots_allows(url: str) -> bool:
    p = urlparse(url)
    rp = robotparser.RobotFileParser()
    try:
        rp.set_url(f"{p.scheme}://{p.netloc}/robots.txt")
        rp.read()
        return rp.can_fetch(UA, url)
    except Exception:
        return True  # if robots is unreadable, proceed cautiously (low volume)


def _parse(html: str, base_url: str):
    soup = BeautifulSoup(html, "lxml")
    out, seen = [], set()
    for a in soup.find_all("a", href=True):
        m = RE_DETAIL.match(a["href"])
        if not m or m.group(1) in seen:
            continue
        node, text = a, ""
        for _ in range(4):
            node = node.parent
            if node is None:
                break
            text = node.get_text("\n", strip=True)
            if "€" in text and "m²" in text:
                break
        if "€" not in text:
            continue
        seen.add(m.group(1))
        price, ppm2 = RE_PRICE.search(text), RE_PPM2.search(text)
        area, rooms, addr = RE_AREA.search(text), RE_ROOMS.search(text), RE_OKRES.search(text)
        out.append({
            "detail_id": m.group(1),
            "detail_url": urljoin(base_url, a["href"]),
            "title": (a.get("title") or a.get_text(" ", strip=True)[:120]) or None,
            "address": addr.group(0).strip() if addr else None,
            "rooms": int(rooms.group(1)) if rooms else None,
            "area_m2": _num(area.group(1)) if area else None,
            "price_eur": _num(price.group(1)) if price else None,
            "price_per_m2": _num(ppm2.group(1)) if ppm2 else None,
            "price_on_request": "dohodou" in text.lower(),
        })
    return out


def _blob_service() -> BlobServiceClient:
    conn = os.environ.get("DATAIN_STORAGE")
    if conn:
        return BlobServiceClient.from_connection_string(conn)
    awjs = os.environ.get("AzureWebJobsStorage", "")
    if "AccountKey=" in awjs or "DefaultEndpointsProtocol=" in awjs:
        return BlobServiceClient.from_connection_string(awjs)
    # managed-identity path (typical on Flex Consumption)
    acct = os.environ.get("AzureWebJobsStorage__accountName") or os.environ.get("DATAIN_ACCOUNT_NAME")
    uri = os.environ.get("AzureWebJobsStorage__blobServiceUri") or (
        f"https://{acct}.blob.core.windows.net" if acct else None)
    if not uri:
        raise RuntimeError("No storage config: set DATAIN_STORAGE or AzureWebJobsStorage__accountName.")
    from azure.identity import DefaultAzureCredential
    return BlobServiceClient(account_url=uri, credential=DefaultAzureCredential())


def _write_csv(rows, ts) -> str:
    cols = ["scraped_at", "locality", "deal", "detail_id", "title", "address",
            "rooms", "area_m2", "price_eur", "price_per_m2", "price_on_request", "detail_url"]
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    w.writerows(rows)
    name = f"nehnutelnosti/{ts.replace(':', '').replace('-', '')}.csv"
    svc = _blob_service()
    cc = svc.get_container_client(CONTAINER)
    try:
        cc.create_container()
    except Exception:
        pass  # already exists
    cc.upload_blob(name=name, data=buf.getvalue().encode("utf-8"), overwrite=True)
    return name


def _coverage(rows):
    n = len(rows) or 1
    def pct(k):
        return round(sum(1 for r in rows if r.get(k) is not None) / n, 2)
    return {"rows": len(rows), "price_eur": pct("price_eur"),
            "area_m2": pct("area_m2"), "price_per_m2": pct("price_per_m2"),
            "address": pct("address")}
