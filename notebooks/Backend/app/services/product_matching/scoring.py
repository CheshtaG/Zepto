from typing import Any, Dict, Optional, Set

from app.services.product_matching.normalization import normalize_text_key
from app.services.product_matching.parser import brands_compatible


def _tokens(s: Optional[str]) -> set[str]:
    if not s:
        return set()
    import re

    return set(re.findall(r"[a-z0-9]+", s.lower()))


def title_similarity(a: Optional[str], b: Optional[str]) -> float:
    if not a or not b:
        return 0.0
    A, B = _tokens(a), _tokens(b)
    if not A or not B:
        return 0.0
    inter = len(A & B)
    union = len(A | B)
    return inter / union if union else 0.0


def score_pair(a: Dict[str, Any], b: Dict[str, Any]) -> float:
    """
    Higher = more likely same SKU. Used pairwise between platform candidates.
    """
    score = 0.0

    ba = a.get("brand") if isinstance(a.get("brand"), str) else None
    bb = b.get("brand") if isinstance(b.get("brand"), str) else None
    compat = brands_compatible(ba, bb)
    if compat is True:
        score += 4.0
    elif compat is False:
        score -= 4.0

    nqa = a.get("normalizedQuantity")
    nua = a.get("normalizedUnit")
    nqb = b.get("normalizedQuantity")
    nub = b.get("normalizedUnit")
    if (
        isinstance(nqa, (int, float))
        and isinstance(nqb, (int, float))
        and nua
        and nub
        and isinstance(nua, str)
        and isinstance(nub, str)
    ):
        if nua == nub:
            if abs(float(nqa) - float(nqb)) < 1e-6:
                score += 4.0
            else:
                score -= 3.0
        else:
            score -= 2.0
    else:
        qla = a.get("quantityLabel") if isinstance(a.get("quantityLabel"), str) else None
        qlb = b.get("quantityLabel") if isinstance(b.get("quantityLabel"), str) else None
        if qla and qlb:
            na, nb = normalize_text_key(qla), normalize_text_key(qlb)
            if na == nb:
                score += 3.0
            elif na in nb or nb in na:
                score += 1.5
            else:
                score -= 2.0

    ca = a.get("category") if isinstance(a.get("category"), str) else None
    cb = b.get("category") if isinstance(b.get("category"), str) else None
    if ca and cb:
        if ca == cb:
            score += 1.5
        else:
            score -= 0.5

    va = a.get("variant") if isinstance(a.get("variant"), str) else None
    vb = b.get("variant") if isinstance(b.get("variant"), str) else None
    if va and vb:
        if va == vb:
            score += 1.5
        else:
            score -= 1.0

    ta = a.get("title") if isinstance(a.get("title"), str) else None
    tb = b.get("title") if isinstance(b.get("title"), str) else None
    ts = title_similarity(ta, tb)
    score += min(2.0, ts * 2.0)

    return score


def _query_overlap_bonus(title: Optional[str], query_tokens: Set[str]) -> float:
    if not title or not query_tokens:
        return 0.0
    low = title.lower()
    n = sum(1 for t in query_tokens if t in low)
    return min(1.8, n * 0.45)


def score_pair_loose(a: Dict[str, Any], b: Dict[str, Any], query_tokens: Set[str]) -> float:
    """
    Softer penalties for brand/qty mismatch; rewards listing titles that contain query tokens.
    Used for produce and broad grocery intents when strict SKU match is unrealistic.
    """
    score = 0.0

    ba = a.get("brand") if isinstance(a.get("brand"), str) else None
    bb = b.get("brand") if isinstance(b.get("brand"), str) else None
    compat = brands_compatible(ba, bb)
    if compat is True:
        score += 4.0
    elif compat is False:
        score -= 1.0

    nqa = a.get("normalizedQuantity")
    nua = a.get("normalizedUnit")
    nqb = b.get("normalizedQuantity")
    nub = b.get("normalizedUnit")
    if (
        isinstance(nqa, (int, float))
        and isinstance(nqb, (int, float))
        and nua
        and nub
        and isinstance(nua, str)
        and isinstance(nub, str)
    ):
        if nua == nub:
            if abs(float(nqa) - float(nqb)) < 1e-6:
                score += 3.5
            else:
                score -= 1.0
        else:
            score -= 0.5
    else:
        qla = a.get("quantityLabel") if isinstance(a.get("quantityLabel"), str) else None
        qlb = b.get("quantityLabel") if isinstance(b.get("quantityLabel"), str) else None
        if qla and qlb:
            na, nb = normalize_text_key(qla), normalize_text_key(qlb)
            if na == nb:
                score += 2.5
            elif na in nb or nb in na:
                score += 1.2
            else:
                score -= 0.8

    ca = a.get("category") if isinstance(a.get("category"), str) else None
    cb = b.get("category") if isinstance(b.get("category"), str) else None
    if ca and cb:
        if ca == cb:
            score += 1.5
        else:
            score -= 0.25

    va = a.get("variant") if isinstance(a.get("variant"), str) else None
    vb = b.get("variant") if isinstance(b.get("variant"), str) else None
    if va and vb:
        if va == vb:
            score += 1.2
        else:
            score -= 0.4

    ta = a.get("title") if isinstance(a.get("title"), str) else None
    tb = b.get("title") if isinstance(b.get("title"), str) else None
    ts = title_similarity(ta, tb)
    score += min(2.0, ts * 2.0)
    score += 0.35 * (_query_overlap_bonus(ta, query_tokens) + _query_overlap_bonus(tb, query_tokens))

    return score
