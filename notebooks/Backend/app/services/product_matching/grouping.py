import logging
from typing import Any, Callable, Dict, List, Optional, Tuple

from models import Platform, ProductInfo

from app.schemas.jobs import JobItemMatch, JobResultItem
from app.services.product_matching.intent import normalize_query_title, query_tokens
from app.services.product_matching.parser import enrich_candidate, extract_brand_from_title
from app.services.product_matching.query_relevance import pick_best_candidate_for_query
from app.services.product_matching.scoring import score_pair, score_pair_loose

logger = logging.getLogger("app.services.product_matching")

HIGH_CONFIDENCE_THRESHOLD = 4.5
_MAX_CANDIDATES = 8

SUBTITLE_GENERIC = "Closest available matches across apps"
SUBTITLE_WEAK = "Limited comparable results found"

ComparisonMode = str  # "exact" | "generic_comparable" | "weak_partial"


def _synthetic_candidate(info: ProductInfo) -> Dict[str, Any]:
    title = (info.listing_title or "").strip() or None
    brand = extract_brand_from_title(title) if title else None
    return enrich_candidate(
        {
            "id": f"{info.platform.value}-primary",
            "title": title,
            "rawTitle": title,
            "brand": brand,
            "quantityLabel": info.quantity_label,
            "variant": None,
            "category": None,
            "price": float(info.price) if info.price is not None else None,
            "inStock": bool(info.availability and info.price is not None),
            "imageUrl": info.image_url,
            "productUrl": info.product_url,
            "platform": info.platform.value,
        }
    )


def _candidates_for_info(info: ProductInfo) -> List[Dict[str, Any]]:
    """
    Merge DOM card candidates with the primary ProductInfo row when the scraper found a price
    there but per-card extraction missed it — prevents all-null triples in the matcher.
    """
    out: List[Dict[str, Any]] = []
    syn = _synthetic_candidate(info)

    def _title_key(c: Dict[str, Any]) -> str:
        return ((c.get("title") or "").strip().lower()[:72])

    def _merge_or_append(c: Dict[str, Any]) -> None:
        k = _title_key(c)
        if k:
            for x in out:
                if _title_key(x) == k:
                    if (c.get("price") is not None) and x.get("price") is None:
                        x["price"] = c.get("price")
                        x["inStock"] = c.get("inStock")
                        if not x.get("imageUrl") and c.get("imageUrl"):
                            x["imageUrl"] = c.get("imageUrl")
                    return
        out.append(c)

    if info.candidate_listings:
        if syn.get("price") is not None:
            _merge_or_append(syn)
        for raw in info.candidate_listings[:_MAX_CANDIDATES]:
            if isinstance(raw, dict):
                c = dict(raw)
                c.setdefault("platform", info.platform.value)
                _merge_or_append(enrich_candidate(c))
        if not out:
            _merge_or_append(syn)
    else:
        _merge_or_append(syn)

    return out[:_MAX_CANDIDATES]


def _pick_info(infos: List[ProductInfo], plat: Platform) -> ProductInfo:
    for p in infos:
        if p.platform == plat:
            return p
    return ProductInfo(platform=plat, price=None, availability=False, error="missing")


def _merge_gemini_quantity(info: ProductInfo, candidate_title: Optional[str]) -> Dict[str, Any]:
    lt = (info.listing_title or "").strip().lower()
    ct = (candidate_title or "").strip().lower()
    if lt and ct and (lt == ct or lt in ct or ct in lt):
        return {
            "quantity_base_value": info.quantity_base_value,
            "quantity_base_unit": info.quantity_base_unit,
            "price_per_base_unit": info.price_per_base_unit,
            "quantity_comparable": info.quantity_comparable,
            "quantity_comparison_note": info.quantity_comparison_note,
        }
    return {}


def _match_to_job_item(info: ProductInfo, c: Dict[str, Any]) -> JobItemMatch:
    extra = _merge_gemini_quantity(info, c.get("title") if isinstance(c.get("title"), str) else None)
    price = c.get("price")
    if isinstance(price, (int, float)):
        price_f: Optional[float] = float(price)
    else:
        price_f = None
    in_stock = bool(c.get("inStock")) and price_f is not None
    img = c.get("imageUrl") if isinstance(c.get("imageUrl"), str) else None
    title = c.get("title") if isinstance(c.get("title"), str) else None
    ql = c.get("quantityLabel") if isinstance(c.get("quantityLabel"), str) else None
    return JobItemMatch(
        platform=info.platform.value,
        price=price_f,
        in_stock=in_stock,
        image_url=img,
        screenshot_url=img,
        listing_title=title,
        quantity_label=ql,
        quantity_base_value=extra.get("quantity_base_value"),
        quantity_base_unit=extra.get("quantity_base_unit"),
        price_per_base_unit=extra.get("price_per_base_unit"),
        quantity_comparable=extra.get("quantity_comparable"),
        quantity_comparison_note=extra.get("quantity_comparison_note"),
    )


def _exact_subtitle(ci: Dict[str, Any], cb: Dict[str, Any], cz: Dict[str, Any]) -> str:
    ql = None
    brand = None
    for c in (ci, cb, cz):
        q = c.get("quantityLabel") if isinstance(c.get("quantityLabel"), str) else None
        b = c.get("brand") if isinstance(c.get("brand"), str) else None
        if q:
            ql = q
        if b:
            brand = b
        if ql and brand:
            break
    parts = [p for p in [ql, brand] if p]
    if len(parts) >= 2:
        return " • ".join(parts)
    if len(parts) == 1:
        return parts[0]
    return SUBTITLE_GENERIC


def _best_triple(
    ci: List[Dict[str, Any]],
    cb: List[Dict[str, Any]],
    cz: List[Dict[str, Any]],
    pair_score: Callable[[Dict[str, Any], Dict[str, Any]], float],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], float]:
    best_i, best_b, best_z = ci[0], cb[0], cz[0]
    best_score = -1e9
    for i in ci:
        for b in cb:
            for z in cz:
                s = (pair_score(i, b) + pair_score(i, z) + pair_score(b, z)) / 3.0
                if s > best_score:
                    best_score = s
                    best_i, best_b, best_z = i, b, z
    return best_i, best_b, best_z, best_score


def _priced_platform_count(bi: Dict[str, Any], bb: Dict[str, Any], bz: Dict[str, Any]) -> int:
    n = 0
    for c in (bi, bb, bz):
        p = c.get("price")
        ok = bool(c.get("inStock")) and isinstance(p, (int, float))
        if ok:
            n += 1
    return n


def _loose_triple_conf(
    bi: Dict[str, Any], bb: Dict[str, Any], bz: Dict[str, Any], qt: set
) -> float:
    return (
        score_pair_loose(bi, bb, qt) + score_pair_loose(bi, bz, qt) + score_pair_loose(bb, bz, qt)
    ) / 3.0


def _log_selection(
    query: str,
    platform_label: str,
    candidates: List[Dict[str, Any]],
    chosen: Dict[str, Any],
) -> None:
    logger.info(
        "[product_matching] query=%r platform=%s pool_size=%s -> selected title=%r price=%s "
        "qty=%r in_stock=%s",
        query,
        platform_label,
        len(candidates),
        (chosen.get("title") or "")[:140] if chosen else None,
        chosen.get("price") if chosen else None,
        chosen.get("quantityLabel") if chosen else None,
        chosen.get("inStock") if chosen else None,
    )
    for idx, c in enumerate(candidates[:10]):
        logger.debug(
            "[product_matching]   candidate[%s] title=%r price=%s qty=%r in_stock=%s",
            idx,
            (c.get("title") or "")[:140],
            c.get("price"),
            c.get("quantityLabel"),
            c.get("inStock"),
        )


def _pick_per_platform(
    query: str,
    qt: set,
    ci: List[Dict[str, Any]],
    cb: List[Dict[str, Any]],
    cz: List[Dict[str, Any]],
) -> Tuple[Dict[str, Any], Dict[str, Any], Dict[str, Any], float]:
    bi, si = pick_best_candidate_for_query(ci, query, qt)
    bb, sb = pick_best_candidate_for_query(cb, query, qt)
    bz, sz = pick_best_candidate_for_query(cz, query, qt)
    conf = _loose_triple_conf(bi, bb, bz, qt)
    return bi, bb, bz, conf


def build_job_row(query: str, infos: List[ProductInfo]) -> JobResultItem:
    """
    One row per user query: query-normalized title, mode-driven subtitle, best-effort matches.

    Generic / low-confidence paths use **per-platform** query relevance so we do not pick a
    joint triple of three unpriced listings just because their titles are mutually similar.
    """
    inst = _pick_info(infos, Platform.INSTAMART)
    blink = _pick_info(infos, Platform.BLINKIT)
    zepto = _pick_info(infos, Platform.ZEPTO)

    ci, cb, cz = _candidates_for_info(inst), _candidates_for_info(blink), _candidates_for_info(zepto)
    qt = query_tokens(query)

    bi_s, bb_s, bz_s, conf_s = _best_triple(ci, cb, cz, score_pair)

    use_strict = conf_s >= HIGH_CONFIDENCE_THRESHOLD

    if use_strict:
        bi, bb, bz = bi_s, bb_s, bz_s
        conf = conf_s
        mode: ComparisonMode = "exact"
        if _priced_platform_count(bi, bb, bz) == 0:
            bi, bb, bz, conf = _pick_per_platform(query, qt, ci, cb, cz)
            mode = "generic_comparable"
    else:
        bi, bb, bz, conf = _pick_per_platform(query, qt, ci, cb, cz)
        mode = "generic_comparable"

    _log_selection(query, "instamart", ci, bi)
    _log_selection(query, "blinkit", cb, bb)
    _log_selection(query, "zepto", cz, bz)

    priced_n = _priced_platform_count(bi, bb, bz)
    if priced_n < 2:
        mode = "weak_partial"

    canon_title = normalize_query_title(query)
    if mode == "exact":
        canon_sub = _exact_subtitle(bi, bb, bz)
    elif mode == "generic_comparable":
        canon_sub = SUBTITLE_GENERIC
    else:
        canon_sub = SUBTITLE_WEAK

    matches = [
        _match_to_job_item(inst, bi),
        _match_to_job_item(blink, bb),
        _match_to_job_item(zepto, bz),
    ]

    high = mode != "weak_partial"

    return JobResultItem(
        query=query,
        matches=matches,
        canonical_title=canon_title,
        canonical_subtitle=canon_sub,
        match_confidence=round(conf, 3),
        high_confidence=high,
        comparison_mode=mode,
    )
