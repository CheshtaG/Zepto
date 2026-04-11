import re
from typing import Optional, Tuple

_LITRE = re.compile(
    r"(\d+(?:\.\d+)?)\s*(?:l|L|litre|litres|liter|liters)\b",
    re.IGNORECASE,
)
_ML = re.compile(r"(\d+(?:\.\d+)?)\s*(?:ml|mL|ML)\b", re.IGNORECASE)
_G = re.compile(r"(\d+(?:\.\d+)?)\s*(?:g|G|gm|gram|grams)\b", re.IGNORECASE)
_KG = re.compile(r"(\d+(?:\.\d+)?)\s*(?:kg|KG|kilo|kilogram)\b", re.IGNORECASE)
_MG = re.compile(r"(\d+(?:\.\d+)?)\s*(?:mg|MG)\b", re.IGNORECASE)
_PACK = re.compile(
    r"(?:pack\s*of|pk\s*of|pack)\s*(\d+)\b|\b(\d+)\s*(?:pcs?|pieces?|pk|units?)\b",
    re.IGNORECASE,
)
_MULT = re.compile(
    r"\b(\d+)\s*[x×]\s*(\d+(?:\.\d+)?)\s*(ml|l|g|kg|mg)\b",
    re.IGNORECASE,
)


_SNIPPET_PATTERNS = [
    re.compile(r"\b\d+\s?x\s?\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg)\b", re.IGNORECASE),
    re.compile(r"\b\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg)\b", re.IGNORECASE),
    re.compile(r"\b\d+\s?(?:pcs?|pieces?|pack(?:\s*of)?\s*\d*|units?)\b", re.IGNORECASE),
    re.compile(r"\bpack\s*of\s*\d+\b", re.IGNORECASE),
]


def extract_quantity_snippet(text: Optional[str]) -> Optional[str]:
    """Best-effort quantity/pack substring (aligned with scraper heuristics)."""
    if not text or not isinstance(text, str):
        return None
    s = re.sub(r"\s+", " ", text).strip()
    if not s:
        return None
    for p in _SNIPPET_PATTERNS:
        m = p.search(s)
        if m:
            return m.group(0).strip()
    return None


def normalize_text_key(s: Optional[str]) -> str:
    if not s:
        return ""
    t = s.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def parse_quantity_to_base(text: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    """
    Normalize to canonical units: ml (volume), g (mass), unit (count / multipack).
    """
    if not text or not isinstance(text, str):
        return None, None
    s = re.sub(r"\s+", " ", text.strip())
    if not s:
        return None, None

    m = _MULT.search(s)
    if m:
        count = float(m.group(1))
        val = float(m.group(2))
        u = m.group(3).lower()
        if u == "l":
            return count * val * 1000.0, "ml"
        if u == "ml":
            return count * val, "ml"
        if u == "kg":
            return count * val * 1000.0, "g"
        if u == "g":
            return count * val, "g"
        if u == "mg":
            return count * val, "mg"

    m = _PACK.search(s)
    if m:
        n = m.group(1) or m.group(2)
        if n:
            return float(n), "unit"

    m = _ML.search(s)
    if m:
        return float(m.group(1)), "ml"

    m = _LITRE.search(s)
    if m:
        return float(m.group(1)) * 1000.0, "ml"

    m = _KG.search(s)
    if m:
        return float(m.group(1)) * 1000.0, "g"

    m = _G.search(s)
    if m:
        return float(m.group(1)), "g"

    m = _MG.search(s)
    if m:
        return float(m.group(1)), "mg"

    return None, None


def quantity_from_candidate_fields(title: Optional[str], quantity_label: Optional[str]) -> Tuple[Optional[float], Optional[str]]:
    combined = f"{title or ''} {quantity_label or ''}"
    return parse_quantity_to_base(combined)


def merge_quantity_label(title: Optional[str], quantity_label: Optional[str]) -> Optional[str]:
    if quantity_label and str(quantity_label).strip():
        return str(quantity_label).strip()
    return extract_quantity_snippet(title)
