"""Score how well a listing matches the user's search intent (per platform, no cross-app agreement)."""

import re
from typing import Any, Dict, List, Set, Tuple

# Strong mismatch signals for dairy / milk queries
_MILK_BAD_SUBSTRINGS = (
    "almond",
    "soy",
    "oat milk",
    "oat-milk",
    "milkshake",
    "shake mix",
    "chocolate milk",
    "condensed milk",
    "milk powder",
    "milkmaid",
    "khoya",
    "mawa",
    "lactose free",
    "vegan",
    "coconut milk",
)

_FULL_CREAM_HINTS = ("full cream", "whole milk", "full fat", "full-fat")


def score_candidate_vs_query(candidate: Dict[str, Any], query: str, query_tokens: Set[str]) -> float:
    """
    Higher = better match to query for picking one listing per platform.
    Brand is optional; price + query terms matter strongly.
    """
    qlow = (query or "").lower().strip()
    title = (candidate.get("title") or "").lower()
    qlab = (candidate.get("quantityLabel") or "").lower()
    text = f"{title} {qlab}"

    score = 0.0

    for t in query_tokens:
        if len(t) < 2:
            continue
        if t in text:
            score += 1.35

    p = candidate.get("price")
    has_price = isinstance(p, (int, float)) and float(p) > 0
    in_stock = bool(candidate.get("inStock"))
    if has_price and in_stock:
        score += 10.0
    elif has_price:
        score += 8.5

    if candidate.get("quantityLabel"):
        score += 1.1

    if "milk" in qlow:
        if "milk" in title or "milk" in qlab:
            score += 2.8
        for bad in _MILK_BAD_SUBSTRINGS:
            if bad in title:
                score -= 7.0
                break

        if "toned" in qlow:
            if "toned" in title or "toned" in qlab:
                score += 5.0
            for fc in _FULL_CREAM_HINTS:
                if fc in title:
                    score -= 6.0
                    break
        if "double" in qlow and "double" in title:
            score += 3.0
        if "skim" in qlow and ("skim" in title or "skimmed" in title):
            score += 3.0

    if "bread" in qlow and "bread" in title:
        score += 2.2

    if re.search(r"\b(apple|guava|banana|tomato|potato|onion)\b", qlow):
        m = re.search(r"\b(apple|guava|banana|tomato|potato|onion)s?\b", qlow)
        if m and m.group(1) in text:
            score += 2.5

    return score


def pick_best_candidate_for_query(
    candidates: List[Dict[str, Any]],
    query: str,
    query_tokens: Set[str],
) -> Tuple[Dict[str, Any], float]:
    if not candidates:
        return {}, -1e9
    best = candidates[0]
    best_s = score_candidate_vs_query(best, query, query_tokens)
    for c in candidates[1:]:
        s = score_candidate_vs_query(c, query, query_tokens)
        if s > best_s:
            best_s = s
            best = c
        elif s == best_s:
            # Tie-break: prefer priced in-stock, then any price
            def _tier(x: Dict[str, Any]) -> tuple:
                p = x.get("price")
                hp = isinstance(p, (int, float)) and float(p) > 0
                ins = bool(x.get("inStock"))
                return (1 if hp and ins else 0, 1 if hp else 0)

            if _tier(c) > _tier(best):
                best = c
    return best, best_s
