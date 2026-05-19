import asyncio
import logging
from datetime import date, timedelta

from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

logger = logging.getLogger(__name__)

BASE_URL = "https://instante.justice.md/ro/hotaririle-instantei"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/124.0.0.0 Safari/537.36"
)


async def scrape_decisions(target_date: date | None = None) -> list[dict]:
    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    date_str = target_date.strftime("%d.%m.%Y")
    logger.info(f"Scraping decisions for date: {date_str}")
    decisions = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=USER_AGENT,
            viewport={"width": 1280, "height": 900},
            locale="ro-RO",
        )
        page = await context.new_page()
        page.set_default_timeout(30_000)

        try:
            await page.goto(BASE_URL, wait_until="domcontentloaded")
            await page.wait_for_load_state("networkidle")
            logger.info("Page loaded")

            await _apply_filters(page, date_str)

            page_num = 1
            while True:
                logger.info(f"Extracting page {page_num}")
                rows = await _extract_table_rows(page)
                decisions.extend(rows)
                logger.info(f"  → {len(rows)} rows on page {page_num}")
                if not await _go_next_page(page):
                    break
                page_num += 1

        except PlaywrightTimeout as exc:
            logger.error(f"Timeout while scraping: {exc}")
            await _save_debug_screenshot(page)
        except Exception as exc:
            logger.error(f"Unexpected scraping error: {exc}")
            await _save_debug_screenshot(page)
        finally:
            await browser.close()

    logger.info(f"Total decisions scraped: {len(decisions)}")
    return decisions


async def _apply_filters(page, date_str: str) -> None:
    # --- Date "from" filter ---
    date_from = await _find_date_input(page, ["de la", "data de", "date_from", "dateFrom", "DataDe", "StartDate"])
    if date_from:
        await date_from.triple_click()
        await date_from.fill(date_str)
        logger.info(f"Set date-from to {date_str}")
    else:
        logger.warning("Could not find date-from input")

    # --- Date "to" filter ---
    date_to = await _find_date_input(page, ["pana la", "până la", "date_to", "dateTo", "DataPana", "EndDate"])
    if date_to:
        await date_to.triple_click()
        await date_to.fill(date_str)
        logger.info(f"Set date-to to {date_str}")
    else:
        # Fall back: second date input on page
        inputs = await page.query_selector_all("input[type='date'], input[type='text'][placeholder*='data'], input[type='text'][placeholder*='Data']")
        if len(inputs) >= 2:
            await inputs[1].triple_click()
            await inputs[1].fill(date_str)
            logger.info(f"Set date-to (fallback) to {date_str}")

    # --- Case type filter: Penal ---
    await _select_case_type_penal(page)

    # --- Submit search ---
    await _click_search(page)
    await page.wait_for_load_state("networkidle")


async def _find_date_input(page, hints: list[str]):
    # Try by label text proximity
    for hint in hints:
        # Look for input near a label containing hint text (case-insensitive)
        el = await page.query_selector(
            f"input[name*='{hint}'], input[id*='{hint}'], input[placeholder*='{hint}']"
        )
        if el:
            return el
    # Try generic date inputs in order
    inputs = await page.query_selector_all(
        "input[type='date'], "
        "input[class*='date'], "
        "input[id*='date'], input[id*='Date'], "
        "input[name*='date'], input[name*='Date']"
    )
    if inputs:
        return inputs[0]
    return None


async def _select_case_type_penal(page) -> None:
    # Strategy 1: select dropdown containing "Penal" option
    selects = await page.query_selector_all("select")
    for sel in selects:
        options = await sel.query_selector_all("option")
        for opt in options:
            text = (await opt.text_content() or "").strip()
            if "penal" in text.lower():
                value = await opt.get_attribute("value") or text
                await sel.select_option(value=value)
                logger.info(f"Selected case type: {text}")
                return

    # Strategy 2: checkbox or radio with label "Penal"
    labels = await page.query_selector_all("label")
    for label in labels:
        text = (await label.text_content() or "").strip()
        if "penal" in text.lower():
            for_ = await label.get_attribute("for")
            if for_:
                inp = await page.query_selector(f"#{for_}")
                if inp:
                    await inp.click()
                    logger.info(f"Clicked Penal label/checkbox")
                    return
            # click the label itself (may toggle adjacent input)
            await label.click()
            logger.info("Clicked Penal label directly")
            return

    logger.warning("Could not find Penal case type filter — will scrape all types and filter locally")


async def _click_search(page) -> None:
    # Look for a search/apply button
    for selector in [
        "button[type='submit']",
        "input[type='submit']",
        "button:has-text('Caută')",
        "button:has-text('Căutare')",
        "button:has-text('Aplică')",
        "button:has-text('Filtrează')",
        "button:has-text('Search')",
        "a:has-text('Caută')",
    ]:
        btn = await page.query_selector(selector)
        if btn:
            await btn.click()
            logger.info(f"Clicked search button: {selector}")
            return
    logger.warning("Search button not found — results may already be showing")


async def _extract_table_rows(page) -> list[dict]:
    rows = []

    # Wait for a results table to appear
    try:
        await page.wait_for_selector("table tbody tr, .result-row, .hotarire-row", timeout=15_000)
    except PlaywrightTimeout:
        logger.warning("No result rows found on page")
        return rows

    # Try standard HTML table first
    table_rows = await page.query_selector_all("table tbody tr")
    if table_rows:
        headers = await _extract_table_headers(page)
        for tr in table_rows:
            cells = await tr.query_selector_all("td")
            if not cells:
                continue
            cell_texts = [((await c.inner_text()) or "").strip() for c in cells]

            # Try to get a link from any cell
            link = None
            for cell in cells:
                a = await cell.query_selector("a[href]")
                if a:
                    href = await a.get_attribute("href")
                    if href:
                        link = href if href.startswith("http") else f"https://instante.justice.md{href}"
                        break

            row = _build_row_dict(headers, cell_texts, link)
            # Only include penal cases (filter locally as fallback)
            tip = row.get("tip_dosar", row.get("tip_cauza", row.get("tip", ""))).lower()
            if tip and "penal" not in tip:
                continue
            rows.append(row)
        return rows

    # Fallback: div-based layout
    divs = await page.query_selector_all(".result-row, .hotarire-row, .decision-row")
    for div in divs:
        text = ((await div.inner_text()) or "").strip()
        link_el = await div.query_selector("a[href]")
        link = None
        if link_el:
            href = await link_el.get_attribute("href")
            link = href if href and href.startswith("http") else f"https://instante.justice.md{href}" if href else None
        rows.append({"raw_text": text, "link": link})

    return rows


async def _extract_table_headers(page) -> list[str]:
    headers = []
    ths = await page.query_selector_all("table thead th, table thead td")
    for th in ths:
        text = ((await th.inner_text()) or "").strip().lower()
        # Normalize to snake_case key
        key = (
            text
            .replace("ă", "a").replace("â", "a").replace("î", "i")
            .replace("ș", "s").replace("ț", "t").replace("ş", "s").replace("ţ", "t")
            .replace(" ", "_").replace(".", "").replace("/", "_")
        )
        headers.append(key or f"col_{len(headers)}")
    return headers


def _build_row_dict(headers: list[str], cells: list[str], link: str | None) -> dict:
    row: dict = {}
    for i, val in enumerate(cells):
        key = headers[i] if i < len(headers) else f"col_{i}"
        row[key] = val

    # Normalize common field names regardless of column order
    _normalize_field(row, "nr_dosar", ["nr_dosar", "nr", "dosar", "numar_dosar", "numar"])
    _normalize_field(row, "data", ["data", "data_pronuntarii", "data_hotararii", "data_emiterii"])
    _normalize_field(row, "instanta", ["instanta", "judecatoria", "curtea", "tribunal"])
    _normalize_field(row, "judecator", ["judecator", "judecatorul", "complet"])
    _normalize_field(row, "tip_dosar", ["tip_dosar", "tip_cauza", "tip", "categorie"])
    _normalize_field(row, "solutie", ["solutie", "dispozitiv", "hotarare", "rezolutie"])

    if link:
        row["link"] = link
    return row


def _normalize_field(row: dict, canonical: str, aliases: list[str]) -> None:
    if canonical in row:
        return
    for alias in aliases:
        if alias in row:
            row[canonical] = row[alias]
            return


async def _go_next_page(page) -> bool:
    for selector in [
        "a[aria-label='Next'], a[aria-label='Următoarea']",
        ".pagination .next:not(.disabled) a",
        "li.next:not(.disabled) a",
        "a:has-text('Următoarea')",
        "a:has-text('»')",
        "[data-page='next']",
    ]:
        btn = await page.query_selector(selector)
        if btn:
            is_disabled = await btn.get_attribute("class") or ""
            if "disabled" in is_disabled:
                return False
            await btn.click()
            await page.wait_for_load_state("networkidle")
            return True
    return False


async def _save_debug_screenshot(page) -> None:
    try:
        await page.screenshot(path="debug_screenshot.png", full_page=True)
        logger.info("Debug screenshot saved: debug_screenshot.png")
    except Exception:
        pass


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    results = asyncio.run(scrape_decisions())
    for d in results:
        print(d)
