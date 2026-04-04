import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    ElementNotInteractableException,
)
from browser_utils import create_driver, wait_and_click, wait_for, slow_type
from resume_data import answer_question, RESUME

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
        self.failed = 0
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
            log.error(f"Fatal error: {e}", exc_info=True)
        finally:
            log.info(
                f"Naukri done — Applied: {self.applied}, Skipped: {self.skipped}, Failed: {self.failed}"
            )
            self.driver.quit()

    # ── Login ──────────────────────────────────────────────────────────────
    def _login(self):
        self.driver.get(f"{self.BASE}/nlogin/login")
        time.sleep(3)

        # Try Google login button first (Edge profile already has Google session)
        try:
            google_btn = self.driver.find_element(
                By.XPATH,
                "//button[contains(@class,'google') or contains(text(),'Google')]"
                "|//div[contains(@class,'google')]"
                "|//a[contains(@href,'google')]",
            )
            google_btn.click()
            time.sleep(5)
            # If a Google account picker appears, select the right account
            try:
                accounts = self.driver.find_elements(
                    By.XPATH, f"//div[@data-email='{self.email}']"
                )
                if accounts:
                    accounts[0].click()
                    time.sleep(5)
            except Exception:
                pass
            # Check if we landed on the homepage (login success)
            if "nlogin" not in self.driver.current_url:
                log.info("Naukri login via Google successful")
                return
        except NoSuchElementException:
            log.info("Google login button not found, falling back to email/password")

        # Fallback: email + password login
        try:
            email_input = wait_for(self.driver, By.ID, "usernameField")
            slow_type(email_input, self.email)
            pwd_input = wait_for(self.driver, By.ID, "passwordField")
            slow_type(pwd_input, self.password)
            wait_and_click(self.driver, By.XPATH, "//button[@type='submit']")
            time.sleep(4)
            log.info("Naukri login via email/password successful")
        except Exception as e:
            log.error(f"Login failed: {e}")
            raise

    # ── Search & Apply (sorted by date — latest first) ─────────────────────
    def _search_and_apply(self, keywords, location):
        keyword_encoded = keywords.replace(" ", "-")
        location_encoded = location.lower().replace(" ", "-")
        page = 1

        while self.applied < self.max_apps:
            # sortBy=date ensures latest jobs first
            url = (
                f"{self.BASE}/{keyword_encoded}-jobs-in-{location_encoded}"
                f"?k={keywords}&l={location}&sortBy=date&pageNo={page}"
            )
            self.driver.get(url)
            time.sleep(4)

            # Try multiple selectors for job cards (Naukri changes DOM often)
            job_cards = []
            for sel in [
                "div.srp-jobtuple-wrapper",
                "article.jobTuple",
                "div.cust-job-tuple",
                "div.list > a.title",
            ]:
                job_cards = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if job_cards:
                    break

            if not job_cards:
                log.info(f"No more jobs on page {page} for '{keywords}' in '{location}'")
                break

            log.info(f"Page {page}: found {len(job_cards)} jobs")

            for i, card in enumerate(job_cards):
                if self.applied >= self.max_apps:
                    return
                try:
                    # Find the job link
                    try:
                        title_el = card.find_element(By.CSS_SELECTOR, "a.title")
                    except NoSuchElementException:
                        title_el = card.find_element(By.CSS_SELECTOR, "a")
                    job_url = title_el.get_attribute("href")
                    job_title = title_el.text.strip() or f"Job #{i+1}"
                    self._apply_to_job(job_url, job_title)
                except (NoSuchElementException, StaleElementReferenceException) as e:
                    log.warning(f"Skipping card {i}: {e}")
                    self.skipped += 1

            page += 1
            time.sleep(2)

    # ── Apply to a single job ──────────────────────────────────────────────
    def _apply_to_job(self, url, title):
        original_window = self.driver.current_window_handle
        self.driver.execute_script("window.open(arguments[0]);", url)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(3)

        try:
            apply_btn = self._find_apply_button()
            if apply_btn is None:
                log.info(f"No apply button: {title}")
                self.skipped += 1
                return

            btn_text = apply_btn.text.strip().lower()
            if "applied" in btn_text:
                log.info(f"Already applied: {title}")
                self.skipped += 1
                return

            apply_btn.click()
            time.sleep(3)

            # Handle any questionnaire / chatbot / popup after clicking apply
            self._handle_apply_popup()

            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {title}")

        except Exception as e:
            log.warning(f"Could not apply to '{title}': {e}")
            self.failed += 1
        finally:
            self.driver.close()
            self.driver.switch_to.window(original_window)
            time.sleep(1)

    def _find_apply_button(self):
        selectors = [
            "//button[contains(translate(text(),'APLY','aply'),'apply')]",
            "//button[contains(@class,'apply')]",
            "//button[@id='apply-button']",
            "//button[contains(@class,'chatbot-apply')]",
            "//a[contains(text(),'Apply on company site')]",
        ]
        for sel in selectors:
            try:
                return self.driver.find_element(By.XPATH, sel)
            except NoSuchElementException:
                continue
        return None

    # ── Handle post-apply popups / questionnaires ──────────────────────────
    def _handle_apply_popup(self):
        for attempt in range(5):
            time.sleep(2)
            if self._answer_visible_questions():
                continue
            if self._click_next_or_submit():
                continue
            break

    def _answer_visible_questions(self):
        answered = False
        # Text inputs
        for inp in self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input[type='number'], input[type='tel']"):
            try:
                if inp.is_displayed() and not inp.get_attribute("value"):
                    label = self._get_label_for(inp)
                    if label:
                        ans = answer_question(label)
                        inp.clear()
                        inp.send_keys(ans)
                        answered = True
                        log.info(f"  Answered '{label}' → '{ans}'")
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # Textareas
        for ta in self.driver.find_elements(By.CSS_SELECTOR, "textarea"):
            try:
                if ta.is_displayed() and not ta.get_attribute("value"):
                    label = self._get_label_for(ta)
                    if label:
                        ans = answer_question(label)
                        ta.clear()
                        ta.send_keys(ans)
                        answered = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # Dropdowns
        for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
            try:
                if sel_el.is_displayed():
                    select = Select(sel_el)
                    if select.first_selected_option.get_attribute("value") in ("", "0", "-1"):
                        label = self._get_label_for(sel_el)
                        ans = answer_question(label) if label else RESUME["experience_years"]
                        for opt in select.options:
                            if ans.lower() in opt.text.lower():
                                select.select_by_visible_text(opt.text)
                                answered = True
                                break
                        else:
                            if len(select.options) > 1:
                                select.select_by_index(1)
                                answered = True
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass

        # Radio buttons — pick first option if none selected
        radio_groups = {}
        for rb in self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            try:
                name = rb.get_attribute("name")
                if name and name not in radio_groups:
                    radio_groups[name] = rb
            except StaleElementReferenceException:
                pass
        for name, rb in radio_groups.items():
            try:
                if rb.is_displayed() and not rb.is_selected():
                    # Check if any in group is selected
                    group = self.driver.find_elements(By.CSS_SELECTOR, f"input[name='{name}']")
                    if not any(r.is_selected() for r in group):
                        group[0].click()
                        answered = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        return answered

    def _get_label_for(self, element):
        try:
            el_id = element.get_attribute("id")
            if el_id:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{el_id}']")
                if labels:
                    return labels[0].text.strip()
        except Exception:
            pass
        try:
            parent = element.find_element(By.XPATH, "./..")
            label = parent.find_element(By.TAG_NAME, "label")
            return label.text.strip()
        except Exception:
            pass
        try:
            placeholder = element.get_attribute("placeholder")
            if placeholder:
                return placeholder
        except Exception:
            pass
        try:
            aria = element.get_attribute("aria-label")
            if aria:
                return aria
        except Exception:
            pass
        return ""

    def _click_next_or_submit(self):
        for xpath in [
            "//button[contains(text(),'Submit')]",
            "//button[contains(text(),'submit')]",
            "//button[contains(text(),'Next')]",
            "//button[contains(text(),'next')]",
            "//button[contains(text(),'Continue')]",
            "//button[contains(text(),'Save')]",
            "//button[contains(text(),'Apply')]",
            "//input[@type='submit']",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    return True
            except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                continue
        return False
