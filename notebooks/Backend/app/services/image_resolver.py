from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, Optional

logger = logging.getLogger("services.image_resolver")


def _strip_json_fence(text: str) -> str:
    t = (text or "").strip()
    if t.startswith("```"):
        t = re.sub(r"^```(?:json)?\s*", "", t, flags=re.IGNORECASE)
        t = re.sub(r"\s*```\s*$", "", t)
    return t.strip()


def _parse_json_block(text: str) -> Optional[Dict[str, Any]]:
    clean = _strip_json_fence(text)
    if not clean:
        return None
    try:
        obj = json.loads(clean)
        return obj if isinstance(obj, dict) else None
    except Exception:
        pass
    m = re.search(r"\{[\s\S]*\}", clean)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except Exception:
        return None


def _looks_like_valid_http_image_url(url: Optional[str]) -> bool:
    if not url or not isinstance(url, str):
        return False
    u = url.strip()
    if not (u.startswith("https://") or u.startswith("http://")):
        return False
    if len(u) < 12:
        return False
    if any(x in u.lower() for x in ("/logo", "/icon", "sprite", "placeholder", "tracking", "pixel")):
        return False
    return True


def _tokenize(s: Optional[str]) -> set[str]:
    if not s:
        return set()
    return {t for t in re.split(r"[^a-z0-9]+", s.lower()) if len(t) >= 3}


def _acceptance_score(
    *,
    canonical_name: Optional[str],
    brand: Optional[str],
    quantity: Optional[str],
    variant: Optional[str],
    matched_title: Optional[str],
    source_page_url: Optional[str],
) -> float:
    wanted = _tokenize(" ".join(x for x in [canonical_name or "", quantity or "", variant or ""] if x))
    matched = _tokenize(" ".join(x for x in [matched_title or "", source_page_url or ""] if x))
    overlap = len(wanted & matched)
    denom = max(len(wanted), 1)
    token_score = overlap / denom

    brand_score = 0.0
    if brand:
        b = brand.lower().strip()
        hay = f"{matched_title or ''} {source_page_url or ''}".lower()
        brand_score = 1.0 if b and b in hay else 0.0
    return min(1.0, 0.65 * token_score + 0.35 * brand_score)


def resolve_image_with_gemini_search_sync(
    *,
    api_key: str,
    model_name: str,
    platform: str,
    raw_query: str,
    canonical_name: Optional[str],
    listing_title: Optional[str],
    brand: Optional[str],
    quantity_label: Optional[str],
    unit: Optional[str],
    variant: Optional[str],
    product_url: Optional[str],
) -> Dict[str, Any]:
    """
    Gemini + Google Search fallback for product image resolution.
    Returns a structured dict with acceptance decision and debug payload.
    """
    if not (api_key or "").strip():
        return {"accepted": False, "reason": "missing_google_api_key"}

    prompt = f"""Find a product image for this grocery listing using Google Search grounding.

Platform: {platform}
User query: {raw_query}
Canonical product: {canonical_name or ""}
Listing title: {listing_title or ""}
Brand: {brand or ""}
Quantity label: {quantity_label or ""}
Unit: {unit or ""}
Variant/type: {variant or ""}
Product URL hint: {product_url or ""}

Rules:
- Prefer exact product match (brand + pack size + variant) for packaged goods.
- For produce/unbranded goods, prioritize product family + variety + approximate quantity.
- Do not return logos/icons/placeholders.
- Return null image_url if confidence is low.

Return JSON only:
{{
  "image_url": "https://...",
  "source_page_url": "https://...",
  "matched_title": "string",
  "confidence": 0.0,
  "reason": "short explanation"
}}
"""
    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)

        tool_payload: Optional[Any] = None
        try:
            # Best effort: enable Google Search grounding when supported by installed SDK/model.
            tool_payload = {"google_search_retrieval": {}}
        except Exception:
            tool_payload = None

        if tool_payload is not None:
            response = model.generate_content(
                [prompt],
                generation_config=genai.types.GenerationConfig(temperature=0.1),
                tools=[tool_payload],
            )
        else:
            response = model.generate_content(
                [prompt],
                generation_config=genai.types.GenerationConfig(temperature=0.1),
            )
        text = getattr(response, "text", "") or ""
    except Exception as exc:
        logger.warning("Gemini image fallback failed: %s", exc)
        return {"accepted": False, "reason": f"gemini_error:{exc}"}

    parsed = _parse_json_block(text)
    if not parsed:
        return {"accepted": False, "reason": "invalid_gemini_json", "raw": text[:1000]}

    image_url = parsed.get("image_url")
    source_page_url = parsed.get("source_page_url")
    matched_title = parsed.get("matched_title")
    reason = (parsed.get("reason") or "").strip() or "gemini_search"
    try:
        gemini_conf = float(parsed.get("confidence") or 0.0)
    except Exception:
        gemini_conf = 0.0

    if not _looks_like_valid_http_image_url(image_url):
        return {
            "accepted": False,
            "reason": "gemini_invalid_image_url",
            "candidate": parsed,
        }

    acceptance = _acceptance_score(
        canonical_name=canonical_name or raw_query,
        brand=brand,
        quantity=quantity_label,
        variant=variant,
        matched_title=matched_title,
        source_page_url=source_page_url,
    )

    branded = bool(brand and brand.strip())
    min_conf = 0.72 if branded else 0.62
    final_conf = min(1.0, (gemini_conf * 0.55) + (acceptance * 0.45))
    accepted = final_conf >= min_conf
    return {
        "accepted": accepted,
        "image_url": image_url,
        "source_page_url": source_page_url,
        "matched_title": matched_title,
        "reason": reason,
        "confidence": round(final_conf, 4),
        "gemini_confidence": round(gemini_conf, 4),
        "acceptance_score": round(acceptance, 4),
        "threshold": min_conf,
        "raw": parsed,
    }
