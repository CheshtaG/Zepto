import re
from typing import Any, Dict, Optional

from app.services.product_matching.normalization import (
    merge_quantity_label,
    normalize_text_key,
    quantity_from_candidate_fields,
)

_STOP = {"pack", "combo", "x", "ml", "l", "g", "kg", "mg", "pcs", "piece", "of", "the", "and"}

_VARIANT_KEYS = (
    "toned",
    "full",
    "whole",
    "skim",
    "low",
    "fat",
    "double",
    "single",
    "brown",
    "white",
    "multigrain",
    "organic",
    "a2",
)

_CATEGORY_KEYS = (
    "milk",
    "bread",
    "water",
    "juice",
    "curd",
    "yogurt",
    "butter",
    "cheese",
    "egg",
    "rice",
    "atta",
    "oil",
)


def extract_brand_from_title(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    s = re.sub(r"\s+", " ", title).strip()
    if not s:
        return None
    parts = [p for p in re.split(r"[\s,/()-]+", s) if p]
    if not parts:
        return None
    brand_tokens: list[str] = []
    for t in parts[:5]:
        tl = t.lower()
        if tl in _STOP or tl in _VARIANT_KEYS or re.search(r"\d", t):
            if brand_tokens:
                break
            continue
        brand_tokens.append(t)
        if len(brand_tokens) >= 2:
            break
    if not brand_tokens:
        return parts[0][:48]
    return " ".join(brand_tokens)[:48]


def extract_variant(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    low = title.lower()
    hits = [k for k in _VARIANT_KEYS if k in low.split() or f" {k} " in f" {low} "]
    if not hits:
        return None
    return ",".join(sorted(set(hits)))[:80]


def extract_category_hint(title: Optional[str]) -> Optional[str]:
    if not title:
        return None
    low = title.lower()
    for k in _CATEGORY_KEYS:
        if k in low:
            return k
    return None


def enrich_candidate(raw: Dict[str, Any]) -> Dict[str, Any]:
    c = dict(raw)
    title = c.get("title") if isinstance(c.get("title"), str) else None
    ql = c.get("quantityLabel") if isinstance(c.get("quantityLabel"), str) else None
    merged_ql = merge_quantity_label(title, ql)
    if merged_ql:
        c["quantityLabel"] = merged_ql
    if not c.get("brand"):
        c["brand"] = extract_brand_from_title(title)
    nq, nu = quantity_from_candidate_fields(title, merged_ql or ql)
    c["normalizedQuantity"] = nq
    c["normalizedUnit"] = nu
    if not c.get("variant"):
        c["variant"] = extract_variant(title)
    if not c.get("category"):
        c["category"] = extract_category_hint(title)
    return c


def brands_compatible(a: Optional[str], b: Optional[str]) -> Optional[bool]:
    """True = match, False = mismatch, None = unknown."""
    if not a or not b:
        return None
    na, nb = normalize_text_key(a), normalize_text_key(b)
    if na == nb:
        return True
    if na in nb or nb in na:
        return True
    return False
