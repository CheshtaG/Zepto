"""
Use Google Gemini (2.0 Flash Lite by default) to read listing screenshots and align
quantities so prices can be compared on a per-unit basis (ml, g, or piece).
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import shutil
from typing import Any, Dict, List, Optional, Tuple

from models import Platform, ProductInfo

logger = logging.getLogger("services.gemini_quantity")

SYSTEM_PROMPT = """You analyze grocery delivery app screenshots. Each image is labeled with its platform name before the image.

The user searched for: "{query}"

For each platform image, look at the FIRST / top-most product listing (hero tile) and extract:
- The visible pack size (e.g. 500 ml, 1 L, 6 x 200 ml, 500 g, 1 kg, pack of 6).
- Convert multi-packs to total volume or total weight when possible.
- The visible selling price in INR (the number written next to the rupee symbol). Prefer the price the user pays (not MRP/discount labels unless no other price exists).

Reply with ONLY valid JSON (no markdown fences), exactly in this shape:
{{
  "per_platform": {{
    "instamart": {{"pack_label": "string or null", "amount_ml": null, "amount_g": null, "piece_count": null, "price_inr": null, "confidence": 0.0}},
    "blinkit": {{"pack_label": null, "amount_ml": null, "amount_g": null, "piece_count": null, "price_inr": null, "confidence": 0.0}},
    "zepto": {{"pack_label": null, "amount_ml": null, "amount_g": null, "piece_count": null, "price_inr": null, "confidence": 0.0}}
  }},
  "same_pack_across_platforms": true,
  "explanation": "short English sentence"
}}

Rules:
- amount_ml: total liquid milliliters (1 L -> 1000, 500 ml -> 500, 6x200ml -> 1200).
- amount_g: total grams for dry goods.
- piece_count: use for countable packs when ml/g are not on the card.
- price_inr: the selling price as a number (e.g. 39.0). Use null if you cannot read the rupee price reliably.
- Use null when unknown. confidence is 0-1.
- same_pack_across_platforms: true only if the dominant listing pack is effectively the same total quantity across all images you could read; otherwise false.
"""


def _strip_json_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
        text = re.sub(r"\s*```\s*$", "", text)
    return text


def _parse_json(text: str) -> Optional[Dict[str, Any]]:
    text = _strip_json_fences(text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{[\s\S]*\}", text)
        if m:
            try:
                return json.loads(m.group(0))
            except json.JSONDecodeError:
                return None
    return None


def _run_gemini_sync(
    query: str,
    platform_image_paths: List[Tuple[str, Optional[str]]],
    api_key: str,
    model_name: str,
) -> Optional[Dict[str, Any]]:
    import google.generativeai as genai
    from PIL import Image

    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(model_name)

    parts: List[Any] = [SYSTEM_PROMPT.format(query=query)]
    loaded_any = False
    for platform_key, path in platform_image_paths:
        if not path or not os.path.isfile(path):
            continue
        try:
            img = Image.open(path).convert("RGB")
            parts.append(f"\n[Platform: {platform_key}]\n")
            parts.append(img)
            loaded_any = True
        except Exception as exc:
            logger.warning("Skip image for %s (%s): %s", platform_key, path, exc)

    if not loaded_any:
        return None

    try:
        response = model.generate_content(
            parts,
            generation_config=genai.types.GenerationConfig(temperature=0.15),
        )
    except Exception as exc:
        logger.exception("Gemini request failed: %s", exc)
        return None

    try:
        text = response.text
    except ValueError:
        logger.warning("Gemini returned no text (blocked or empty response)")
        return None
    if not text:
        return None
    return _parse_json(text)


def _pick_base_unit(block: Dict[str, Any]) -> Tuple[Optional[float], Optional[str]]:
    ml = block.get("amount_ml")
    g = block.get("amount_g")
    pieces = block.get("piece_count")
    try:
        if ml is not None and float(ml) > 0:
            return float(ml), "ml"
    except (TypeError, ValueError):
        pass
    try:
        if g is not None and float(g) > 0:
            return float(g), "g"
    except (TypeError, ValueError):
        pass
    try:
        if pieces is not None and float(pieces) > 0:
            return float(pieces), "piece"
    except (TypeError, ValueError):
        pass
    return None, None


def enrich_product_infos_with_quantities(
    query: str,
    infos: List[ProductInfo],
    api_key: str,
    model_name: str,
) -> List[ProductInfo]:
    """Return a new list of ProductInfo with quantity fields filled from Gemini."""
    order = [Platform.INSTAMART, Platform.BLINKIT, Platform.ZEPTO]
    by_platform = {i.platform: i for i in infos}
    paths: List[Tuple[str, Optional[str]]] = []
    for plat in order:
        info = by_platform.get(plat)
        paths.append((plat.value, info.screenshot_path if info else None))

    data = _run_gemini_sync(query, paths, api_key, model_name)
    if not data:
        return [
            i.model_copy(
                update={
                    "quantity_comparison_note": i.quantity_comparison_note
                    or "Quantity vision pass skipped (missing screenshots, API error, or invalid model response)."
                }
            )
            for i in infos
        ]

    per = data.get("per_platform") or {}
    same_pack = data.get("same_pack_across_platforms")
    explanation = (data.get("explanation") or "").strip()

    # Compare-on-same-basis rule:
    # - If we can extract a base unit (ml/g/piece) for at least 2 platforms
    # - And that base unit matches across them
    # then we can compare on a per-base-unit basis even if the pack labels differ.
    extracted_base_units: set[str] = set()
    extracted_any_base_val = False
    per_info: dict[str, tuple[Optional[float], Optional[str]]] = {}
    for info in infos:
        key = info.platform.value
        block = per.get(key)
        if not isinstance(block, dict):
            block = {}
        base_val, base_unit = _pick_base_unit(block)
        per_info[key] = (base_val, base_unit)
        if base_unit:
            extracted_base_units.add(base_unit)
        if base_val is not None:
            extracted_any_base_val = True

    quantity_comparable = None
    if len(extracted_base_units) == 1 and extracted_any_base_val and same_pack is not False:
        # same_pack can be true or missing; if Gemini says packs are totally different,
        # we still may compare if unit matches; allow regardless of same_pack boolean.
        quantity_comparable = True
    elif len(extracted_base_units) == 1 and extracted_any_base_val:
        quantity_comparable = True

    out: List[ProductInfo] = []
    for info in infos:
        key = info.platform.value
        block = per.get(key)
        if not isinstance(block, dict):
            block = {}

        pack_label = block.get("pack_label")
        if pack_label is not None and not isinstance(pack_label, str):
            pack_label = str(pack_label)

        base_val, base_unit = per_info.get(key, (None, None))

        vision_price = block.get("price_inr")
        vision_price_val: Optional[float] = None
        try:
            if vision_price is not None:
                vision_price_val = float(vision_price)
        except (TypeError, ValueError):
            vision_price_val = None

        # Prefer vision price when available, because OCR can confuse pack size with price.
        final_price = vision_price_val if vision_price_val is not None else info.price

        ppu: Optional[float] = None
        if final_price is not None and base_val and base_val > 0:
            ppu = round(float(final_price) / base_val, 6)

        note = explanation
        if note:
            if same_pack is False:
                note = f"{note} Pack sizes may differ — use price per ml/g/piece when available."
            elif quantity_comparable is True:
                note = f"{note} Compared on a common unit basis."

        out.append(
            info.model_copy(
                update={
                    "quantity_label": pack_label,
                    "quantity_base_value": base_val,
                    "quantity_base_unit": base_unit,
                    "price": final_price,
                    "price_per_base_unit": ppu,
                    "quantity_comparable": quantity_comparable,
                    "quantity_comparison_note": note or None,
                }
            )
        )
    return out


async def enrich_product_infos_async(
    query: str,
    infos: List[ProductInfo],
    api_key: str,
    model_name: str,
) -> List[ProductInfo]:
    return await asyncio.to_thread(
        enrich_product_infos_with_quantities,
        query,
        infos,
        api_key,
        model_name,
    )


_INSTAMART_PRICE_PROMPT = """Swiggy Instamart screenshot. User searched for: "{query}".

Pick the FIRST organic product card in the results grid under "Showing results" (top-left / first row item). Ignore middle-of-page sponsored hero banners if the first small product tile is clearly above them.

Return the price the customer pays: the INR number next to ₹ on that card (use the sale/discounted price if both MRP and a lower price are shown).

Reply with ONLY this JSON, no markdown:
{{"price_inr": <number>}}
or {{"price_inr": null}} if impossible."""


def _gemini_response_text(response: Any) -> str:
    """Some responses block `response.text`; still read candidate parts when possible."""
    try:
        t = getattr(response, "text", None)
        if t:
            return str(t).strip()
    except ValueError:
        pass
    try:
        chunks: List[str] = []
        for c in getattr(response, "candidates", None) or []:
            content = getattr(c, "content", None)
            if not content:
                continue
            for p in getattr(content, "parts", None) or []:
                txt = getattr(p, "text", None)
                if txt:
                    chunks.append(str(txt))
        return "\n".join(chunks).strip()
    except Exception:
        return ""


def _price_inr_from_model_text(text: str) -> Optional[float]:
    if not text:
        return None
    data = _parse_json(text)
    if isinstance(data, dict):
        raw = data.get("price_inr")
        if raw is not None and str(raw).lower() != "null":
            try:
                val = float(raw)
                if 1.0 <= val <= 50000.0:
                    return val
            except (TypeError, ValueError):
                pass
    m = re.search(r'"price_inr"\s*:\s*([0-9]+(?:\.[0-9]+)?)', text, re.I)
    if m:
        try:
            val = float(m.group(1))
            if 1.0 <= val <= 50000.0:
                return val
        except ValueError:
            pass
    m2 = re.search(r"₹\s*([0-9]+(?:\.[0-9]+)?)", text)
    if m2:
        try:
            val = float(m2.group(1))
            if 1.0 <= val <= 50000.0:
                return val
        except ValueError:
            pass
    return None


# Prefer models that support vision + generateContent on AI Studio (v1beta).
# Avoid deprecated ids like gemini-1.5-flash (404 on many projects).
_INSTAMART_MODEL_FALLBACKS = (
    "gemini-2.0-flash",
    "gemini-2.5-flash",
    "gemini-2.0-flash-lite",
)


def read_instamart_price_from_ocr_sync(image_path: str) -> Optional[float]:
    """Last-resort price from Instamart PNG when Gemini fails (needs tesseract on PATH)."""
    try:
        import pytesseract
        from PIL import Image
    except ImportError:
        return None
    try:
        tesseract_cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
        if not tesseract_cmd:
            for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
                if os.path.exists(candidate):
                    tesseract_cmd = candidate
                    break
        if tesseract_cmd:
            pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
        text = pytesseract.image_to_string(Image.open(image_path).convert("RGB"), lang="eng")
    except Exception as exc:
        logger.warning(
            "Instamart OCR failed (%s). On macOS install the engine: brew install tesseract",
            exc,
        )
        return None
    if not text or not text.strip():
        return None
    # First ₹ amount in reading order is usually the first product card on search grids.
    for m in re.finditer(r"₹\s*([0-9]+(?:\.[0-9]+)?)", text):
        try:
            val = float(m.group(1))
            if 5.0 <= val <= 10000.0:
                return val
        except ValueError:
            continue
    for m in re.finditer(r"(?:Rs\.?|INR)\s*([0-9]+(?:\.[0-9]+)?)", text, re.I):
        try:
            val = float(m.group(1))
            if 5.0 <= val <= 10000.0:
                return val
        except ValueError:
            continue
    return None


def _pil_resize_for_gemini(img: Any, max_side: int = 1536) -> Any:
    """Very large Instamart full-page PNGs can cause Gemini to fail; shrink while keeping detail."""
    from PIL import Image

    w, h = img.size
    if max(w, h) <= max_side:
        return img
    scale = max_side / float(max(w, h))
    nw, nh = max(1, int(w * scale)), max(1, int(h * scale))
    return img.resize((nw, nh), Image.Resampling.LANCZOS)


def _read_instamart_price_gemini_sync(
    image_path: str,
    query: str,
    api_key: str,
    model_name: str,
) -> Optional[float]:
    import google.generativeai as genai
    from PIL import Image

    genai.configure(api_key=api_key)
    try:
        img = Image.open(image_path).convert("RGB")
        img = _pil_resize_for_gemini(img)
    except Exception as exc:
        logger.warning("Instamart Gemini: cannot open %s: %s", image_path, exc)
        return None

    models_order = [model_name] + [m for m in _INSTAMART_MODEL_FALLBACKS if m != model_name]
    prompt = _INSTAMART_PRICE_PROMPT.format(query=query)
    last_exc: Optional[Exception] = None
    for mdl in models_order:
        try:
            model = genai.GenerativeModel(mdl)
            response = model.generate_content(
                [prompt, img],
                generation_config=genai.types.GenerationConfig(temperature=0.1),
            )
            text = _gemini_response_text(response)
            if not text:
                logger.warning(
                    "Instamart vision: no extractable text model=%s query=%r", mdl, query
                )
                continue
            val = _price_inr_from_model_text(text)
            if val is not None:
                logger.info("Instamart vision ok model=%s price=%s query=%r", mdl, val, query)
                return val
            logger.warning(
                "Instamart vision: parse failed model=%s query=%r sample=%r",
                mdl,
                query,
                text[:500],
            )
        except Exception as exc:
            last_exc = exc
            logger.warning("Instamart vision: model %s error: %s", mdl, exc)
            continue
    if last_exc:
        logger.error("Instamart vision: exhausted models for query=%r: %s", query, last_exc)
    return None


def read_instamart_price_from_screenshot_sync(
    image_path: str,
    query: str,
    api_key: str,
    model_name: str,
) -> Optional[float]:
    """Gemini first (if API key), then Tesseract OCR on the same PNG."""
    if not image_path or not os.path.isfile(image_path):
        return None
    key = (api_key or "").strip()
    if key:
        g = _read_instamart_price_gemini_sync(image_path, query, key, model_name)
        if g is not None:
            return g
    ocr = read_instamart_price_from_ocr_sync(image_path)
    if ocr is not None:
        logger.info("Instamart price from OCR: %s file=%s", ocr, image_path)
    return ocr


async def read_instamart_price_from_screenshot_parallel(
    image_path: str,
    query: str,
    api_key: str,
    model_name: str,
) -> Optional[float]:
    """
    Read Instamart price from the same screenshot using BOTH:
    - Gemini vision
    - Tesseract OCR

    Run them in parallel and return the first non-None price.
    This reduces worst-case latency when Gemini is slow/429 while OCR succeeds.
    """
    api_key = (api_key or "").strip()
    tasks: List[asyncio.Task[Optional[float]]] = []

    if api_key:
        tasks.append(
            asyncio.create_task(
                asyncio.to_thread(
                    _read_instamart_price_gemini_sync,
                    image_path,
                    query,
                    api_key,
                    model_name,
                )
            )
        )

    tasks.append(asyncio.create_task(asyncio.to_thread(read_instamart_price_from_ocr_sync, image_path)))

    pending = set(tasks)
    while pending:
        done, pending = await asyncio.wait(pending, return_when=asyncio.FIRST_COMPLETED)
        for d in done:
            try:
                val = d.result()
            except Exception:
                val = None
            if val is not None:
                return val

    return None


def resolve_instamart_screenshot_path(query: str, hinted_path: Optional[str]) -> Optional[str]:
    """Use ProductInfo path if valid; else data/instamart/{query}_search.png under known data roots."""
    if hinted_path:
        ap = os.path.abspath(hinted_path)
        if os.path.isfile(ap):
            return ap
    roots: List[str] = []
    try:
        from config import DATA_DIR as legacy_dir

        if legacy_dir:
            roots.append(legacy_dir)
    except Exception:
        pass
    try:
        from app.core.config import get_settings

        gd = (get_settings().data_dir or "").strip()
        if gd:
            roots.append(gd)
    except Exception:
        pass
    env_dir = (os.environ.get("COMPARE_DATA_DIR") or "").strip()
    if env_dir:
        roots.append(env_dir)
    safe_name = query.strip().replace(" ", "_")
    seen: set[str] = set()
    for DATA_DIR in roots:
        if not DATA_DIR or DATA_DIR in seen:
            continue
        seen.add(DATA_DIR)
        candidate = os.path.join(DATA_DIR, "instamart", f"{safe_name}_search.png")
        if os.path.isfile(candidate):
            return os.path.abspath(candidate)
    return None


async def fill_instamart_price_from_screenshot_if_missing(
    query: str,
    infos: List[ProductInfo],
    api_key: str,
    model_name: str,
) -> List[ProductInfo]:
    """If Instamart has no DOM price but a screenshot file exists, set price from Gemini."""
    idx = next((i for i, p in enumerate(infos) if p.platform == Platform.INSTAMART), None)
    if idx is None:
        return infos
    inst = infos[idx]
    if inst.price is not None:
        return infos
    path = resolve_instamart_screenshot_path(query, inst.screenshot_path)
    if not path:
        logger.warning(
            "Instamart vision skipped for query=%r: no screenshot file (hint=%r)",
            query,
            inst.screenshot_path,
        )
        return infos
    logger.info("Instamart screenshot fallback query=%r file=%s", query, path)
    price = await read_instamart_price_from_screenshot_parallel(
        path,
        query,
        api_key,
        model_name,
    )
    if price is None:
        logger.warning(
            "Instamart screenshot gave no price (Gemini + OCR) query=%r file=%s", query, path
        )
        return infos
    logger.info("Instamart screenshot price set: %s query=%s", price, query)
    updated = inst.model_copy(
        update={
            "price": price,
            "availability": True,
            "quantity_comparison_note": inst.quantity_comparison_note
            or "Instamart price read from screenshot (Gemini or OCR; DOM had no price).",
        }
    )
    out = list(infos)
    out[idx] = updated
    return out
