import asyncio
import json
import logging
import re
from typing import List

from app.schemas.jobs import ClarificationQuestion

logger = logging.getLogger("services.item_clarifier")


_BROAD_HINTS = {
    "oil",
    "water",
    "soap",
    "shampoo",
    "chips",
    "biscuit",
    "biscuits",
    "rice",
    "atta",
    "chocolate",
    "milk",
    "butter",
}


def _is_broad_item(item: str) -> bool:
    low = item.strip().lower()
    if not low:
        return False
    if len(low.split()) >= 2:
        return False
    return low in _BROAD_HINTS


def _extract_json(text: str):
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    m = re.search(r"\{[\s\S]*\}", text)
    if m:
        text = m.group(0)
    return json.loads(text)


def _clarify_sync(items: List[str], api_key: str, model_name: str) -> List[ClarificationQuestion]:
    import google.generativeai as genai

    broad = [i for i in items if _is_broad_item(i)]
    if not broad:
        return []

    prompt = f"""
You are helping clarify grocery shopping queries.
Given broad product names, return 3-5 popular brand+variant+size options for each item in India.
Rules:
- Quantity should be explicit in each option (e.g., 1 L, 500 ml, 1 kg, 200 g).
- Prefer common options users actually compare.
- Return JSON only with this shape:
{{
  "questions": [
    {{
      "item": "oil",
      "prompt": "Which oil do you want to compare?",
      "options": ["Fortune Sunflower Oil 1 L", "..."]
    }}
  ]
}}

Items: {broad}
"""
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)
    res = model.generate_content(prompt)
    text = res.text or ""
    data = _extract_json(text)
    out: List[ClarificationQuestion] = []
    for q in data.get("questions", []):
        item = str(q.get("item", "")).strip()
        prompt_txt = str(q.get("prompt", "")).strip() or f"Which {item} do you want to compare?"
        options = [str(x).strip() for x in (q.get("options") or []) if str(x).strip()]
        if item and options:
            out.append(ClarificationQuestion(item=item, prompt=prompt_txt, options=options[:5]))
    return out


async def clarify_items_with_llm(
    items: List[str],
    api_key: str,
    model_name: str = "gemini-2.0-flash-lite",
) -> List[ClarificationQuestion]:
    broad = [i for i in items if _is_broad_item(i)]
    if not broad:
        return []
    if not api_key.strip():
        # Minimal fallback questions when key is missing.
        return [
            ClarificationQuestion(
                item=i,
                prompt=f"Which {i} do you want to compare?",
                options=[],
            )
            for i in broad
        ]
    try:
        return await asyncio.to_thread(_clarify_sync, items, api_key, model_name)
    except Exception as e:
        logger.warning("Item clarification LLM failed: %s", e)
        return []
