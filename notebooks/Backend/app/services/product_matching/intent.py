"""User-query normalization for display titles and tokenization."""

import re
from typing import Set


def normalize_query_title(query: str) -> str:
    """Display title from what the user typed, e.g. apples → Apples, brown bread → Brown Bread."""
    s = (query or "").strip()
    if not s:
        return s
    s = re.sub(r"\s+", " ", s)
    return s.title()


def query_tokens(query: str) -> Set[str]:
    raw = re.findall(r"[a-z0-9]+", (query or "").lower())
    return {t for t in raw if len(t) >= 2}
