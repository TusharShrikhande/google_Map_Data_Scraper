from __future__ import annotations

import os
import re
import time
from datetime import datetime
from urllib.parse import quote_plus

import pandas as pd

from selenium import webdriver
from selenium.common.exceptions import (
    NoSuchElementException,
    StaleElementReferenceException,
    TimeoutException,
    WebDriverException,
)
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


# =========================================================
# SETTINGS
# =========================================================

WAIT_TIME = 20

SCROLL_WAIT = 2

MAX_UNCHANGED_ROUNDS = 8

MAX_SCROLL_ROUNDS = 500


class ScrapeCancelled(Exception):
    """Raised when the user requests that a scrape stop."""


def check_cancelled(cancel_event):
    if cancel_event and cancel_event.is_set():
        raise ScrapeCancelled("Scraping stopped by user.")


# =========================================================
# CLEAN TEXT
# =========================================================

def clean_text(value):

    if value is None:
        return ""

    value = str(value)

    value = re.sub(r"\s+", " ", value)

    return value.strip()


# =========================================================
# SAFE FILENAME
# =========================================================

def safe_filename(text):

    text = clean_text(text)

    text = re.sub(
        r'[<>:"/\\|?*]',
        "_",
        text,
    )

    text = re.sub(
        r"\s+",
        "_",
        text,
    )

    return text[:100]


# =========================================================
# PROGRESS HELPER
# =========================================================

def send_progress(
    callback,
    message,
    current=0,
    total=0,
    results=None,
):

    print(
        f"[PROGRESS] {message} | "
        f"{current}/{total if total else '?'}"
    )

    if callback:

        try:

            callback(
                message,
                current,
                total,
                results,
            )

        except TypeError:

            # Compatibility with older callback
            callback(
                message,
                current,
                total,
            )


# =========================================================
# CREATE DRIVER
# =========================================================

def create_driver():

    options = webdriver.ChromeOptions()

    options.add_argument("--start-maximized")

    options.add_argument("--lang=en-US")

    options.add_argument("--disable-notifications")

    options.add_argument("--disable-popup-blocking")

    options.add_argument("--disable-infobars")

    options.add_argument("--disable-blink-features=AutomationControlled")

    options.add_experimental_option(
        "excludeSwitches",
        ["enable-automation"],
    )

    options.add_experimental_option(
        "useAutomationExtension",
        False,
    )

    driver = webdriver.Chrome(
        options=options
    )

    driver.set_page_load_timeout(60)

    return driver


# =========================================================
# GET ELEMENT TEXT
# =========================================================

def get_element_text(
    driver,
    selectors,
):

    if isinstance(selectors, str):

        selectors = [selectors]

    for selector in selectors:

        try:

            element = driver.find_element(
                By.CSS_SELECTOR,
                selector,
            )

            text = clean_text(
                element.text
            )

            if text:

                return text

        except NoSuchElementException:

            continue

        except Exception:

            continue

    return ""


# =========================================================
# GET ATTRIBUTE
# =========================================================

def get_element_attribute(
    driver,
    selectors,
    attribute,
):

    if isinstance(selectors, str):

        selectors = [selectors]

    for selector in selectors:

        try:

            element = driver.find_element(
                By.CSS_SELECTOR,
                selector,
            )

            value = element.get_attribute(
                attribute
            )

            if value:

                return clean_text(value)

        except NoSuchElementException:

            continue

        except Exception:

            continue

    return ""


# =========================================================
# COLLECT GOOGLE MAPS LINKS
# =========================================================

def collect_listing_links(
    driver,
    search_query,
    max_results,
    progress_callback=None,
    cancel_event=None,
):

    search_url = (
        "https://www.google.com/maps/search/"
        + quote_plus(search_query)
    )

    send_progress(
        progress_callback,
        "Opening Google Maps...",
        0,
        max_results if isinstance(max_results, int) else 0,
    )

    print()
    print("Google Maps URL:")
    print(search_url)
    print()

    check_cancelled(cancel_event)
    driver.get(search_url)
    check_cancelled(cancel_event)

    send_progress(
        progress_callback,
        "Google Maps loaded.",
        0,
        max_results if isinstance(max_results, int) else 0,
    )

    if cancel_event and cancel_event.wait(5):
        check_cancelled(cancel_event)
    check_cancelled(cancel_event)

    # -----------------------------------------
    # WAIT FOR RESULTS
    # -----------------------------------------

    try:

        WebDriverWait(
            driver,
            WAIT_TIME,
        ).until(

            lambda d: (
                check_cancelled(cancel_event)
                or len(
                    d.find_elements(
                        By.CSS_SELECTOR,
                        "a.hfpxzc",
                    )
                ) > 0
            )

        )

    except TimeoutException:

        # Try alternate selectors
        try:

            WebDriverWait(
                driver,
                10,
            ).until(

                lambda d: (
                    check_cancelled(cancel_event)
                    or len(
                        d.find_elements(
                            By.CSS_SELECTOR,
                            'div[role="feed"] a[href*="/maps/place/"]',
                        )
                    ) > 0
                )

            )

        except TimeoutException:

            raise RuntimeError(
                "Google Maps results did not load. "
                "Check your internet connection, "
                "Google Maps access, or browser window."
            )

    # -----------------------------------------
    # FIND FEED
    # -----------------------------------------

    try:

        feed = driver.find_element(
            By.CSS_SELECTOR,
            'div[role="feed"]',
        )

    except NoSuchElementException:

        feed = None

    links = set()

    unchanged_rounds = 0

    last_count = 0

    scroll_round = 0

    # -----------------------------------------
    # SCROLL
    # -----------------------------------------

    while True:

        scroll_round += 1
        check_cancelled(cancel_event)

        # -------------------------------------
        # COLLECT LINKS
        # -------------------------------------

        elements = driver.find_elements(
            By.CSS_SELECTOR,
            "a.hfpxzc",
        )

        for element in elements:

            try:

                href = element.get_attribute(
                    "href"
                )

                if href and "/maps/place/" in href:

                    links.add(href)

            except StaleElementReferenceException:

                continue

            except Exception:

                continue

        # -------------------------------------
        # ALTERNATIVE LINK SELECTOR
        # -------------------------------------

        if not links:

            elements = driver.find_elements(
                By.CSS_SELECTOR,
                'div[role="feed"] a[href*="/maps/place/"]',
            )

            for element in elements:

                try:

                    href = element.get_attribute(
                        "href"
                    )

                    if href:

                        links.add(href)

                except Exception:

                    continue

        # -------------------------------------
        # RESULT LIMIT
        # -------------------------------------

        if max_results != "all":

            if len(links) >= max_results:

                break

        # -------------------------------------
        # PROGRESS
        # -------------------------------------

        send_progress(
            progress_callback,
            f"Finding businesses... {len(links)} found",
            len(links),
            max_results if isinstance(max_results, int) else len(links),
        )

        # -------------------------------------
        # CHECK IF NEW RESULTS APPEARED
        # -------------------------------------

        if len(links) == last_count:

            unchanged_rounds += 1

        else:

            unchanged_rounds = 0

            last_count = len(links)

        # -------------------------------------
        # STOP IF NOTHING NEW
        # -------------------------------------

        if unchanged_rounds >= MAX_UNCHANGED_ROUNDS:

            break

        if scroll_round >= MAX_SCROLL_ROUNDS:

            break

        # -------------------------------------
        # SCROLL
        # -------------------------------------

        try:

            if feed:

                driver.execute_script(
                    """
                    arguments[0].scrollTop =
                    arguments[0].scrollHeight;
                    """,
                    feed,
                )

            else:

                driver.execute_script(
                    """
                    window.scrollTo(
                        0,
                        document.body.scrollHeight
                    );
                    """
                )

        except Exception:

            pass

        if cancel_event and cancel_event.wait(SCROLL_WAIT):
            check_cancelled(cancel_event)

    # -----------------------------------------
    # LIMIT LINKS
    # -----------------------------------------

    links = list(links)

    if max_results != "all":

        links = links[:max_results]

    send_progress(
        progress_callback,
        f"Found {len(links)} businesses.",
        0,
        len(links),
    )

    return links


# =========================================================
# SCRAPE SINGLE BUSINESS
# =========================================================

def scrape_business(
    driver,
    url,
    cancel_event=None,
):

    check_cancelled(cancel_event)
    driver.get(url)
    check_cancelled(cancel_event)

    if cancel_event and cancel_event.wait(2):
        check_cancelled(cancel_event)
    check_cancelled(cancel_event)

    # -----------------------------------------
    # BUSINESS NAME
    # -----------------------------------------

    name = get_element_text(
        driver,
        "h1",
    )

    # -----------------------------------------
    # CATEGORY
    # -----------------------------------------

    category = get_element_text(
        driver,
        [
            'button[jsaction*="category"]',
            'button[class*="DkEaL"]',
        ],
    )

    # -----------------------------------------
    # PHONE
    # -----------------------------------------

    phone = get_element_attribute(
        driver,
        'button[data-item-id^="phone:tel:"]',
        "aria-label",
    )

    if phone:

        phone = re.sub(
            r"^Phone:\s*",
            "",
            phone,
            flags=re.IGNORECASE,
        )

    else:

        phone = get_element_text(
            driver,
            'button[data-item-id^="phone:tel:"]',
        )

        phone = re.sub(
            r"^Phone:\s*",
            "",
            phone,
            flags=re.IGNORECASE,
        )

    # -----------------------------------------
    # ADDRESS
    # -----------------------------------------

    address = get_element_text(
        driver,
        'button[data-item-id="address"]',
    )

    address = re.sub(
        r"^Address:\s*",
        "",
        address,
        flags=re.IGNORECASE,
    )

    # -----------------------------------------
    # WEBSITE
    # -----------------------------------------

    website = get_element_attribute(
        driver,
        'a[data-item-id="authority"]',
        "href",
    )

    # -----------------------------------------
    # LOCATION
    # -----------------------------------------

    location = get_element_text(
        driver,
        'button[data-item-id="oloc"]',
    )

    # -----------------------------------------
    # RATING
    # -----------------------------------------

    rating = get_element_text(
        driver,
        'div.F7nice span[aria-hidden="true"]',
    )

    # -----------------------------------------
    # REVIEWS
    # -----------------------------------------

    reviews = ""

    try:

        review_element = driver.find_element(
            By.CSS_SELECTOR,
            'div.F7nice span[aria-label*="review"]',
        )

        reviews = (
            review_element.get_attribute(
                "aria-label"
            )
            or review_element.text
        )

        reviews = clean_text(reviews)

    except Exception:

        reviews = ""

    # -----------------------------------------
    # HOURS / STATUS
    # -----------------------------------------

    hours = get_element_text(
        driver,
        'div[role="region"]',
    )

    # -----------------------------------------
    # CURRENT URL
    # -----------------------------------------

    maps_url = driver.current_url

    return {
        "Business Name": name,
        "Category": category,
        "Phone": phone,
        "Address": address,
        "Website": website,
        "Location": location,
        "Rating": rating,
        "Reviews": reviews,
        "Hours / Status": hours,
        "Google Maps URL": maps_url,
    }


# =========================================================
# MAIN SCRAPER
# =========================================================

def run_scraper(
    search_query,
    max_results,
    progress_callback=None,
    export_dir="exports",
    cancel_event=None,
):

    driver = None

    all_results = []

    try:

        # -----------------------------------------
        # START
        # -----------------------------------------

        send_progress(
            progress_callback,
            "Preparing Chrome...",
            0,
            max_results if isinstance(max_results, int) else 0,
        )

        check_cancelled(cancel_event)

        # -----------------------------------------
        # CREATE CHROME
        # -----------------------------------------

        send_progress(
            progress_callback,
            "Starting Chrome...",
            0,
            max_results if isinstance(max_results, int) else 0,
        )

        driver = create_driver()
        check_cancelled(cancel_event)

        send_progress(
            progress_callback,
            "Chrome started successfully.",
            0,
            max_results if isinstance(max_results, int) else 0,
        )

        # -----------------------------------------
        # COLLECT LINKS
        # -----------------------------------------

        links = collect_listing_links(
            driver=driver,
            search_query=search_query,
            max_results=max_results,
            progress_callback=progress_callback,
            cancel_event=cancel_event,
        )

        if not links:

            raise RuntimeError(
                "No Google Maps businesses were found."
            )

        # -----------------------------------------
        # SCRAPE EACH BUSINESS
        # -----------------------------------------

        total = len(links)

        send_progress(
            progress_callback,
            f"Starting business details scraping... 0/{total}",
            0,
            total,
        )

        for index, url in enumerate(
            links,
            start=1,
        ):

            try:

                check_cancelled(cancel_event)

                send_progress(
                    progress_callback,
                    f"Scraping business {index}/{total}...",
                    index - 1,
                    total,
                    all_results[-100:],
                )

                result = scrape_business(
                    driver,
                    url,
                    cancel_event=cancel_event,
                )

                # Only keep useful listings
                if result.get("Business Name"):

                    all_results.append(result)

                send_progress(
                    progress_callback,
                    f"Scraped {len(all_results)} businesses.",
                    index,
                    total,
                    all_results[-100:],
                )

                check_cancelled(cancel_event)

            except Exception as e:

                check_cancelled(cancel_event)

                print(
                    f"[WARNING] Failed listing "
                    f"{index}: {e}"
                )

                continue

        # -----------------------------------------
        # NO RESULTS
        # -----------------------------------------

        if not all_results:

            raise RuntimeError(
                "Businesses were found, but no business details "
                "could be extracted."
            )

        check_cancelled(cancel_event)

        # -----------------------------------------
        # CREATE EXPORT DIRECTORY
        # -----------------------------------------

        os.makedirs(
            export_dir,
            exist_ok=True,
        )

        # -----------------------------------------
        # CREATE DATAFRAME
        # -----------------------------------------

        dataframe = pd.DataFrame(
            all_results
        )

        # -----------------------------------------
        # FILE NAME
        # -----------------------------------------

        timestamp = datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )

        query_name = safe_filename(
            search_query
        )

        filename = (
            f"{query_name}_{timestamp}.csv"
        )

        filepath = os.path.join(
            export_dir,
            filename,
        )

        # -----------------------------------------
        # SAVE CSV
        # -----------------------------------------

        dataframe.to_csv(
            filepath,
            index=False,
            encoding="utf-8-sig",
        )

        # -----------------------------------------
        # COMPLETE
        # -----------------------------------------

        send_progress(
            progress_callback,
            f"Completed. {len(all_results)} businesses saved.",
            len(all_results),
            len(all_results),
            all_results[-100:],
        )

        print()
        print("=" * 70)
        print("SCRAPING COMPLETED")
        print("=" * 70)
        print(f"Businesses: {len(all_results)}")
        print(f"CSV: {filepath}")
        print("=" * 70)
        print()

        return {
            "count": len(all_results),
            "filename": filename,
            "results": all_results[-100:],
        }

    except WebDriverException as e:

        print()
        print("=" * 70)
        print("CHROME / SELENIUM ERROR")
        print("=" * 70)
        print(str(e))
        print("=" * 70)
        print()

        raise RuntimeError(
            "Chrome/Selenium could not start or communicate with Chrome. "
            f"Details: {str(e)}"
        )

    except Exception as e:

        print()
        print("=" * 70)
        print("SCRAPER ERROR")
        print("=" * 70)
        print(str(e))
        print("=" * 70)
        print()

        raise

    finally:

        # -----------------------------------------
        # ALWAYS CLOSE CHROME
        # -----------------------------------------

        if driver:

            try:

                driver.quit()

                print(
                    "[INFO] Chrome closed."
                )

            except Exception:

                pass
