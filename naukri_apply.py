import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from browser_utils import create_driver, wait_and_click, wait_for, slow_type

log = logging.getLogger(__name__)


class NaukriApplier:
    BASE = "https://www.naukri.com"

    def __init__(self, email, password, keywords, locations, max_apps):
        self.email = email
        self.password = password
        self.keywords = keywords if isinstance(keywords, list) else [keywords]
        self.locations = locations if isinstance(locations, list) else [locations]
        self.max_apps = max_apps
        self.applied = 0
        self.skipped = 0
        self.driver = None

    def run(self):
        self.driver = create_driver()
        try:
            self._login()
            for kw in self.keywords:
                for loc in self.locations:
                    if self.applied >= self.max_apps:
                        return
                    log.info(f"Searching: '{kw}' in '{loc}'")
                    self._search_and_apply(kw, loc)
        except Exception as e:
            log.error(f"Fatal error: {e}")
        finally:
            log.info(f"Naukri done — Applied: {self.applied}, Skipped: {self.skipped}")
            self.driver.quit()

    def _login(self):
        self.driver.get(f"{self.BASE}/nlogin/login")
        time.sleep(2)
        email_input = wait_for(self.driver, By.ID, "usernameField")
        slow_type(email_input, self.email)
        pwd_input = wait_for(self.driver, By.ID, "passwordField")
        slow_type(pwd_input, self.password)
        wait_and_click(self.driver, By.XPATH, "//button[@type='submit']")
        time.sleep(3)
        log.info("Naukri login successful")

    def _search_and_apply(self, keywords, location):
        keyword_encoded = keywords.replace(" ", "-")
        location_encoded = location.lower().replace(" ", "-")
        page = 1

        while self.applied < self.max_apps:
            url = f"{self.BASE}/{keyword_encoded}-jobs-in-{location_encoded}?k={keywords}&l={location}&experience=&pageNo={page}"
            self.driver.get(url)
            time.sleep(3)

            job_cards = self.driver.find_elements(By.CSS_SELECTOR, "article.jobTuple")
            if not job_cards:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.srp-jobtuple-wrapper")
            if not job_cards:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, "div.cust-job-tuple")

            if not job_cards:
                log.info(f"No more jobs found on page {page}")
                break

            log.info(f"Page {page}: found {len(job_cards)} jobs")

            for i, card in enumerate(job_cards):
                if self.applied >= self.max_apps:
                    return
                try:
                    title_el = card.find_element(By.CSS_SELECTOR, "a.title")
                    job_url = title_el.get_attribute("href")
                    job_title = title_el.text.strip()
                    self._apply_to_job(job_url, job_title)
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    log.warning(f"Skipping card {i}: {e}")
                    self.skipped += 1

            page += 1

    def _apply_to_job(self, url, title):
        original_window = self.driver.current_window_handle
        self.driver.execute_script("window.open(arguments[0]);", url)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(2)

        try:
            # Look for apply button variants
            apply_btn = None
            for selector in [
                "//button[contains(text(),'Apply')]",
                "//button[contains(@class,'apply-button')]",
                "//button[@id='apply-button']",
                "//a[contains(text(),'Apply on company site')]",
            ]:
                try:
                    apply_btn = self.driver.find_element(By.XPATH, selector)
                    break
                except NoSuchElementException:
                    continue

            if apply_btn is None:
                log.info(f"No apply button for: {title}")
                self.skipped += 1
                return

            # Check if already applied
            btn_text = apply_btn.text.strip().lower()
            if "applied" in btn_text:
                log.info(f"Already applied: {title}")
                self.skipped += 1
                return

            apply_btn.click()
            time.sleep(2)

            # Handle chatbot / questionnaire popup — try to submit if present
            self._handle_apply_popup()

            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {title}")

        except (ElementClickInterceptedException, TimeoutException) as e:
            log.warning(f"Could not apply to {title}: {e}")
            self.skipped += 1
        finally:
            self.driver.close()
            self.driver.switch_to.window(original_window)
            time.sleep(1)

    def _handle_apply_popup(self):
        """Try to handle Naukri's post-click apply popups/chatbot."""
        try:
            # Sometimes Naukri shows a chatbot or questionnaire after clicking apply
            submit_btns = self.driver.find_elements(
                By.XPATH, "//button[contains(text(),'Submit')]"
            )
            if submit_btns:
                submit_btns[0].click()
                time.sleep(1)
        except Exception:
            pass
