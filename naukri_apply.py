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


def _safe(fn):
    try:
        return fn()
    except Exception:
        return None


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
                    log.info(f"Search: '{kw}' in '{loc}'")
                    self._search_and_apply(kw, loc)
        except Exception as e:
            log.error(f"Fatal: {e}", exc_info=True)
        finally:
            log.info(f"Done — Applied:{self.applied} Skipped:{self.skipped} Failed:{self.failed}")
            self.driver.quit()

    def _login(self):
        d = self.driver
        d.get(self.BASE)
        time.sleep(1.5)
        if self._is_logged_in():
            log.info("Already logged in")
            return
        d.get(f"{self.BASE}/nlogin/login")
        time.sleep(1.5)
        for sel in ["//button[contains(text(),'Google')]", "//div[contains(text(),'Sign in with Google')]",
                     "//span[contains(text(),'Google')]", "//div[contains(@class,'google')]"]:
            try:
                btn = d.find_element(By.XPATH, sel)
                if btn.is_displayed():
                    btn.click()
                    time.sleep(2)
                    mw = d.current_window_handle
                    if len(d.window_handles) > 1:
                        for w in d.window_handles:
                            if w != mw:
                                d.switch_to.window(w)
                                break
                        time.sleep(1.5)
                        for a in [f"//div[@data-email='{self.email}']", f"//div[contains(text(),'{self.email}')]",
                                  f"//div[@data-identifier='{self.email}']"]:
                            try:
                                d.find_element(By.XPATH, a).click()
                                break
                            except NoSuchElementException:
                                continue
                        time.sleep(2)
                        try:
                            d.switch_to.window(mw)
                        except Exception:
                            d.switch_to.window(d.window_handles[0])
                    time.sleep(1.5)
                    if self._is_logged_in():
                        log.info("Google login OK")
                        return
                    break
            except (NoSuchElementException, ElementClickInterceptedException):
                continue
        try:
            wait_for(d, By.ID, "usernameField", timeout=5).send_keys(self.email)
            wait_for(d, By.ID, "passwordField", timeout=5).send_keys(self.password)
            wait_and_click(d, By.XPATH, "//button[@type='submit']", timeout=5)
            time.sleep(1.5)
            log.info("Password login OK")
        except Exception as e:
            log.error(f"Login failed: {e}")
            raise

    def _is_logged_in(self):
        for s in ["div.nI-gNb-drawer__hamburger", "a[href*='mnjuser']",
                   "span.nI-gNb-header__userName", "img.nI-gNb-header__userImg"]:
            try:
                if self.driver.find_element(By.CSS_SELECTOR, s).is_displayed():
                    return True
            except (NoSuchElementException, StaleElementReferenceException):
                pass
        u = self.driver.current_url
        return "nlogin" not in u and "login" not in u

    def _search_and_apply(self, keywords, location):
        kw, loc = keywords.replace(" ", "-"), location.lower().replace(" ", "-")
        page = 1
        while self.applied < self.max_apps:
            self.driver.get(f"{self.BASE}/{kw}-jobs-in-{loc}?k={keywords}&l={location}&sortBy=date&pageNo={page}")
            time.sleep(1.5)
            jobs = []
            for s in ["div.srp-jobtuple-wrapper a.title", "article.jobTuple a.title",
                       "div.cust-job-tuple a.title", "a.title"]:
                els = self.driver.find_elements(By.CSS_SELECTOR, s)
                if els:
                    for e in els:
                        try:
                            h, t = e.get_attribute("href"), e.text.strip()
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

    def _apply_to_job(self, url, title):
        d = self.driver
        mw = d.current_window_handle
        d.execute_script("window.open(arguments[0]);", url)
        d.switch_to.window(d.window_handles[-1])
        time.sleep(0.5)
        try:
            btn = self._find_apply_btn()
            if not btn:
                self.skipped += 1
                return
            if "applied" in btn.text.strip().lower():
                self.skipped += 1
                return
            btn.click()
            time.sleep(0.5)
            self._handle_all_popups()
            self.applied += 1
            log.info(f"[{self.applied}/{self.max_apps}] Applied: {title}")
        except Exception as e:
            log.warning(f"Failed '{title}': {e}")
            self.failed += 1
        finally:
            d.close()
            d.switch_to.window(mw)

    def _find_apply_btn(self):
        for s in ["//button[contains(translate(.,'APLY','aply'),'apply') and not(contains(translate(.,'APLIED','aplied'),'applied'))]",
                   "//button[contains(@class,'apply')]", "//button[@id='apply-button']", "//button[contains(@id,'apply')]"]:
            try:
                b = self.driver.find_element(By.XPATH, s)
                if b.is_displayed():
                    return b
            except NoSuchElementException:
                pass
        return None

    # ══════════════════════════════════════════════════════════════════════
    #  POPUP / CHATBOT / FORM HANDLER — fills EVERYTHING fast
    # ══════════════════════════════════════════════════════════════════════
    def _handle_all_popups(self):
        prev_q = 0
        for _ in range(25):
            time.sleep(0.3)
            chatbot = self._find_chatbot()
            if chatbot:
                qs = self.driver.find_elements(By.CSS_SELECTOR, "div.botMsg.msg span, div.botMsg span, li.botItem span")
                if len(qs) == prev_q:
                    self._click_save_send()
                    time.sleep(0.3)
                    qs2 = self.driver.find_elements(By.CSS_SELECTOR, "div.botMsg.msg span, div.botMsg span, li.botItem span")
                    if len(qs2) == prev_q:
                        break
                prev_q = len(qs)
                latest = qs[-1].text.strip() if qs else ""
                log.info(f"  Q: {latest}")
                ans = answer_question(latest)
                if not self._click_chip(ans):
                    if not self._fill_all_fields(latest):
                        self._type_contenteditable(ans)
                self._click_save_send()
            else:
                if not self._fill_all_fields(""):
                    self._click_any_submit()
                    break
                self._click_any_submit()

    def _find_chatbot(self):
        for s in ["div.chatbot_DrawerContentWrapper", "div.chatbot_MessageContainer", "div[class*='chatbot_Drawer']"]:
            try:
                e = self.driver.find_element(By.CSS_SELECTOR, s)
                if e.is_displayed():
                    return e
            except NoSuchElementException:
                pass
        return None

    # ── Type into contenteditable div ──────────────────────────────────────
    def _type_contenteditable(self, answer):
        for s in ["div.textArea[contenteditable='true']", "div[contenteditable='true']",
                   "div.chatbot_InputContainer div[contenteditable]"]:
            try:
                inp = self.driver.find_element(By.CSS_SELECTOR, s)
                if inp.is_displayed():
                    inp.click()
                    self.driver.execute_script(
                        "var e=arguments[0];e.innerText=arguments[1];"
                        "e.dispatchEvent(new Event('input',{bubbles:true}));"
                        "e.dispatchEvent(new Event('change',{bubbles:true}));"
                        "e.dispatchEvent(new KeyboardEvent('keyup',{bubbles:true}));",
                        inp, answer)
                    log.info(f"  Typed: {answer}")
                    return True
            except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                pass
        return False

    # ── Click Save/Send ────────────────────────────────────────────────────
    def _click_save_send(self):
        d = self.driver
        # Remove disabled from send button container
        _safe(lambda: d.execute_script(
            "document.querySelectorAll('.send.disabled').forEach(e=>e.classList.remove('disabled'));"
            "document.querySelectorAll('.sendMsg').forEach(e=>e.style.pointerEvents='auto');"
        ))
        for s in ["div.sendMsg", "div.send div.sendMsg"]:
            try:
                b = d.find_element(By.CSS_SELECTOR, s)
                if b.is_displayed():
                    d.execute_script("arguments[0].click();", b)
                    return True
            except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                pass
        for x in ["//div[text()='Save']", "//div[text()='Send']", "//button[text()='Save']",
                   "//button[text()='Send']", "//button[text()='Submit']"]:
            try:
                b = d.find_element(By.XPATH, x)
                if b.is_displayed():
                    d.execute_script("arguments[0].click();", b)
                    return True
            except (NoSuchElementException, ElementNotInteractableException, StaleElementReferenceException):
                pass
        return False

    # ── Click chip/option ──────────────────────────────────────────────────
    def _click_chip(self, answer):
        al = answer.lower()
        for s in ["div.chip", "button.chip", "span.chip", "div.option", "button.option",
                   "li.option", "div.selectable", "div.chipMsg button", "div.footerWrapper button",
                   "div.footerWrapper div.chip"]:
            chips = self.driver.find_elements(By.CSS_SELECTOR, s)
            for c in chips:
                try:
                    ct = c.text.strip().lower()
                    if ct and c.is_displayed() and (al in ct or ct in al):
                        c.click()
                        log.info(f"  Chip: {c.text.strip()}")
                        return True
                except (ElementClickInterceptedException, StaleElementReferenceException, ElementNotInteractableException):
                    pass
        # Click first visible chip if no match
        for s in ["div.chip", "button.chip"]:
            for c in self.driver.find_elements(By.CSS_SELECTOR, s):
                try:
                    if c.is_displayed() and c.text.strip():
                        c.click()
                        return True
                except (ElementClickInterceptedException, StaleElementReferenceException, ElementNotInteractableException):
                    pass
        return False

    # ══════════════════════════════════════════════════════════════════════
    #  FILL ALL FIELDS — text, number, tel, textarea, select, custom
    #  dropdown, radio, checkbox, accordion, toggle, date, file
    # ══════════════════════════════════════════════════════════════════════
    def _fill_all_fields(self, context_question=""):
        d = self.driver
        filled = False

        # ── Expand accordions / collapsed sections first ──
        for s in ["div.accordion-header", "div[class*='accordion']", "div[class*='collaps']",
                   "div[class*='expand']", "summary", "div[role='button'][aria-expanded='false']",
                   "button[aria-expanded='false']", "div.section-header", "h3.toggle", "h4.toggle"]:
            for el in d.find_elements(By.CSS_SELECTOR, s):
                try:
                    if el.is_displayed():
                        el.click()
                        time.sleep(0.2)
                except (ElementClickInterceptedException, ElementNotInteractableException, StaleElementReferenceException):
                    pass

        # ── Text / Number / Tel / Email / URL inputs ──
        for inp in d.find_elements(By.CSS_SELECTOR,
                "input[type='text'], input[type='number'], input[type='tel'], "
                "input[type='email'], input[type='url'], input:not([type]), textarea"):
            try:
                if not inp.is_displayed():
                    continue
                if inp.get_attribute("readonly") or inp.get_attribute("disabled"):
                    continue
                val = (inp.get_attribute("value") or "").strip()
                if val:
                    continue
                label = self._get_label(inp)
                q = label or context_question
                ans = answer_question(q)
                inp.click()
                inp.clear()
                inp.send_keys(ans)
                inp.send_keys(Keys.TAB)
                filled = True
                log.info(f"  Input '{q}' → {ans}")
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # ── Native <select> dropdowns ──
        for sel_el in d.find_elements(By.CSS_SELECTOR, "select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                cv = (select.first_selected_option.get_attribute("value") or "").strip().lower()
                ct = select.first_selected_option.text.strip().lower()
                if cv and cv not in ("", "0", "-1", "select", "--select--") and ct not in ("select", "--select--", "choose", ""):
                    continue
                label = self._get_label(sel_el)
                q = label or context_question
                ans = answer_question(q).lower()
                matched = False
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot and ot not in ("select", "--select--", "choose", "") and (ans in ot or ot in ans):
                        select.select_by_visible_text(opt.text)
                        matched = True
                        filled = True
                        log.info(f"  Select '{q}' → {opt.text.strip()}")
                        break
                if not matched and len(select.options) > 1:
                    for opt in select.options:
                        if opt.get_attribute("value") and opt.get_attribute("value") not in ("", "0", "-1"):
                            select.select_by_visible_text(opt.text)
                            filled = True
                            break
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass

        # ── Custom div-based dropdowns ──
        for dd in d.find_elements(By.CSS_SELECTOR,
                "div.customSelect, div.dropdownMainContainer, div[class*='dropdown'], "
                "div[class*='Dropdown'], div[class*='select-wrapper'], div[class*='SelectBox']"):
            try:
                if not dd.is_displayed():
                    continue
                dt = dd.text.strip().lower()
                if dt and dt not in ("select", "choose", "--select--", ""):
                    continue
                label = self._get_label(dd)
                ans = answer_question(label or context_question).lower()
                dd.click()
                time.sleep(0.2)
                for opt in d.find_elements(By.CSS_SELECTOR,
                        "li, div.optionItem, div[class*='option'], ul li, div[class*='Option']"):
                    try:
                        ot = opt.text.strip().lower()
                        if ot and opt.is_displayed() and (ans in ot or ot in ans):
                            opt.click()
                            filled = True
                            break
                    except (ElementClickInterceptedException, StaleElementReferenceException):
                        pass
            except (ElementNotInteractableException, StaleElementReferenceException, NoSuchElementException):
                pass

        # ── Radio buttons ──
        groups = {}
        for rb in d.find_elements(By.CSS_SELECTOR, "input[type='radio']"):
            try:
                n = rb.get_attribute("name")
                if n:
                    groups.setdefault(n, []).append(rb)
            except StaleElementReferenceException:
                pass
        for n, radios in groups.items():
            try:
                if any(r.is_selected() for r in radios):
                    continue
                label = self._get_label(radios[0])
                ans = answer_question(label or context_question).lower()
                clicked = False
                for r in radios:
                    try:
                        rl = self._get_label(r).lower()
                        if ans in rl or rl in ans or "yes" in rl:
                            d.execute_script("arguments[0].click();", r)
                            clicked = True
                            filled = True
                            break
                    except (ElementNotInteractableException, StaleElementReferenceException):
                        pass
                if not clicked:
                    try:
                        d.execute_script("arguments[0].click();", radios[0])
                        filled = True
                    except Exception:
                        pass
            except (StaleElementReferenceException, ElementNotInteractableException):
                pass

        # ── ALL checkboxes — check every unchecked visible checkbox ──
        for cb in d.find_elements(By.CSS_SELECTOR, "input[type='checkbox']"):
            try:
                if cb.is_displayed() and not cb.is_selected():
                    d.execute_script("arguments[0].click();", cb)
                    filled = True
                    log.info(f"  Checkbox checked")
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # ── Toggle switches ──
        for tog in d.find_elements(By.CSS_SELECTOR,
                "div[class*='toggle'], div[class*='switch'], label.switch, span[class*='toggle']"):
            try:
                if tog.is_displayed():
                    aria = tog.get_attribute("aria-checked") or ""
                    if aria == "false" or not aria:
                        d.execute_script("arguments[0].click();", tog)
                        filled = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # ── Date inputs ──
        for di in d.find_elements(By.CSS_SELECTOR, "input[type='date'], input[type='month']"):
            try:
                if di.is_displayed() and not (di.get_attribute("value") or "").strip():
                    di.send_keys("2025-01-01")
                    filled = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        # ── Contenteditable divs (outside chatbot too) ──
        for ce in d.find_elements(By.CSS_SELECTOR, "div[contenteditable='true']"):
            try:
                if ce.is_displayed() and not (ce.text or "").strip():
                    label = self._get_label(ce)
                    ans = answer_question(label or context_question)
                    d.execute_script(
                        "var e=arguments[0];e.innerText=arguments[1];"
                        "e.dispatchEvent(new Event('input',{bubbles:true}));", ce, ans)
                    filled = True
            except (ElementNotInteractableException, StaleElementReferenceException):
                pass

        return filled

    def _click_any_submit(self):
        d = self.driver
        for x in ["//button[contains(text(),'Submit')]", "//button[contains(text(),'submit')]",
                   "//button[contains(text(),'Next')]", "//button[contains(text(),'Apply')]",
                   "//button[contains(text(),'Save')]", "//button[contains(text(),'Continue')]",
                   "//button[contains(text(),'Done')]", "//button[contains(text(),'Confirm')]",
                   "//input[@type='submit']", "//button[@type='submit']"]:
            try:
                b = d.find_element(By.XPATH, x)
                if b.is_displayed() and b.is_enabled():
                    d.execute_script("arguments[0].click();", b)
                    return True
            except (NoSuchElementException, ElementClickInterceptedException, ElementNotInteractableException):
                pass
        return False

    def _get_label(self, element):
        try:
            eid = element.get_attribute("id")
            if eid:
                for l in self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{eid}']"):
                    if l.text.strip():
                        return l.text.strip()
        except Exception:
            pass
        for depth in ["./..", "./../.."]:
            try:
                p = element.find_element(By.XPATH, depth)
                for tag in ["label", "span", "p", "div.label"]:
                    try:
                        l = p.find_element(By.CSS_SELECTOR, tag)
                        t = l.text.strip()
                        if t and len(t) < 200:
                            return t
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
