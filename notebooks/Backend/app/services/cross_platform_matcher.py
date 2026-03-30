"""LLM-assisted single search string so all platforms target the same SKU / pack size."""

import json
import logging
import re
from typing import List, Optional

from models import ProductInfo

logger = logging.getLogger("services.cross_platform_matcher")


def _extract_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def unified_search_after_first_pass(
    user_query: str,
    infos: List[ProductInfo],
    api_key: str,
    model_name: str,
) -> Optional[str]:
    """
    Return a refined search phrase to run on ALL platforms, or None to keep the first pass only.

    When the model believes the three listings already match the same product+pack, it should
    set should_rerun false so we avoid an extra scrape.
    """
    if not api_key.strip():
        return None

    lines = []
    for p in infos:
        lines.append(
            f"- {p.platform.value}: title={p.listing_title!r} qty_hint={p.quantity_label!r} price={p.price}"
        )
    block = "\n".join(lines)

    prompt = f"""You align grocery price comparisons across Instamart, Blinkit, and Zepto (India).

User asked to compare: "{user_query}"

Each app currently opened the TOP relevant search result:
{block}

Decide if these three rows describe the SAME product and SAME pack size (e.g. same ml/g/pc count). If they do not, or if the query was vague, propose ONE search string that should be used on ALL THREE apps to find a single comparable SKU (include brand and pack size when possible, e.g. "Aquafina drinking water 1 l" or "Amul Taaza toned milk 500 ml").

Rules:
- unified_search must be short enough to paste into each app's search box.
- If first-pass listings already match on product + pack size, set should_rerun to false.
- If they differ in brand, volume, or unit count, set should_rerun to true and fill unified_search.

Reply with JSON only:
{{"unified_search": "<string or empty>", "should_rerun": true/false, "note": "<one sentence>"}}
"""

    try:
        import google.generativeai as genai

        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(model_name)
        res = model.generate_content(prompt)
        text = res.text or ""
        data = _extract_json(text)
    except Exception:
        logger.exception("cross_platform_matcher: Gemini call failed")
        return None

    should_rerun = bool(data.get("should_rerun"))
    unified = (data.get("unified_search") or "").strip()
    note = (data.get("note") or "").strip()

    if not should_rerun:
        logger.info("cross_platform_match: keeping first pass (%s)", note[:120])
        return None

    if not unified:
        logger.warning("cross_platform_match: should_rerun but empty unified_search")
        return None

    if unified.lower() == user_query.strip().lower():
        return None

    logger.info("cross_platform_match: second pass with %r (%s)", unified, note[:120])
    return unified

