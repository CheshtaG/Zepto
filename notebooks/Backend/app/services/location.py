import json
import ipaddress
import urllib.parse
import urllib.request
from typing import Optional, Dict, Any


def _safe_get(url: str, headers: Optional[Dict[str, str]] = None, timeout: int = 6) -> Optional[Dict[str, Any]]:
    req = urllib.request.Request(url, headers=headers or {})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw)
    except Exception:
        return None


def _is_public_ip(ip: str) -> bool:
    try:
        parsed = ipaddress.ip_address(ip)
        return not (parsed.is_private or parsed.is_loopback or parsed.is_reserved or parsed.is_link_local)
    except Exception:
        return False


def extract_client_ip(headers: Dict[str, str], request_client_host: Optional[str]) -> Optional[str]:
    forwarded_for = headers.get("x-forwarded-for")
    if forwarded_for:
        first = forwarded_for.split(",")[0].strip()
        if first:
            return first

    for key in ("cf-connecting-ip", "x-real-ip"):
        val = headers.get(key)
        if val:
            return val.strip()

    return request_client_host


def reverse_geocode_lat_lng(lat: float, lng: float) -> Optional[Dict[str, Any]]:
    query = urllib.parse.urlencode({"format": "jsonv2", "lat": lat, "lon": lng})
    url = f"https://nominatim.openstreetmap.org/reverse?{query}"
    payload = _safe_get(url, headers={"User-Agent": "zepto-compare-app/1.0"})
    if not payload:
        return None

    address = payload.get("address", {}) if isinstance(payload, dict) else {}
    city = (
        address.get("city")
        or address.get("town")
        or address.get("village")
        or address.get("suburb")
        or address.get("state_district")
        or address.get("state")
    )
    pincode = address.get("postcode")

    label_parts = [p for p in (city, pincode) if p]
    return {
        "city": city,
        "pincode": pincode,
        "label": ", ".join(label_parts) if label_parts else payload.get("display_name"),
        "source": "geolocation",
    }


def lookup_location_by_ip(ip: Optional[str]) -> Optional[Dict[str, Any]]:
    if not ip or not _is_public_ip(ip):
        return None

    url = f"https://ipapi.co/{urllib.parse.quote(ip)}/json/"
    payload = _safe_get(url)
    if not payload:
        return None

    city = payload.get("city")
    pincode = payload.get("postal")
    latitude = payload.get("latitude")
    longitude = payload.get("longitude")
    label_parts = [p for p in (city, pincode) if p]
    return {
        "city": city,
        "pincode": pincode,
        "lat": latitude,
        "lng": longitude,
        "label": ", ".join(label_parts) if label_parts else city or ip,
        "source": "ip",
    }

