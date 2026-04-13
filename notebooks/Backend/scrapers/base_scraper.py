from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urljoin

from playwright.async_api import async_playwright, Browser, ElementHandle, Page, Playwright
from models import ProductInfo, Platform
import asyncio
import os
import shutil
import re
from app.core.config import get_settings
from app.services.image_resolver import resolve_image_with_gemini_search_sync


class BaseScraper(ABC):
    # Reuse a single Playwright + browser across requests to reduce startup latency.
    # Contexts are still created per search so we don't share mutable state.
    _shared_playwright: Optional[Playwright] = None
    _shared_browser: Optional[Browser] = None
    _shared_lock: Optional[asyncio.Lock] = None

    def __init__(self):
        self.target_city: Optional[str] = None
        self.target_pincode: Optional[str] = None

    def set_runtime_location(self, city: Optional[str], pincode: Optional[str]) -> None:
        """Set per-request target location for scraper interactions."""
        self.target_city = city
        self.target_pincode = pincode

    @classmethod
    async def _get_shared_browser(cls):
        """Initialize (once) a shared Playwright + browser instance."""
        if cls._shared_playwright is not None and cls._shared_browser is not None:
            return cls._shared_playwright, cls._shared_browser

        if cls._shared_lock is None:
            cls._shared_lock = asyncio.Lock()

        async with cls._shared_lock:
            if cls._shared_playwright is not None and cls._shared_browser is not None:
                return cls._shared_playwright, cls._shared_browser

            playwright = await async_playwright().start()
            # Use Firefox (more stable on macOS, Chromium has issues)
            browser = await playwright.firefox.launch(
                headless=True,
                timeout=90000,
            )

            cls._shared_playwright = playwright
            cls._shared_browser = browser
            return playwright, browser
    
    async def _create_browser_context(self):
        """Create a new browser and page for each operation with anti-detection measures."""
        max_retries = 2
        retry_delay = 1

        playwright, browser = await self._get_shared_browser()

        for attempt in range(max_retries):
            try:
                # Create a fresh context per search so we don't share cookies/modals/state.
                context = await browser.new_context(
                    viewport={"width": 2560, "height": 1440},
                    device_scale_factor=2,
                    user_agent='Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                    locale='en-US',
                    timezone_id='Asia/Kolkata',
                    ignore_https_errors=True,
                )
                page = await context.new_page()
                return playwright, browser, context, page
            except Exception as e:
                if attempt < max_retries - 1:
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                raise Exception(f"Failed to create browser context: {e}")
    
    async def _close_browser_context(self, playwright, browser, context, page):
        """Close page+context. Shared browser/playwright stays alive for speed."""
        try:
            if page:
                try:
                    await page.close()
                except Exception:
                    pass
        except Exception:
            pass
        try:
            if context:
                try:
                    await context.close()
                except Exception:
                    pass
        except Exception:
            pass

    async def _recover_from_error_page(self, page: Page, max_attempts: int = 2) -> bool:
        """
        Some platforms show transient error/blocked pages like:
        - 'Something went wrong' with a 'Try Again' button.
        Best-effort recovery by clicking Try Again or reloading.
        Returns True if we *might* have recovered.
        """
        for attempt in range(max_attempts):
            try:
                # Detect common error banners
                error_node = await page.query_selector('text=/Something went wrong/i')
                if not error_node:
                    return True

                # Try click 'Try Again' if present
                try_again = await page.query_selector('text=/Try Again/i')
                if try_again and await try_again.is_visible():
                    try:
                        await try_again.click()
                    except Exception:
                        await try_again.evaluate('el => el.click()')
                else:
                    await page.reload(wait_until="domcontentloaded")

                # Wait a short moment; then rely on the next selectors/waits
                # (in the concrete scraper) to confirm the page recovered.
                await asyncio.sleep(0.8 + 0.4 * attempt)
                # If error text is gone, we recovered.
                still_error = await page.query_selector('text=/Something went wrong/i')
                if not still_error:
                    return True
            except Exception:
                try:
                    await page.reload(wait_until="domcontentloaded")
                    await asyncio.sleep(0.8 + 0.4 * attempt)
                except Exception:
                    pass

        return False

    async def _wait_for_spa_dom_commit(self, page: Page) -> None:
        """Wait for the next paint after client-side rendering (React/Vue commit to real ``document``).

        Framework virtual DOM is not readable from outside; this lets hydration settle before we scrape.
        """
        try:
            await page.evaluate(
                """() => new Promise((resolve) => {
                  requestAnimationFrame(() => {
                    requestAnimationFrame(() => resolve(null));
                  });
                })"""
            )
        except Exception:
            pass

    async def read_rendered_dom(
        self, page: Page, expression: str, arg: Optional[Any] = None
    ) -> Any:
        """Run JS in the page context; read the **rendered** DOM (post-hydration), not static HTML."""
        if arg is not None:
            return await page.evaluate(expression, arg)
        return await page.evaluate(expression)

    async def _extract_price_vdom_from_element(self, root: Optional[ElementHandle]) -> Optional[float]:
        """Tier 1 — in-page JS on the rendered tree (``element.evaluate``). Prefer before Playwright DOM."""
        if root is None:
            return None
        try:
            val = await root.evaluate(
                """(el) => {
                  const txt = ((el.innerText || el.textContent || '') || '').replace(/\\s+/g, ' ');
                  const re = /(?:₹|\\u20b9|[Rr][sS]\\.?)\\s*(\\d+(?:\\.\\d+)?)/gi;
                  const badCtx = (slice) =>
                    /\\boff\\b|discount|save\\s|cashback|reward|coupon|applied|%\\s*off|\\d+\\s*%|mins?\\b|minutes?|delivery|arriving|km\\b|located|sponsored|extra\\s*₹/i.test(
                      slice,
                    );
                  const candidates = [];
                  let m;
                  while ((m = re.exec(txt)) !== null) {
                    const v = Number(m[1]);
                    if (!Number.isFinite(v) || v < 1 || v > 10000) continue;
                    const start = Math.max(0, m.index - 24);
                    const end = Math.min(txt.length, m.index + m[0].length + 24);
                    if (badCtx(txt.slice(start, end))) continue;
                    candidates.push(v);
                  }
                  if (!candidates.length) return null;
                  const plausible = candidates.filter((x) => x >= 5);
                  const pool = plausible.length ? plausible : candidates;
                  let chosen = Math.min(...pool);
                  const hi = Math.max(...candidates);
                  if (chosen < 5 && hi >= 25) {
                    const g = pool.filter((x) => x >= 5);
                    if (g.length) chosen = Math.min(...g);
                  }
                  return chosen;
                }"""
            )
            if val is None:
                return None
            f = float(val)
            return f if 1.0 <= f <= 10000.0 else None
        except Exception:
            return None

    async def _extract_price_vdom_first_product_card(self, page: Page) -> Optional[float]:
        """Tier 1 — first visible product tile via ``page.evaluate`` (rendered document)."""
        try:
            val = await page.evaluate(
                """() => {
                  const sels = [
                    '[data-testid*="product" i]', '.product-card', '.product-item',
                    '[class*="ProductCard" i]', '[class*="product-card" i]',
                    'article', '[role="article"]', 'a[href*="product" i]'
                  ];
                  const vh = window.innerHeight || 900;
                  const badCtx = (slice) =>
                    /\\boff\\b|discount|save\\s|cashback|reward|coupon|applied|%\\s*off|\\d+\\s*%|mins?\\b|minutes?|delivery|arriving|km\\b|located|sponsored|extra\\s*₹/i.test(
                      slice,
                    );
                  const rupeeVals = (txt) => {
                    const re = /(?:₹|\\u20b9|[Rr][sS]\\.?)\\s*(\\d+(?:\\.\\d+)?)/gi;
                    const candidates = [];
                    let m;
                    while ((m = re.exec(txt)) !== null) {
                      const v = Number(m[1]);
                      if (!Number.isFinite(v) || v < 1 || v > 10000) continue;
                      const start = Math.max(0, m.index - 24);
                      const end = Math.min(txt.length, m.index + m[0].length + 24);
                      if (badCtx(txt.slice(start, end))) continue;
                      candidates.push(v);
                    }
                    if (!candidates.length) return null;
                    const plausible = candidates.filter((x) => x >= 5);
                    const pool = plausible.length ? plausible : candidates;
                    let chosen = Math.min(...pool);
                    const hi = Math.max(...candidates);
                    if (chosen < 5 && hi >= 25) {
                      const g = pool.filter((x) => x >= 5);
                      if (g.length) chosen = Math.min(...g);
                    }
                    return chosen;
                  };
                  for (const s of sels) {
                    let nodes = [];
                    try { nodes = Array.from(document.querySelectorAll(s)); } catch (e) { continue; }
                    for (const el of nodes) {
                      const r = el.getBoundingClientRect();
                      if (r.width < 40 || r.height < 40) continue;
                      if (r.bottom < 0 || r.top > vh + 200) continue;
                      const txt = (el.innerText || el.textContent || '').replace(/\\s+/g, ' ');
                      if (txt.length < 8) continue;
                      const pick = rupeeVals(txt);
                      if (pick != null) return pick;
                    }
                  }
                  return null;
                }"""
            )
            if val is None:
                return None
            f = float(val)
            return f if 1.0 <= f <= 10000.0 else None
        except Exception:
            return None

    async def _extract_price_dom_playwright(
        self,
        page: Page,
        product_element: Optional[ElementHandle],
        price_selectors: List[str],
    ) -> Optional[float]:
        """Tier 2 — Playwright ``query_selector`` + ``inner_text`` (first fallback after tier 1)."""
        price_text = None
        if product_element:
            try:
                for elem in (await product_element.query_selector_all("span, div, p"))[:14]:
                    try:
                        text = await elem.inner_text()
                        if "₹" in text or "Rs" in text.lower():
                            import re

                            if re.search(r"[₹Rs]?\s*\d+", text):
                                price_text = text
                                break
                    except Exception:
                        continue
            except Exception:
                pass
        if not price_text:
            for selector in price_selectors:
                try:
                    for elem in (await page.query_selector_all(selector))[:12]:
                        try:
                            text = await elem.inner_text()
                            if "₹" in text or "Rs" in text.lower():
                                price_text = text
                                break
                        except Exception:
                            continue
                    if price_text:
                        break
                except Exception:
                    continue
        return self._extract_price(price_text) if price_text else None

    def _absolute_media_url(self, page: Page, raw: Optional[str]) -> Optional[str]:
        """Turn a possibly relative image URL into an absolute https URL for the browser."""
        if not raw or not isinstance(raw, str):
            return None
        raw = raw.strip()
        if raw.startswith("data:"):
            return None
        if len(raw) < 8:
            return None
        if raw.startswith("//"):
            return "https:" + raw
        if raw.startswith("http://") or raw.startswith("https://"):
            return raw
        try:
            return urljoin(page.url, raw)
        except Exception:
            return None

    async def _extract_product_image_url(self, page: Page, root: Optional[ElementHandle]) -> Optional[str]:
        """
        Best-effort URL of the product thumbnail inside the chosen card (CDN img src / lazy attrs / srcset).
        """
        if root is None:
            return None
        try:
            raw = await root.evaluate(
                """(el) => {
                  const bad = (u) => !u || u.startsWith('data:') || u.length < 8;
                  const firstFromSrcset = (s) => {
                    if (!s) return null;
                    const p = s.split(',')[0].trim().split(/\\s+/)[0];
                    return p || null;
                  };
                  const imgs = el.querySelectorAll('img');
                  let best = null;
                  let bestArea = 0;
                  for (const img of imgs) {
                    let u = img.currentSrc || img.getAttribute('src') || '';
                    if (bad(u)) u = img.getAttribute('data-src') || img.getAttribute('data-original') || '';
                    if (bad(u)) u = firstFromSrcset(img.getAttribute('srcset')) || '';
                    if (bad(u)) u = img.getAttribute('data-lazy-src') || '';
                    if (bad(u)) continue;
                    const w = img.naturalWidth || img.width || 0;
                    const h = img.naturalHeight || img.height || 0;
                    const area = w * h;
                    if (area >= bestArea) { bestArea = area; best = u; }
                  }
                  if (best) return best;
                  for (const img of imgs) {
                    const u = img.getAttribute('data-src') || img.getAttribute('data-lazy-src');
                    if (!bad(u)) return u;
                  }
                  const pic = el.querySelector('picture source[srcset]');
                  if (pic) {
                    const u = firstFromSrcset(pic.getAttribute('srcset'));
                    if (!bad(u)) return u;
                  }
                  return null;
                }"""
            )
        except Exception:
            return None
        return self._absolute_media_url(page, raw)

    async def _extract_product_image_candidates_from_card(
        self, page: Page, root: Optional[ElementHandle]
    ) -> List[Dict[str, Any]]:
        if root is None:
            return []
        try:
            raw = await root.evaluate(
                """(el) => {
                  const out = [];
                  const bad = (u) => !u || typeof u !== 'string' || u.length < 8 || u.startsWith('data:');
                  const pickBestSrcset = (s) => {
                    if (!s) return null;
                    const items = String(s).split(',').map((x) => x.trim()).filter(Boolean);
                    let best = null;
                    let bestW = -1;
                    for (const item of items) {
                      const p = item.split(/\\s+/);
                      const u = p[0] || '';
                      if (bad(u)) continue;
                      let w = 0;
                      const m = item.match(/(\\d+)w/);
                      if (m) w = Number(m[1]);
                      if (w >= bestW) { bestW = w; best = u; }
                    }
                    return best;
                  };
                  const pushCandidate = (url, kind, node, extra={}) => {
                    if (bad(url)) return;
                    const w = Number(node?.naturalWidth || node?.width || extra.w || 0) || 0;
                    const h = Number(node?.naturalHeight || node?.height || extra.h || 0) || 0;
                    out.push({
                      url: String(url),
                      kind,
                      width: w,
                      height: h,
                      area: w * h,
                      className: (node?.className && String(node.className)) || '',
                      alt: (node?.getAttribute && (node.getAttribute('alt') || '')) || '',
                    });
                  };

                  const imgs = Array.from(el.querySelectorAll('img'));
                  for (const img of imgs) {
                    const currentSrc = img.currentSrc || '';
                    const src = img.getAttribute('src') || '';
                    const srcset = pickBestSrcset(img.getAttribute('srcset'));
                    const dataSrc = img.getAttribute('data-src') || img.getAttribute('data-original') || img.getAttribute('data-lazy-src') || '';
                    pushCandidate(currentSrc, 'img.currentSrc', img);
                    pushCandidate(src, 'img.src', img);
                    pushCandidate(srcset, 'img.srcset', img);
                    pushCandidate(dataSrc, 'img.dataSrc', img);
                  }

                  const pictureSources = Array.from(el.querySelectorAll('picture source[srcset]'));
                  for (const s of pictureSources) {
                    const u = pickBestSrcset(s.getAttribute('srcset'));
                    pushCandidate(u, 'picture.srcset', s);
                  }

                  const withBg = Array.from(el.querySelectorAll('*')).slice(0, 180);
                  const reBg = /url\\((['"]?)(.*?)\\1\\)/i;
                  for (const n of withBg) {
                    const style = window.getComputedStyle(n);
                    const bg = style && style.backgroundImage ? String(style.backgroundImage) : '';
                    if (!bg || bg === 'none') continue;
                    const m = bg.match(reBg);
                    if (!m || !m[2]) continue;
                    const r = n.getBoundingClientRect();
                    pushCandidate(m[2], 'css.backgroundImage', n, { w: r.width || 0, h: r.height || 0 });
                  }
                  return out;
                }"""
            )
        except Exception:
            return []
        out: List[Dict[str, Any]] = []
        seen: set[str] = set()
        for row in raw or []:
            if not isinstance(row, dict):
                continue
            abs_url = self._absolute_media_url(page, row.get("url"))
            if not abs_url or abs_url in seen:
                continue
            seen.add(abs_url)
            row["url"] = abs_url
            out.append(row)
        return out

    def _score_dom_image_candidate(self, candidate: Dict[str, Any]) -> Tuple[float, str]:
        url = str(candidate.get("url") or "")
        low = url.lower()
        if not (low.startswith("https://") or low.startswith("http://")):
            return 0.0, "non_http_url"
        if len(low) < 12:
            return 0.0, "too_short_url"
        if low.startswith("data:") or low.startswith("blob:"):
            return 0.05, "data_or_blob_url"

        negative = [
            "placeholder", "sprite", "logo", "icon", "favicon", "banner", "avatar",
            "tracking", "pixel", "spacer", "blank", "loader", "thumbnail-default",
        ]
        if any(x in low for x in negative):
            return 0.08, "generic_asset_pattern"
        if re.search(r"(1x1|16x16|24x24|32x32|48x48)", low):
            return 0.1, "tiny_dimension_pattern"

        width = float(candidate.get("width") or 0)
        height = float(candidate.get("height") or 0)
        area = float(candidate.get("area") or (width * height))
        kind = str(candidate.get("kind") or "")
        alt = str(candidate.get("alt") or "").lower()

        score = 0.35
        reason = "usable_http_candidate"
        if "cdn" in low or "images" in low or "product" in low:
            score += 0.18
            reason = "cdn_productish_url"
        if kind in ("img.currentSrc", "img.srcset", "picture.srcset"):
            score += 0.12
        if area >= 18000 or (width >= 120 and height >= 120):
            score += 0.16
        elif area > 0 and area < 3600:
            score -= 0.22
            reason = "very_small_candidate"
        if alt and re.search(r"(logo|icon|brand)", alt):
            score -= 0.15
            reason = "alt_indicates_non_product"
        return max(0.0, min(1.0, score)), reason

    async def _resolve_product_image(
        self,
        *,
        page: Page,
        root: Optional[ElementHandle],
        platform: Platform,
        query: str,
        listing_title: Optional[str],
        quantity_label: Optional[str],
        brand: Optional[str],
        variant: Optional[str] = None,
        product_url: Optional[str] = None,
    ) -> Dict[str, Any]:
        debug: Dict[str, Any] = {
            "dom_candidates": [],
            "selected_dom_candidate": None,
            "dom_rejections": [],
            "gemini_invoked": False,
            "gemini_result": None,
        }

        dom_candidates = await self._extract_product_image_candidates_from_card(page, root)
        best: Optional[Dict[str, Any]] = None
        best_score = -1.0
        best_reason = "none"
        for cand in dom_candidates[:28]:
            score, reason = self._score_dom_image_candidate(cand)
            entry = {
                "url": cand.get("url"),
                "kind": cand.get("kind"),
                "size": [cand.get("width"), cand.get("height")],
                "score": round(score, 4),
                "reason": reason,
            }
            debug["dom_candidates"].append(entry)
            if score > best_score:
                best_score = score
                best = cand
                best_reason = reason
        if best is not None and best_score >= 0.55:
            debug["selected_dom_candidate"] = {
                "url": best.get("url"),
                "score": round(best_score, 4),
                "reason": best_reason,
            }
            return {
                "image_url": best.get("url"),
                "image_source": "dom_card",
                "image_confidence": round(best_score, 4),
                "image_match_reason": f"DOM card candidate accepted ({best_reason})",
                "image_debug": debug,
            }
        if best is not None:
            debug["dom_rejections"].append(
                {"url": best.get("url"), "score": round(best_score, 4), "reason": best_reason}
            )

        settings = get_settings()
        debug["gemini_invoked"] = bool(
            settings.enable_gemini_image_fallback and settings.google_api_key
        )
        if settings.enable_gemini_image_fallback and settings.google_api_key:
            gemini = await asyncio.to_thread(
                resolve_image_with_gemini_search_sync,
                api_key=settings.google_api_key or "",
                model_name=settings.gemini_match_model or settings.gemini_model,
                platform=platform.value,
                raw_query=query,
                canonical_name=listing_title or query,
                listing_title=listing_title,
                brand=brand,
                quantity_label=quantity_label,
                unit=None,
                variant=variant,
                product_url=product_url,
            )
            debug["gemini_result"] = gemini
            if gemini.get("accepted") and gemini.get("image_url"):
                return {
                    "image_url": gemini.get("image_url"),
                    "image_source": "gemini_search",
                    "image_confidence": float(gemini.get("confidence") or 0.0),
                    "image_match_reason": gemini.get("reason") or "gemini_search_accepted",
                    "image_debug": debug,
                }

        return {
            "image_url": None,
            "image_source": "placeholder",
            "image_confidence": 0.0,
            "image_match_reason": "no_high_confidence_dom_or_gemini_image",
            "image_debug": debug,
        }

    async def _extract_listing_title(self, root: Optional[ElementHandle]) -> Optional[str]:
        """Best-effort visible product name from the chosen listing card (as on the site)."""
        if root is None:
            return None
        try:
            text = await root.evaluate(
                """(el) => {
                  const priceLike = (t) => /₹|rs\\.?\\s*\\d|mrp|^\\s*\\d+\\s*%|off\\s*₹/i.test(t);
                  const badLine = (t) => {
                    const s = t.trim();
                    if (s.length < 4 || s.length > 240) return true;
                    if (/^add$/i.test(s)) return true;
                    if (/^\\d+\\s*mins?$/i.test(s)) return true;
                    if (priceLike(s) && s.length < 28) return true;
                    return false;
                  };
                  const cands = [];
                  for (const sel of ['[class*="title" i]', '[class*="name" i]', '[class*="Title" i]', 'h1', 'h2', 'h3', 'h4']) {
                    for (const n of el.querySelectorAll(sel)) {
                      const t = (n.textContent || '').replace(/\\s+/g, ' ').trim();
                      if (!badLine(t)) cands.push(t);
                    }
                  }
                  if (cands.length) {
                    cands.sort((a, b) => b.length - a.length);
                    return cands[0];
                  }
                  const lines = (el.innerText || '').split('\\n').map((s) => s.trim()).filter(Boolean);
                  for (const line of lines) {
                    if (!badLine(line)) return line;
                  }
                  return null;
                }"""
            )
        except Exception:
            return None
        if not text or not isinstance(text, str):
            return None
        t = text.strip()
        return t[:500] if t else None

    def _extract_quantity_from_text(self, text: Optional[str]) -> Optional[str]:
        """Extract a pack/quantity snippet from plain text."""
        if not text or not isinstance(text, str):
            return None
        s = re.sub(r"\s+", " ", text).strip()
        if not s:
            return None
        patterns = [
            r"\b\d+\s?x\s?\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg)\b",
            r"\b\d+(?:\.\d+)?\s?(?:ml|l|g|kg|mg)\b",
            r"\b\d+\s?(?:pcs?|pieces?|pack(?:\s*of)?\s*\d*|units?)\b",
            r"\bpack\s*of\s*\d+\b",
        ]
        for p in patterns:
            m = re.search(p, s, re.IGNORECASE)
            if m:
                return m.group(0).strip()
        return None

    async def _extract_quantity_label(self, root: Optional[ElementHandle], listing_title: Optional[str] = None) -> Optional[str]:
        q = self._extract_quantity_from_text(listing_title)
        if q:
            return q
        if root is None:
            return None
        try:
            raw = await root.evaluate(
                """(el) => {
                  const rows = [];
                  const selectors = [
                    '[class*="qty" i]', '[class*="quantity" i]', '[class*="pack" i]',
                    '[class*="size" i]', '[class*="weight" i]', '[class*="variant" i]',
                    '[data-testid*="quantity" i]', '[data-testid*="pack" i]',
                    'span', 'div', 'p'
                  ];
                  for (const sel of selectors) {
                    for (const n of el.querySelectorAll(sel)) {
                      const t = (n.textContent || '').replace(/\\s+/g, ' ').trim();
                      if (!t || t.length > 80) continue;
                      rows.push(t);
                    }
                  }
                  return [...new Set(rows)].slice(0, 40);
                }"""
            )
        except Exception:
            return None
        if isinstance(raw, list):
            for candidate in raw:
                q2 = self._extract_quantity_from_text(candidate if isinstance(candidate, str) else None)
                if q2:
                    return q2
        return None

    def _extract_brand_from_title(self, title: Optional[str]) -> Optional[str]:
        if not title:
            return None
        s = re.sub(r"\s+", " ", title).strip()
        if not s:
            return None
        stop = {"pack", "combo", "x", "ml", "l", "g", "kg", "mg", "pcs", "piece", "of", "the", "and"}
        variant_skip = {
            "toned", "full", "whole", "skim", "low", "fat", "double", "single",
            "brown", "white", "multigrain", "organic", "a2",
        }
        parts = [p for p in re.split(r"[\s,/()-]+", s) if p]
        if not parts:
            return None
        brand_tokens: List[str] = []
        for t in parts[:5]:
            tl = t.lower()
            if tl in stop or tl in variant_skip or re.search(r"\d", t):
                if brand_tokens:
                    break
                continue
            brand_tokens.append(t)
            if len(brand_tokens) >= 2:
                break
        if not brand_tokens:
            return parts[0][:48]
        return " ".join(brand_tokens)[:48]

    async def _product_link_from_root(self, root: ElementHandle) -> Optional[str]:
        try:
            href = await root.evaluate(
                """(el) => {
                  const a = el.closest('a[href]') || el.querySelector('a[href]');
                  return a && a.href ? String(a.href) : null;
                }"""
            )
            return href if isinstance(href, str) and href.startswith("http") else None
        except Exception:
            return None

    async def _listing_candidate_dict(
        self,
        page: Page,
        platform: Platform,
        root: ElementHandle,
        idx: int,
    ) -> Dict[str, Any]:
        raw_title = await self._extract_listing_title(root)
        title = (raw_title or "").strip()
        quantity_label = await self._extract_quantity_label(root, raw_title)
        card_text = ""
        try:
            card_text = await root.inner_text()
        except Exception:
            card_text = title
        price = self._extract_price(card_text or "")
        image_url = await self._extract_product_image_url(page, root)
        product_url = await self._product_link_from_root(root) or page.url
        brand = self._extract_brand_from_title(title)
        return {
            "id": f"{platform.value}-{idx}",
            "title": title or None,
            "rawTitle": raw_title or title or None,
            "brand": brand,
            "quantityLabel": quantity_label,
            "normalizedQuantity": None,
            "normalizedUnit": None,
            "variant": None,
            "category": None,
            "price": float(price) if price is not None else None,
            "inStock": price is not None,
            "imageUrl": image_url,
            "productUrl": product_url,
            "platform": platform.value,
        }

    async def _collect_listing_candidates(
        self,
        page: Page,
        platform: Platform,
        product_selectors: List[str],
        max_candidates: int = 8,
    ) -> List[Dict[str, Any]]:
        await self._wait_for_spa_dom_commit(page)
        seen: set = set()
        roots: List[ElementHandle] = []
        for selector in product_selectors:
            try:
                elements = await page.query_selector_all(selector)
                for elem in elements[:24]:
                    try:
                        if not await elem.is_visible():
                            continue
                        key = await elem.evaluate("el => (el.innerText || '').slice(0, 120)")
                        key = (key or "").strip()
                        if not key or key in seen:
                            continue
                        seen.add(key)
                        roots.append(elem)
                        if len(roots) >= max_candidates:
                            break
                    except Exception:
                        continue
                if len(roots) >= max_candidates:
                    break
            except Exception:
                continue

        out: List[Dict[str, Any]] = []
        for i, root in enumerate(roots[:max_candidates]):
            try:
                out.append(await self._listing_candidate_dict(page, platform, root, i))
            except Exception:
                continue
        return out

    async def _candidate_listings_with_primary(
        self,
        page: Page,
        platform: Platform,
        product_selectors: List[str],
        product_element: Optional[ElementHandle],
        max_candidates: int = 10,
    ) -> List[Dict[str, Any]]:
        collected = await self._collect_listing_candidates(
            page, platform, product_selectors, max_candidates
        )
        if not product_element:
            return collected[:max_candidates]
        try:
            prim = await self._listing_candidate_dict(page, platform, product_element, 0)
            key = (prim.get("title") or "")[:100]
            rest = [c for c in collected if (c.get("title") or "")[:100] != key]
            merged = [prim] + rest
            return merged[:max_candidates]
        except Exception:
            return collected[:max_candidates]

    @abstractmethod
    async def set_location(self, page: Page):
        """Set location to Pune. Should be implemented by each scraper."""
        pass
    
    @abstractmethod
    async def search_product(self, product_name: str) -> ProductInfo:
        """Search for a product and return ProductInfo. Should be implemented by each scraper."""
        pass
    
    def _extract_price(self, price_text: str) -> float:
        """Extract numeric price from text."""
        if not price_text:
            return None

        import re
        txt = price_text.strip()
        low = txt.lower()

        # If this snippet is clearly a discount badge (e.g. "₹8 OFF"), don't treat it as price.
        if "off" in low or "%" in low or "discount" in low or "save" in low:
            return None

        # Prefer explicit currency amounts.
        vals = []
        for m in re.finditer(r'(?:₹|Rs\.?|INR)\s*(\d+\.?\d*)', txt, re.IGNORECASE):
            try:
                v = float(m.group(1))
                if 1.0 <= v <= 10000.0:
                    vals.append(v)
            except Exception:
                continue
        if vals:
            # Selling price is typically lower than MRP in mixed snippets.
            return min(vals)

        # Fallback to plain numbers only when text doesn't look like discount/quantity context.
        if re.search(r'\b(ml|l|g|kg|pcs?|pack|piece)\b', low, re.IGNORECASE):
            return None
        numbers = re.findall(r'\d+\.?\d*', txt)
        if numbers:
            try:
                v = float(numbers[0])
                if 1.0 <= v <= 10000.0:
                    return v
            except Exception:
                return None
        return None

    async def _take_screenshot(self, page: Page, screenshot_path: str, selector: Optional[str] = None):
        """Take a screenshot of the page or a specific element."""
        try:
            if selector:
                # Wait for the element to be visible
                element = await page.wait_for_selector(selector, timeout=10000, state='visible')
                if element:
                    await element.screenshot(path=screenshot_path)
                    print(f"[Screenshot] Saved element screenshot to {screenshot_path}")
                else:
                    # Fallback to full page screenshot
                    await page.screenshot(path=screenshot_path, full_page=True)
                    print(f"[Screenshot] Element not found, saved full page screenshot to {screenshot_path}")
            else:
                # Take full page screenshot
                await page.screenshot(path=screenshot_path, full_page=True)
                print(f"[Screenshot] Saved full page screenshot to {screenshot_path}")
            return True
        except Exception as e:
            print(f"[Screenshot] Error taking screenshot: {e}")
            return False
    
    def _extract_text_from_screenshot(self, screenshot_path: str) -> str:
        """Extract text from screenshot using OCR."""
        try:
            import pytesseract
            from PIL import Image

            tesseract_cmd = os.getenv("TESSERACT_CMD") or shutil.which("tesseract")
            if not tesseract_cmd:
                for candidate in ("/opt/homebrew/bin/tesseract", "/usr/local/bin/tesseract"):
                    if os.path.exists(candidate):
                        tesseract_cmd = candidate
                        break
            if tesseract_cmd:
                pytesseract.pytesseract.tesseract_cmd = tesseract_cmd
            
            # Read the image
            image = Image.open(screenshot_path)
            
            # Extract text using OCR
            text = pytesseract.image_to_string(image, lang='eng')
            print(f"[OCR] Extracted text from screenshot: {len(text)} characters")
            if len(text) > 0:
                print(f"[OCR] Sample text: {text[:200]}...")
            return text
        except ImportError:
            print("[OCR] Warning: pytesseract not installed. Install with: pip install pytesseract pillow")
            print("[OCR] Also install Tesseract OCR engine:")
            print("[OCR]   macOS: brew install tesseract")
            print("[OCR]   Linux: sudo apt-get install tesseract-ocr")
            print("[OCR]   Windows: Download from https://github.com/UB-Mannheim/tesseract/wiki")
            return ""
        except Exception as e:
            error_msg = str(e)
            if "tesseract" in error_msg.lower() or "not found" in error_msg.lower():
                print(f"[OCR] Error: Tesseract OCR not found. Please install Tesseract:")
                print(f"[OCR]   macOS: brew install tesseract")
                print(f"[OCR]   Linux: sudo apt-get install tesseract-ocr")
            else:
                print(f"[OCR] Error extracting text: {e}")
            return ""
    
    def _extract_price_from_ocr_text(self, ocr_text: str) -> Optional[float]:
        """Extract price from OCR text by looking for currency symbols and numbers."""
        if not ocr_text:
            return None
        
        import re
        
        # Prefer currency-symbol candidates, but don't blindly take the first one.
        # Some listings have pack size (e.g. "48 ml") near other numbers; OCR can mix these up.
        # We:
        # 1) Collect all currency matches with positions
        # 2) Filter out candidates whose local context looks like quantity units (ml/g/kg/l/pieces)
        # 3) Pick the last remaining candidate (usually the price is lower than pack size)
        currency_patterns = [
            r'₹\s*(\d+\.?\d*)',  # ₹60, ₹ 60
            r'Rs\.?\s*(\d+\.?\d*)',  # Rs. 60, Rs 60
            r'(\d+\.?\d*)\s*₹',  # 60 ₹
            r'(\d+\.?\d*)\s*Rs',  # 60 Rs
        ]

        candidates: List[Tuple[int, float]] = []
        for pattern in currency_patterns:
            for m in re.finditer(pattern, ocr_text, re.IGNORECASE):
                try:
                    price = float(m.group(1))
                except ValueError:
                    continue
                if not (1.0 <= price <= 10000.0):
                    continue

                start = max(0, m.start() - 18)
                end = min(len(ocr_text), m.end() + 18)
                context = ocr_text[start:end].lower()
                candidates.append((m.start(), price))

        if candidates:
            # Filter out likely quantity values near the candidate.
            valid: List[Tuple[int, float]] = []
            for pos, price in candidates:
                start = max(0, pos - 18)
                end = min(len(ocr_text), pos + 18 + 18)
                context = ocr_text[start:end].lower()
                if re.search(r'\b(ml|l|g|kg|pcs?|pieces?|pack)\b', context, re.IGNORECASE):
                    continue
                # Skip discount badge values like "₹8 OFF"
                if re.search(r'\b(off|discount|save)\b|%', context, re.IGNORECASE):
                    continue
                valid.append((pos, price))

            chosen = (valid or candidates)
            # Prefer the lower non-discount amount (often selling price vs MRP).
            _, best_price = min(chosen, key=lambda x: x[1])
            print(f"[OCR] Found price candidate: ₹{best_price}")
            return best_price
        
        # Fallback (quantities can be mistaken as price):
        # If OCR didn't include currency symbols, we *only* accept numbers that do NOT look like
        # quantity expressions (ml/g/l/kg/pieces). Otherwise we return None and rely on DOM/text
        # extraction which usually contains explicit ₹/Rs.
        for m in re.finditer(r'\b(\d+\.?\d{0,2})\b', ocr_text):
            try:
                num = float(m.group(1))
            except ValueError:
                continue
            if not (5.0 <= num <= 5000.0):
                continue

            start = max(0, m.start() - 12)
            end = min(len(ocr_text), m.end() + 25)
            context = ocr_text[start:end].lower()

            # Skip likely quantities.
            # Examples: "500 ml", "250g", "1 L", "6 x 200 ml", "pcs"
            if re.search(r'\b(ml|l|g|kg|pcs?|pieces?|pack)\b', context, re.IGNORECASE):
                continue

            # Also skip if "mrp" or other non-price patterns dominate.
            if "ml" in context or "g" in context:
                continue

            print(f"[OCR] Found potential price (no currency, quantity-filtered): ₹{num}")
            return num
        
        print("[OCR] No price found in OCR text")
        return None

    def _extract_price_from_text(self, text: str) -> Optional[float]:
        """Extract price from generic text (DOM/OCR fallback)."""
        if not text:
            return None

        import re

        candidates = []
        patterns = [
            r'₹\s*(\d+\.?\d*)',
            r'Rs\.?\s*(\d+\.?\d*)',
            r'(\d+\.?\d*)\s*₹',
            r'(\d+\.?\d*)\s*Rs',
        ]
        for pattern in patterns:
            for match in re.finditer(pattern, text, re.IGNORECASE):
                try:
                    value = float(match.group(1))
                    if 1.0 <= value <= 5000.0:
                        candidates.append((match.start(), value))
                except Exception:
                    continue

        if not candidates:
            return None

        candidates.sort(key=lambda x: x[0])
        early = [v for _, v in candidates[:15]]
        return min(early) if early else None

    async def _extract_price_from_page(self, page: Page) -> Optional[float]:
        """Fallback extraction from rendered page text/content."""
        try:
            text = await page.inner_text("body")
        except Exception:
            try:
                text = await page.content()
            except Exception:
                return None
        return self._extract_price_from_text(text)
