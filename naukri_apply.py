import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select, WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
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

FAST = 1  # base wait in seconds


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
            log.info(f"Done — Applied: {self.applied}, Skipped: {self.skipped}, Failed: {self.failed}")
            self.driver.quit()

    # ── Login (skip if already logged in) ──────────────────────────────────
    def _login(self):
        self.driver.get(self.BASE)
        time.sleep(FAST * 2)

        # Check if already logged in by looking for profile/user elements
        if self._is_logged_in():
            log.info("Already logged in, skipping login")
            return

        # Go to login page
        self.driver.get(f"{self.BASE}/nlogin/login")
        time.sleep(FAST * 2)

        # Try Google Sign-In
        google_selectors = [
            "//button[contains(text(),'Sign in with Google')]",
            "//button[contains(text(),'Google')]",
            "//div[contains(text(),'Sign in with Google')]",
            "//span[contains(text(),'Sign in with Google')]",
            "//div[contains(@class,'google-login')]",
            "//button[contains(@class,'google')]",
            "//div[contains(@class,'google')]",
            "//div[@id='google-login-btn']",
        ]
        for sel in google_selectors:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed():
                    btn.click()
                    log.info(f"Clicked Google button: {sel}")
                    time.sleep(FAST * 3)

                    # Handle Google popup
                    main_win = self.driver.current_window_handle
                    if len(self.driver.window_handles) > 1:
                        for w in self.driver.window_handles:
                            if w != main_win:
                                self.driver.switch_to.window(w)
                                break
                        time.sleep(FAST * 2)
                        # Pick account
                        for asel in [
                            f"//div[@data-email='{self.email}']",
                            f"//div[contains(text(),'{self.email}')]",
                            f"//div[@data-identifier='{self.email}']",
                        ]:
                            try:
                                self.driver.find_element(By.XPATH, asel).click()
                                log.info(f"Selected Google account: {self.email}")
                                break
                            except NoSuchElementException:
                                continue
                        time.sleep(FAST * 3)
                        try:
                            self.driver.switch_to.window(main_win)
                        except Exception:
                            self.driver.switch_to.window(self.driver.window_handles[0])

                    time.sleep(FAST * 2)
                    if self._is_logged_in():
                        log.info("Google login successful")
                        return
                    break
            except (NoSuchElementException, ElementClickInterceptedException):
                continue

        # Fallback: email/password
        try:
            email_input = wait_for(self.driver, By.ID, "usernameField", timeout=5)
            slow_type(email_input, self.email)
            pwd_input = wait_for(self.driver, By.ID, "passwordField", timeout=5)
            slow_type(pwd_input, self.password)
            wait_and_click(self.driver, By.XPATH, "//button[@type='submit']", timeout=5)
            time.sleep(FAST * 2)
            log.info("Email/password login done")
        except Exception as e:
            log.error(f"Login failed: {e}")
            raise

    def _is_logged_in(self):
        for sel in [
            "div.nI-gNb-drawer__hamburger",  # hamburger menu (logged in)
            "div.nI-gNb-header__right-info",
            "a[href*='mnjuser']",
            "div.user-info",
            "span.nI-gNb-header__userName",
            "img.nI-gNb-header__userImg",
        ]:
            try:
                if self.driver.find_element(By.CSS_SELECTOR, sel).is_displayed():
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                continue
        # Also check URL — if redirected away from login
        return "nlogin" not in self.driver.current_url and "login" not in self.driver.current_url

    # ── Search & Apply (latest first) ──────────────────────────────────────
    def _search_and_apply(self, keywords, location):
        kw_enc = keywords.replace(" ", "-")
        loc_enc = location.lower().replace(" ", "-")
        page = 1

        while self.applied < self.max_apps:
            url = (
                f"{self.BASE}/{kw_enc}-jobs-in-{loc_enc}"
                f"?k={keywords}&l={location}&sortBy=date&pageNo={page}"
            )
            self.driver.get(url)
            time.sleep(FAST * 2)

            # Collect job links from the page first (avoids stale refs)
            jobs = []
            for sel in [
                "div.srp-jobtuple-wrapper a.title",
                "article.jobTuple a.title",
                "div.cust-job-tuple a.title",
                "a.title",
            ]:
                elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if elements:
                    for el in elements:
                        try:
                            href = el.get_attribute("href")
                            title = el.text.strip()
                            if href and title:
                                jobs.append((href, title))
                        except StaleElementReferenceException:
                            pass
                    break

            if not jobs:
                log.info(f"No jobs on page {page}")
                break

            log.info(f"Page {page}: {len(jobs)} jobs")

            for href, title in jobs:
                if self.applied >= self.max_apps:
                    return
                self._apply_to_job(href, title)

            page += 1

    # ── Apply to single job ────────────────────────────────────────────────
    def _apply_to_job(self, url, title):
        main_win = self.driver.current_window_handle
        self.driver.execute_script("window.open(arguments[0]);", url)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(FAST)

        try:
            apply_btn = self._find_apply_button()
            if not apply_btn:
                log.info(f"No apply btn: {title}")
                self.skipped += 1
                return

            txt = apply_btn.text.strip().lower()
            if "applied" in txt:
                log.info(f"Already applied: {title}")
                self.skipped += 1
                return

            apply_btn.click()
            time.sleep(FAST)

            # Handle popup/chatbot/questionnaire
            self._handle_popup()

            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {title}")

        except Exception as e:
            log.warning(f"Failed '{title}': {e}")
            self.failed += 1
        finally:
            self.driver.close()
            self.driver.switch_to.window(main_win)

    def _find_apply_button(self):
        for sel in [
            "//button[contains(translate(.,'APLY','aply'),'apply') and not(contains(translate(.,'APLIED','aplied'),'applied'))]",
            "//button[contains(@class,'apply')]",
            "//button[@id='apply-button']",
            "//button[contains(@id,'apply')]",
            "//a[contains(text(),'Apply on company site')]",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed():
                    return btn
            except NoSuchElementException:
                continue
        return None

    # ── Handle Naukri post-apply popup/chatbot ─────────────────────────────
    def _handle_popup(self):
        for _ in range(8):
            time.sleep(FAST)
            changed = False
            changed |= self._fill_text_fields()
            changed |= self._fill_dropdowns()
            changed |= self._fill_radio_checkbox()
            changed |= self._fill_chatbot_options()
            if self._click_action_button():
                changed = True
            if not changed:
                break

    def _fill_text_fields(self):
        filled = False
        for inp in self.driver.find_elements(By.CSS_SELECTOR,
                "input[type='text'], input[type='number'], input[type='tel'], textarea"):
            try:
                if not inp.is_displayed():
                    continue
                val = inp.get_attribute("value") or ""
                if val.strip():
                    continue
                label = self._get_label(inp)
                ans = answer_question(label)
                inp.clear()
                inp.send_keys(ans)
                filled = True
                log.info(f"  Filled '{label}' → '{ans}'")
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass
        return filled

    def _fill_dropdowns(self):
        filled = False
        # Native <select>
        for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                cur = select.first_selected_option
                if cur.get_attribute("value") not in ("", "0", "-1", "select", "Select"):
                    continue
                label = self._get_label(sel_el)
                ans = answer_question(label)
                # Try exact then partial match
                matched = False
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot and (ans.lower() == ot or ans.lower() in ot):
                        select.select_by_visible_text(opt.text)
                        matched = True
                        filled = True
                        log.info(f"  Dropdown '{label}' → '{opt.text}'")
                        break
                if not matched and len(select.options) > 1:
                    select.select_by_index(1)
                    filled = True
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass

        # Naukri custom dropdowns (div-based)
        for dd in self.driver.find_elements(By.CSS_SELECTOR,
                "div.customSelect, div.dropdownMainContainer, div[class*='dropdown'], div[class*='select']"):
            try:
                if not dd.is_displayed():
                    continue
                # Check if it has a placeholder or empty value
                dd_text = dd.text.strip().lower()
                if dd_text and dd_text not in ("select", "choose", "--select--", ""):
                    continue
                label = self._get_label(dd)
                ans = answer_question(label)
                dd.click()
                time.sleep(0.5)
                # Find options inside the dropdown
                for opt in self.driver.find_elements(By.CSS_SELECTOR,
                        "li, div.optionItem, div[class*='option'], ul li"):
                    try:
                        ot = opt.text.strip().lower()
                        if ot and (ans.lower() in ot or ot in ans.lower()):
                            opt.click()
                            filled = True
                            log.info(f"  Custom dropdown '{label}' → '{opt.text.strip()}'")
                            break
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        pass
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass
        return filled

    def _fill_radio_checkbox(self):
        filled = False
        # Radio groups
        groups = {}
        for rb in self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            try:
                name = rb.get_attribute("name")
                if name:
                    groups.setdefault(name, []).append(rb)
            except StaleElementReferenceException:
                pass

        for name, radios in groups.items():
            try:
                if any(r.is_selected() for r in radios):
                    continue
                label = self._get_label(radios[0])
                ans = answer_question(label).lower()
                # Try to match answer to radio label
                clicked = False
                for r in radios:
                    try:
                        r_label = self._get_label(r).lower()
                        if ans in r_label or r_label in ans or "yes" in r_label:
                            r.click()
                            clicked = True
                            filled = True
                            break
                    except (ElementNotInteractableException, StaleElementReferenceException):
                        pass
                if not clicked and radios:
                    try:
                        radios[0].click()
                        filled = True
                    except (ElementNotInteractableException, StaleElementReferenceException):
                        pass
            except (StaleElementReferenceException, ElementNotInteractableException):
                pass

        # Checkboxes — check unchecked ones if they seem relevant
        for cb in self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            try:
                if cb.is_displayed() and not cb.is_selected():
                    label = self._get_label(cb).lower()
                    if any(k in label for k in ["agree", "terms", "consent", "confirm", "accept"]):
                        cb.click()
                        filled = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass
        return filled

    def _fill_chatbot_options(self):
        """Handle Naukri chatbot-style popups with clickable chips/buttons for answers."""
        filled = False
        # Naukri chatbot shows options as chips/buttons
        for container_sel in [
            "div.chatbot_container", "div[class*='chatbot']", "div[class*='chat-']",
            "div.bot-body", "div[class*='questionnaire']", "div[class*='popup']",
        ]:
            containers = self.driver.find_elements(By.CSS_SELECTOR, container_sel)
            for container in containers:
                try:
                    if not container.is_displayed():
                        continue
                    # Get the question text
                    q_text = ""
                    for q_sel in ["div.msg", "div.question", "p", "span", "div.bot-msg"]:
                        try:
                            q_el = container.find_element(By.CSS_SELECTOR, q_sel)
                            q_text = q_el.text.strip()
                            if q_text:
                                break
                        except NoSuchElementException:
                            pass

                    ans = answer_question(q_text) if q_text else RESUME["total_experience"]

                    # Click matching chip/option
                    for chip_sel in [
                        "button.chip", "div.chip", "span.chip",
                        "button.option", "div.option", "a.option",
                        "button", "div.selectable",
                    ]:
                        chips = container.find_elements(By.CSS_SELECTOR, chip_sel)
                        for chip in chips:
                            try:
                                ct = chip.text.strip().lower()
                                if ct and (ans.lower() in ct or ct in ans.lower()):
                                    chip.click()
                                    filled = True
                                    log.info(f"  Chatbot '{q_text}' → '{chip.text.strip()}'")
                                    break
                            except (ElementClickInterceptedException, StaleElementReferenceException):
                                pass
                except (StaleElementReferenceException, NoSuchElementException):
                    pass
        return filled

    def _click_action_button(self):
        for xpath in [
            "//button[contains(text(),'Submit')]",
            "//button[contains(text(),'submit')]",
            "//button[contains(text(),'Next')]",
            "//button[contains(text(),'next')]",
            "//button[contains(text(),'Continue')]",
            "//button[contains(text(),'continue')]",
            "//button[contains(text(),'Save')]",
            "//button[contains(text(),'Apply')]",
            "//button[contains(text(),'Done')]",
            "//button[contains(text(),'Confirm')]",
            "//button[contains(text(),'Send')]",
            "//input[@type='submit']",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, xpath)
                if btn.is_displayed() and btn.is_enabled():
                    btn.click()
                    time.sleep(FAST)
                    return True
            except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                continue
        return False

    # ── Label extraction ───────────────────────────────────────────────────
    def _get_label(self, element):
        try:
            el_id = element.get_attribute("id")
            if el_id:
                labels = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{el_id}']")
                if labels and labels[0].text.strip():
                    return labels[0].text.strip()
        except Exception:
            pass
        # Walk up parents looking for label/text
        try:
            parent = element.find_element(By.XPATH, "./..")
            for tag in ["label", "span", "div.label", "p"]:
                try:
                    lbl = parent.find_element(By.CSS_SELECTOR, tag)
                    if lbl.text.strip():
                        return lbl.text.strip()
                except NoSuchElementException:
                    pass
            # Try grandparent
            gp = parent.find_element(By.XPATH, "./..")
            for tag in ["label", "span", "div.label", "p"]:
                try:
                    lbl = gp.find_element(By.CSS_SELECTOR, tag)
                    if lbl.text.strip():
                        return lbl.text.strip()
                except NoSuchElementException:
                    pass
        except Exception:
            pass
        for attr in ["placeholder", "aria-label", "title", "name"]:
            try:
                v = element.get_attribute(attr)
                if v:
                    return v
            except Exception:
                pass
        return ""
