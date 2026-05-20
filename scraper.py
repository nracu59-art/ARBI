import asyncio
import logging
import os
from datetime import date, timedelta
from urllib.parse import urlencode

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

BASE_URL = "https://instante.justice.md/ro/hotaririle-instantei"

# Allow overriding the Chromium binary via env var (useful in constrained envs)
CHROMIUM_EXECUTABLE = os.getenv(
    "PLAYWRIGHT_CHROMIUM_EXECUTABLE_PATH",
    "/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell"
    if os.path.exists("/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell")
    else None
)
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)

# Tipul_dosarului=3 = Penal (from URL params observed on site)
TIPUL_PENAL = "3"
# Rows per page — try to set to 100 to minimize page loads
ROWS_PER_PAGE = 100

# Exact column order as shown in the table (0-indexed)
COLUMNS = [
    "instanta_judecatoreasca",
    "numarul_dosarului",
    "denumirea_dosarului",
    "data_pronuntarii",
    "data_inregistrarii",
    "data_publicarii",
    "tipul_dosarului",
    "tematica_dosarului",
    "judecator",
    "act_judecatoresc_url",  # PDF link column — store URL, don't download
]


async def scrape_decisions(target_date: date | None = None) -> list[dict]:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.strftime("%Y-%m-%d")
    logger.info(f"Scraping penal decisions for date: {date_str}")

    params = {
        "Instance": "All",
        "Numarul_dosarului": "",
        "Denumirea_dosarului": "",
        "date": date_str,
        "Tematica_dosarului": "",
        "Tipul_dosarului": TIPUL_PENAL,
    }
    url = f"{BASE_URL}?{urlencode(params)}"
    decisions = []

    async with async_playwright() as p:
        launch_opts = {"headless": True}
        if CHROMIUM_EXECUTABLE:
            launch_opts["executable_path"] = CHROMIUM_EXECUTABLE
            logger.info(f"Using Chromium: {CHROMIUM_EXECUTABLE}")
        browser = await p.chromium.launch(**launch_opts)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1440, "height": 900},
            locale="ro-RO",
            ignore_https_errors=True,
        )
        page = await context.new_page()
        page.set_default_timeout(30_000)

        try:
            logger.info(f"Loading: {url}")
            await page.goto(url, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")

            # Increase rows per page to speed up scraping
            await _set_rows_per_page(page, ROWS_PER_PAGE)

            # Scrape all pages
            page_num = 1
            while True:
                logger.info(f"Extracting page {page_num}")
                await page.wait_for_selector("table tbody tr", timeout=15_000)
                rows = await _extract_rows(page)
                decisions.extend(rows)
                logger.info(f"  → {len(rows)} rows (total so far: {len(decisions)})")
                if not await _go_next_page(page):
                    break
                page_num += 1

        except PlaywrightTimeout as exc:
            logger.error(f"Timeout: {exc}")
            await _save_screenshot(page, "debug_screenshot.png")
        except Exception as exc:
            logger.error(f"Scraping error: {exc}", exc_info=True)
            await _save_screenshot(page, "debug_screenshot.png")
        finally:
            await browser.close()

    logger.info(f"Total decisions scraped: {len(decisions)}")
    return decisions


async def _set_rows_per_page(page, count: int) -> None:
    try:
        result = await page.evaluate("""
            () => {
                const selects = document.querySelectorAll('select');
                for (const sel of selects) {
                    const opts = Array.from(sel.options).filter(o => /^\\d+$/.test(o.value));
                    if (opts.length > 0) {
                        const max = opts.reduce((a, b) => parseInt(a.value) > parseInt(b.value) ? a : b);
                        sel.value = max.value;
                        sel.dispatchEvent(new Event('change', {bubbles: true}));
                        return max.value;
                    }
                }
                return null;
            }
        """)
        if result:
            await page.wait_for_load_state("networkidle")
            logger.info(f"Set rows per page via JS: {result}")
        else:
            logger.warning("Could not find rows-per-page select")
    except Exception as exc:
        logger.warning(f"Could not set rows per page: {exc}")


async def _extract_rows(page) -> list[dict]:
    rows = []
    trs = await page.query_selector_all("table tbody tr")
    for tr in trs:
        cells = await tr.query_selector_all("td")
        if len(cells) < 9:
            continue

        cell_texts = []
        pdf_url = None
        for i, cell in enumerate(cells):
            text = ((await cell.inner_text()) or "").strip()
            cell_texts.append(text)
            # Last column: Act judecătoresc — grab PDF href
            if i == len(cells) - 1:
                a = await cell.query_selector("a[href]")
                if a:
                    href = await a.get_attribute("href") or ""
                    if href:
                        pdf_url = href if href.startswith("http") else f"https://instante.justice.md{href}"

        row: dict = {}
        for i, col in enumerate(COLUMNS):
            if col == "act_judecatoresc_url":
                row[col] = pdf_url or ""
            elif i < len(cell_texts):
                row[col] = cell_texts[i]
            else:
                row[col] = ""

        rows.append(row)
    return rows


async def _go_next_page(page) -> bool:
    # Try standard CSS selectors
    for selector in [
        "li.next:not(.disabled) a",
        "a[aria-label='Next']",
        ".pagination a:has-text('›')",
        ".pagination a:has-text('>')",
        ".pagination a:has-text('>>')",
        ".pagination a:has-text('»')",
        "li:not(.disabled) > a[rel='next']",
    ]:
        btn = await page.query_selector(selector)
        if btn:
            parent_class = ""
            parent = await btn.evaluate_handle("el => el.parentElement")
            if parent:
                parent_class = await parent.get_attribute("class") or ""
            if "disabled" in parent_class:
                return False
            await btn.click()
            await page.wait_for_load_state("networkidle")
            return True

    # JavaScript fallback — find active page li and click the next sibling's link
    clicked = await page.evaluate("""
        () => {
            const pagers = document.querySelectorAll('.pagination, [class*="pagination"], nav ul');
            for (const pager of pagers) {
                const active = pager.querySelector('.active, [class*="active"]');
                if (!active) continue;
                let next = active.nextElementSibling;
                while (next) {
                    if (next.classList.contains('disabled')) return false;
                    const link = next.querySelector('a');
                    if (link) { link.click(); return true; }
                    next = next.nextElementSibling;
                }
            }
            return false;
        }
    """)
    if clicked:
        await page.wait_for_load_state("networkidle")
        return True

    # Last resort — click the next page number directly
    try:
        active = await page.query_selector(".pagination .active a, .pagination .active span")
        if active:
            current = int(((await active.inner_text()) or "0").strip())
            next_btn = await page.query_selector(f".pagination a:has-text('{current + 1}')")
            if next_btn:
                await next_btn.click()
                await page.wait_for_load_state("networkidle")
                return True
    except Exception:
        pass

    return False


async def _save_screenshot(page, path: str) -> None:
    try:
        await page.screenshot(path=path, full_page=True)
        logger.info(f"Debug screenshot saved: {path}")
    except Exception:
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(scrape_decisions())
    for d in results:
        print(d)
