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

W = 0.8  # fast wait


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
            log.error(f"Fatal: {e}", exc_info=True)
        finally:
            log.info(f"Done — Applied:{self.applied} Skipped:{self.skipped} Failed:{self.failed}")
            self.driver.quit()

    # ── Login ──────────────────────────────────────────────────────────────
    def _login(self):
        self.driver.get(self.BASE)
        time.sleep(W * 2)
        if self._is_logged_in():
            log.info("Already logged in")
            return

        self.driver.get(f"{self.BASE}/nlogin/login")
        time.sleep(W * 2)

        # Google sign-in
        for sel in [
            "//button[contains(text(),'Google')]",
            "//div[contains(text(),'Sign in with Google')]",
            "//span[contains(text(),'Google')]",
            "//div[contains(@class,'google')]",
        ]:
            try:
                btn = self.driver.find_element(By.XPATH, sel)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(W * 3)
                    main_win = self.driver.current_window_handle
                    if len(self.driver.window_handles) > 1:
                        for w in self.driver.window_handles:
                            if w != main_win:
                                self.driver.switch_to.window(w)
                                break
                        time.sleep(W * 2)
                        for asel in [
                            f"//div[@data-email='{self.email}']",
                            f"//div[contains(text(),'{self.email}')]",
                            f"//div[@data-identifier='{self.email}']",
                        ]:
                            try:
                                self.driver.find_element(By.XPATH, asel).click()
                                break
                            except NoSuchElementException:
                                continue
                        time.sleep(W * 3)
                        try:
                            self.driver.switch_to.window(main_win)
                        except Exception:
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    time.sleep(W * 2)
                    if self._is_logged_in():
                        log.info("Google login OK")
                        return
                    break
            except (NoSuchElementException, ElementClickInterceptedException):
                continue

        # Fallback email/password
        try:
            wait_for(self.driver, By.ID, "usernameField", timeout=5).send_keys(self.email)
            wait_for(self.driver, By.ID, "passwordField", timeout=5).send_keys(self.password)
            wait_and_click(self.driver, By.XPATH, "//button[@type='submit']", timeout=5)
            time.sleep(W * 2)
            log.info("Password login OK")
        except Exception as e:
            log.error(f"Login failed: {e}")
            raise

    def _is_logged_in(self):
        for sel in [
            "div.nI-gNb-drawer__hamburger", "a[href*='mnjuser']",
            "span.nI-gNb-header__userName", "img.nI-gNb-header__userImg",
        ]:
            try:
                if self.driver.find_element(By.CSS_SELECTOR, sel).is_displayed():
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                pass
        return "nlogin" not in self.driver.current_url and "login" not in self.driver.current_url

    # ── Search (latest first) ──────────────────────────────────────────────
    def _search_and_apply(self, keywords, location):
        kw_enc = keywords.replace(" ", "-")
        loc_enc = location.lower().replace(" ", "-")
        page = 1
        while self.applied < self.max_apps:
            self.driver.get(
                f"{self.BASE}/{kw_enc}-jobs-in-{loc_enc}"
                f"?k={keywords}&l={location}&sortBy=date&pageNo={page}"
            )
            time.sleep(W * 2)
            jobs = []
            for sel in ["div.srp-jobtuple-wrapper a.title", "article.jobTuple a.title",
                        "div.cust-job-tuple a.title", "a.title"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                if els:
                    for el in els:
                        try:
                            h, t = el.get_attribute("href"), el.text.strip()
                            if h and t:
                                jobs.append((h, t))
                        except StaleElementReferenceException:
                            pass
                    break
            if not jobs:
                log.info(f"No jobs page {page}")
                break
            log.info(f"Page {page}: {len(jobs)} jobs")
            for h, t in jobs:
                if self.applied >= self.max_apps:
                    return
                self._apply_to_job(h, t)
            page += 1

    # ── Apply ──────────────────────────────────────────────────────────────
    def _apply_to_job(self, url, title):
        main_win = self.driver.current_window_handle
        self.driver.execute_script("window.open(arguments[0]);", url)
        self.driver.switch_to.window(self.driver.window_handles[-1])
        time.sleep(W)
        try:
            btn = self._find_apply_btn()
            if not btn:
                self.skipped += 1
                return
            if "applied" in btn.text.strip().lower():
                log.info(f"Already applied: {title}")
                self.skipped += 1
                return
            btn.click()
            time.sleep(W)
            self._handle_chatbot_popup()
            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {title}")
        except Exception as e:
            log.warning(f"Failed '{title}': {e}")
            self.failed += 1
        finally:
            self.driver.close()
            self.driver.switch_to.window(main_win)

    def _find_apply_btn(self):
        for sel in [
            "//button[contains(translate(.,'APLY','aply'),'apply') and not(contains(translate(.,'APLIED','aplied'),'applied'))]",
            "//button[contains(@class,'apply')]", "//button[@id='apply-button']",
            "//button[contains(@id,'apply')]",
        ]:
            try:
                b = self.driver.find_element(By.XPATH, sel)
                if b.is_displayed():
                    return b
            except NoSuchElementException:
                pass
        return None

    # ── Naukri Chatbot Popup Handler ───────────────────────────────────────
    def _handle_chatbot_popup(self):
        """
        Naukri chatbot flow:
        - Questions appear as botMsg in chatbot_MessageContainer
        - Input is a contenteditable div (div.textArea)
        - OR clickable chips (div.chip / button inside footerWrapper)
        - OR native select/input fields inside the chatbot
        - Send/Save button is div.sendMsg
        - After answering, next question appears. Loop until no new question.
        """
        prev_q_count = 0
        for _ in range(20):  # up to 20 questions
            time.sleep(W)

            # Check if chatbot is visible
            chatbot = self._find_chatbot()
            if not chatbot:
                # Maybe a regular form popup instead
                self._handle_form_popup()
                break

            # Get all bot questions
            questions = chatbot.find_elements(By.CSS_SELECTOR, "div.botMsg.msg span")
            if len(questions) == prev_q_count:
                # No new question, try clicking save/submit one more time
                self._click_save_send(chatbot)
                break
            prev_q_count = len(questions)

            # Get the latest question
            latest_q = questions[-1].text.strip() if questions else ""
            log.info(f"  Chatbot Q: {latest_q}")
            ans = answer_question(latest_q)

            # Try chips first (clickable options)
            if self._click_chip(chatbot, ans):
                time.sleep(W)
                continue

            # Try select dropdowns inside chatbot
            if self._fill_chatbot_select(chatbot, latest_q):
                self._click_save_send(chatbot)
                time.sleep(W)
                continue

            # Try regular input fields inside chatbot
            if self._fill_chatbot_inputs(chatbot, latest_q):
                self._click_save_send(chatbot)
                time.sleep(W)
                continue

            # Type into contenteditable div
            if self._type_in_chatbot(chatbot, ans):
                self._click_save_send(chatbot)
                time.sleep(W)
                continue

            # Nothing worked, try save anyway
            self._click_save_send(chatbot)

    def _find_chatbot(self):
        for sel in ["div.chatbot_DrawerContentWrapper", "div.chatbot_MessageContainer",
                     "div[class*='chatbot_Drawer']", "div[class*='chatbot']"]:
            try:
                el = self.driver.find_element(By.CSS_SELECTOR, sel)
                if el.is_displayed():
                    return el
            except NoSuchElementException:
                pass
        return None

    def _type_in_chatbot(self, chatbot, answer):
        """Type into the contenteditable div input."""
        for sel in [
            "div.textArea[contenteditable='true']",
            "div[contenteditable='true']",
            "div.chatbot_InputContainer div[contenteditable]",
        ]:
            try:
                inp = self.driver.find_element(By.CSS_SELECTOR, sel)
                if inp.is_displayed():
                    inp.click()
                    time.sleep(0.2)
                    inp.clear()
                    # Use JS to set text since contenteditable divs are tricky
                    self.driver.execute_script(
                        "arguments[0].innerText = arguments[1]; "
                        "arguments[0].dispatchEvent(new Event('input', {bubbles:true}));",
                        inp, answer
                    )
                    time.sleep(0.3)
                    log.info(f"  Typed: '{answer}'")
                    return True
            except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                pass
        return False

    def _click_save_send(self, chatbot):
        """Click Save/Send button in chatbot."""
        for sel in [
            "div.sendMsg", "div.send div.sendMsg",
            "//div[contains(@class,'sendMsg')]",
            "//div[contains(@class,'send')]//div[text()='Save']",
            "//div[text()='Save']", "//div[text()='Send']",
            "//button[text()='Save']", "//button[text()='Send']",
            "//button[text()='Submit']", "//button[text()='Next']",
        ]:
            try:
                if sel.startswith("//"):
                    btn = self.driver.find_element(By.XPATH, sel)
                else:
                    btn = self.driver.find_element(By.CSS_SELECTOR, sel)
                if btn.is_displayed():
                    # Remove disabled class via JS if present, then click
                    self.driver.execute_script(
                        "arguments[0].closest('.send')?.classList.remove('disabled'); "
                        "arguments[0].click();", btn
                    )
                    time.sleep(0.5)
                    return True
            except (NoSuchElementException, ElementClickInterceptedException,
                    ElementNotInteractableException, StaleElementReferenceException):
                pass
        return False

    def _click_chip(self, chatbot, answer):
        """Click a chip/option button that matches the answer."""
        ans_lower = answer.lower()
        for sel in ["div.chip", "button.chip", "span.chip", "div.option",
                     "button.option", "li.option", "div.selectable"]:
            chips = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for chip in chips:
                try:
                    ct = chip.text.strip().lower()
                    if ct and chip.is_displayed():
                        if ans_lower in ct or ct in ans_lower:
                            chip.click()
                            log.info(f"  Chip: '{chip.text.strip()}'")
                            return True
                except (ElementClickInterceptedException, StaleElementReferenceException,
                        ElementNotInteractableException):
                    pass
        # If no match, click first visible chip
        for sel in ["div.chip", "button.chip"]:
            chips = self.driver.find_elements(By.CSS_SELECTOR, sel)
            for chip in chips:
                try:
                    if chip.is_displayed() and chip.text.strip():
                        chip.click()
                        log.info(f"  Chip (first): '{chip.text.strip()}'")
                        return True
                except (ElementClickInterceptedException, StaleElementReferenceException,
                        ElementNotInteractableException):
                    pass
        return False

    def _fill_chatbot_select(self, chatbot, question):
        """Fill select dropdowns inside chatbot."""
        filled = False
        for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                cur_val = select.first_selected_option.get_attribute("value") or ""
                if cur_val and cur_val not in ("", "0", "-1", "select"):
                    continue
                ans = answer_question(question)
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot and (ans.lower() in ot or ot in ans.lower()):
                        select.select_by_visible_text(opt.text)
                        filled = True
                        log.info(f"  Select: '{opt.text.strip()}'")
                        break
                else:
                    if len(select.options) > 1:
                        select.select_by_index(1)
                        filled = True
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass
        return filled

    def _fill_chatbot_inputs(self, chatbot, question):
        """Fill regular input/textarea fields inside chatbot."""
        filled = False
        for inp in self.driver.find_elements(By.CSS_SELECTOR,
                "input[type='text'], input[type='number'], input[type='tel'], textarea"):
            try:
                if not inp.is_displayed():
                    continue
                val = (inp.get_attribute("value") or "").strip()
                if val:
                    continue
                ans = answer_question(question)
                inp.clear()
                inp.send_keys(ans)
                filled = True
                log.info(f"  Input: '{ans}'")
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass
        return filled

    # ── Regular form popup (non-chatbot) ───────────────────────────────────
    def _handle_form_popup(self):
        for _ in range(5):
            time.sleep(W)
            changed = False
            # Text fields
            for inp in self.driver.find_elements(By.CSS_SELECTOR,
                    "input[type='text'], input[type='number'], input[type='tel'], textarea"):
                try:
                    if inp.is_displayed() and not (inp.get_attribute("value") or "").strip():
                        label = self._get_label(inp)
                        ans = answer_question(label)
                        inp.clear()
                        inp.send_keys(ans)
                        changed = True
                except (ElementNotInteractableException, StaleElementReferenceException):
                    pass
            # Selects
            for sel_el in self.driver.find_elements(By.CSS_SELECTOR, "select"):
                try:
                    if not sel_el.is_displayed():
                        continue
                    select = Select(sel_el)
                    cv = select.first_selected_option.get_attribute("value") or ""
                    if cv and cv not in ("", "0", "-1"):
                        continue
                    label = self._get_label(sel_el)
                    ans = answer_question(label)
                    for opt in select.options:
                        if ans.lower() in opt.text.strip().lower():
                            select.select_by_visible_text(opt.text)
                            changed = True
                            break
                    else:
                        if len(select.options) > 1:
                            select.select_by_index(1)
                            changed = True
                except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                    pass
            # Radio
            groups = {}
            for rb in self.driver.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
                try:
                    n = rb.get_attribute("name")
                    if n:
                        groups.setdefault(n, []).append(rb)
                except StaleElementReferenceException:
                    pass
            for n, radios in groups.items():
                try:
                    if not any(r.is_selected() for r in radios):
                        radios[0].click()
                        changed = True
                except (ElementNotInteractableException, StaleElementReferenceException):
                    pass
            # Checkboxes (agree/terms)
            for cb in self.driver.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
                try:
                    if cb.is_displayed() and not cb.is_selected():
                        lb = self._get_label(cb).lower()
                        if any(k in lb for k in ["agree", "terms", "consent", "confirm"]):
                            cb.click()
                            changed = True
                except (ElementNotInteractableException, StaleElementReferenceException):
                    pass
            # Submit
            for xpath in ["//button[contains(text(),'Submit')]", "//button[contains(text(),'Next')]",
                          "//button[contains(text(),'Apply')]", "//button[contains(text(),'Save')]",
                          "//button[contains(text(),'Continue')]", "//input[@type='submit']"]:
                try:
                    b = self.driver.find_element(By.XPATH, xpath)
                    if b.is_displayed() and b.is_enabled():
                        b.click()
                        time.sleep(W)
                        changed = True
                        break
                except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                    pass
            if not changed:
                break

    def _get_label(self, element):
        try:
            el_id = element.get_attribute("id")
            if el_id:
                lbl = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{el_id}']")
                if lbl and lbl[0].text.strip():
                    return lbl[0].text.strip()
        except Exception:
            pass
        for depth in ["./..","./../../"]:
            try:
                p = element.find_element(By.XPATH, depth)
                for tag in ["label","span","p"]:
                    try:
                        l = p.find_element(By.CSS_SELECTOR, tag)
                        if l.text.strip():
                            return l.text.strip()
                    except NoSuchElementException:
                        pass
            except Exception:
                pass
        for attr in ["placeholder","aria-label","title","name"]:
            try:
                v = element.get_attribute(attr)
                if v:
                    return v
            except Exception:
                pass
        return ""
