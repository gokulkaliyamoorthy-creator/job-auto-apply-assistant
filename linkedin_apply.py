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


class LinkedInApplier:
    BASE = "https://www.linkedin.com"

    def __init__(self, email, password, keywords, location, max_apps):
        self.email = email
        self.password = password
        self.keywords = keywords
        self.location = location
        self.max_apps = max_apps
        self.applied = 0
        self.skipped = 0
        self.driver = None

    def run(self):
        self.driver = create_driver()
        try:
            self._login()
            self._search_and_apply()
        except Exception as e:
            log.error(f"Fatal error: {e}")
        finally:
            log.info(f"LinkedIn done — Applied: {self.applied}, Skipped: {self.skipped}")
            self.driver.quit()

    def _login(self):
        self.driver.get(f"{self.BASE}/login")
        time.sleep(2)
        email_input = wait_for(self.driver, By.ID, "username")
        slow_type(email_input, self.email)
        pwd_input = wait_for(self.driver, By.ID, "password")
        slow_type(pwd_input, self.password)
        wait_and_click(self.driver, By.XPATH, "//button[@type='submit']")
        time.sleep(5)
        # Manual CAPTCHA / 2FA pause
        if "checkpoint" in self.driver.current_url or "challenge" in self.driver.current_url:
            log.warning("CAPTCHA or 2FA detected — solve it manually in the browser")
            input("Press ENTER after you've completed verification...")
        log.info("LinkedIn login successful")

    def _search_and_apply(self):
        page = 0
        while self.applied < self.max_apps:
            start = page * 25
            url = (
                f"{self.BASE}/jobs/search/?keywords={self.keywords}"
                f"&location={self.location}&f_AL=true&start={start}"
            )
            self.driver.get(url)
            time.sleep(3)

            job_cards = self.driver.find_elements(
                By.CSS_SELECTOR, "div.job-card-container"
            )
            if not job_cards:
                job_cards = self.driver.find_elements(
                    By.CSS_SELECTOR, "li.jobs-search-results__list-item"
                )

            if not job_cards:
                log.info(f"No more jobs on page {page + 1}")
                break

            log.info(f"Page {page + 1}: found {len(job_cards)} jobs")

            for card in job_cards:
                if self.applied >= self.max_apps:
                    return
                try:
                    card.click()
                    time.sleep(2)
                    self._try_easy_apply()
                except (
                    StaleElementReferenceException,
                    ElementClickInterceptedException,
                ) as e:
                    log.warning(f"Skipping card: {e}")
                    self.skipped += 1

            page += 1

    def _try_easy_apply(self):
        try:
            easy_apply_btn = self.driver.find_element(
                By.XPATH, "//button[contains(@class,'jobs-apply-button')]"
            )
        except NoSuchElementException:
            self.skipped += 1
            return

        btn_text = easy_apply_btn.text.strip().lower()
        if "easy apply" not in btn_text:
            self.skipped += 1
            return

        job_title = "Unknown"
        try:
            job_title = self.driver.find_element(
                By.CSS_SELECTOR, "h1.t-24, h2.t-24, h1.job-details-jobs-unified-top-card__job-title"
            ).text.strip()
        except NoSuchElementException:
            pass

        easy_apply_btn.click()
        time.sleep(2)

        if self._submit_application():
            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {job_title}")
        else:
            self.skipped += 1
            log.info(f"Skipped (multi-step/questions): {job_title}")
            self._close_modal()

    def _submit_application(self):
        """Walk through Easy Apply modal pages. Returns True if submitted."""
        max_pages = 10
        for _ in range(max_pages):
            time.sleep(1)

            # Check for submit button
            submit_btns = self.driver.find_elements(
                By.XPATH, "//button[contains(@aria-label,'Submit application')]"
            )
            if submit_btns:
                submit_btns[0].click()
                time.sleep(2)
                # Dismiss post-apply modal
                self._close_modal()
                return True

            # Check for next / review button
            next_btn = None
            for label in ["Continue to next step", "Review your application"]:
                btns = self.driver.find_elements(
                    By.XPATH, f"//button[contains(@aria-label,'{label}')]"
                )
                if btns:
                    next_btn = btns[0]
                    break

            if next_btn:
                # Check for required unfilled fields — skip if any
                required_empty = self.driver.find_elements(
                    By.CSS_SELECTOR, "input[required]:not([value]), select[required] option:checked[value='']"
                )
                if required_empty:
                    return False
                next_btn.click()
                time.sleep(1)
            else:
                return False

        return False

    def _close_modal(self):
        try:
            dismiss_btns = self.driver.find_elements(
                By.XPATH,
                "//button[contains(@aria-label,'Dismiss')]"
                " | //button[contains(@aria-label,'discard')]"
                " | //button[contains(text(),'Discard')]",
            )
            for btn in dismiss_btns:
                btn.click()
                time.sleep(0.5)
        except Exception:
            pass
