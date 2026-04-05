import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import *
from browser_utils import create_driver, wait_and_click, wait_for
from resume_data import answer_question, RESUME, is_relevant_job

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

    def _js(self, script, *args):
        return self.driver.execute_script(script, *args)

    def _scroll(self, el):
        self._js("arguments[0].scrollIntoView({block:'center',behavior:'instant'});", el)

    def _click(self, el):
        self._scroll(el)
        self._js("arguments[0].click();", el)

    def _els(self, css):
        return self.driver.find_elements(By.CSS_SELECTOR, css)

    def _el(self, css):
        return self.driver.find_element(By.CSS_SELECTOR, css)

    def _xel(self, xpath):
        return self.driver.find_element(By.XPATH, xpath)

    def run(self):
        self.driver = create_driver()
        try:
            self._login()
            combos = [(kw, loc) for kw in self.keywords for loc in self.locations]
            page = 1
            while self.applied < self.max_apps:
                found_any = False
                for kw, loc in combos:
                    if self.applied >= self.max_apps:
                        return
                    try:
                        count = self._search_page(kw, loc, page)
                        if count > 0:
                            found_any = True
                    except Exception as e:
                        log.error(f"Search error: {e}")
                if not found_any:
                    break
                page += 1
        except KeyboardInterrupt:
            log.info("Stopped by user")
        except Exception as e:
            log.error(f"Fatal: {e}")
        finally:
            log.info(f"Done — Applied:{self.applied} Skipped:{self.skipped} Failed:{self.failed}")
            try:
                self.driver.quit()
            except Exception:
                pass

    # ── LOGIN ──────────────────────────────────────────────────────────────
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
                            except Exception:
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
            except Exception:
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
                if self._el(s).is_displayed():
                    return True
            except Exception:
                pass
        u = self.driver.current_url
        return "nlogin" not in u and "login" not in u

    # ── SEARCH ─────────────────────────────────────────────────────────────
    def _search_page(self, keywords, location, page):
        kw, loc = keywords.replace(" ", "-"), location.lower().replace(" ", "-")
        try:
            self.driver.get(f"{self.BASE}/{kw}-jobs-in-{loc}?k={keywords}&l={location}&sortBy=date&pageNo={page}")
            time.sleep(1.2)
            jobs = []
            for s in ["div.srp-jobtuple-wrapper a.title", "article.jobTuple a.title",
                       "div.cust-job-tuple a.title", "a.title"]:
                els = self._els(s)
                if els:
                    for e in els:
                        try:
                            h, t = e.get_attribute("href"), e.text.strip()
                            if h and t:
                                jobs.append((h, t))
                        except Exception:
                            pass
                    break
            if not jobs:
                return 0
            log.info(f"'{keywords}' in '{location}' page {page}: {len(jobs)} jobs")
            for h, t in jobs:
                if self.applied >= self.max_apps:
                    return len(jobs)
                try:
                    self._apply_to_job(h, t)
                except Exception as e:
                    log.warning(f"Error on '{t}': {e}")
                    self.failed += 1
                    try:
                        if len(self.driver.window_handles) > 1:
                            self.driver.close()
                            self.driver.switch_to.window(self.driver.window_handles[0])
                    except Exception:
                        pass
            return len(jobs)
        except Exception as e:
            log.error(f"Page {page} error: {e}")
            return 0

    # ── APPLY ──────────────────────────────────────────────────────────────
    def _apply_to_job(self, url, title):
        d = self.driver
        mw = d.current_window_handle
        d.execute_script("window.open(arguments[0]);", url)
        d.switch_to.window(d.window_handles[-1])
        time.sleep(0.4)
        try:
            btn = self._find_apply_btn()
            if not btn:
                self.skipped += 1
                return
            if "applied" in btn.text.strip().lower():
                self.skipped += 1
                return
            if not is_relevant_job(title):
                log.info(f"Skipped (not AI/ML): {title}")
                self.skipped += 1
                return
            self._click(btn)
            time.sleep(0.5)
            self._handle_all_popups()
            self.applied += 1
            log.info(f"[{self.applied}] Applied: {title}")
        except Exception as e:
            log.warning(f"Failed '{title}': {e}")
            self.failed += 1
        finally:
            try:
                d.close()
            except Exception:
                pass
            try:
                d.switch_to.window(mw)
            except Exception:
                try:
                    d.switch_to.window(d.window_handles[0])
                except Exception:
                    pass

    def _find_apply_btn(self):
        for s in ["//button[contains(translate(.,'APLY','aply'),'apply') and not(contains(translate(.,'APLIED','aplied'),'applied'))]",
                   "//button[contains(@class,'apply')]", "//button[@id='apply-button']", "//button[contains(@id,'apply')]"]:
            try:
                b = self.driver.find_element(By.XPATH, s)
                if b.is_displayed():
                    return b
            except Exception:
                pass
        return None

    # ══════════════════════════════════════════════════════════════════════
    #  POPUP HANDLER — fast, direct
    # ══════════════════════════════════════════════════════════════════════
    def _handle_all_popups(self):
        prev_q = 0
        stale = 0
        for _ in range(25):
            time.sleep(0.3)
            try:
                # Check if chatbot is present
                chatbot = self._els("div.chatbot_DrawerContentWrapper")
                if chatbot:
                    qs = self._els("li.botItem div.botMsg span")
                    if not qs:
                        qs = self._els("div.botMsg span")
                    if len(qs) <= prev_q:
                        self._force_click_save()
                        time.sleep(0.3)
                        qs = self._els("li.botItem div.botMsg span") or self._els("div.botMsg span")
                        if len(qs) <= prev_q:
                            stale += 1
                            if stale >= 3:
                                break
                            continue
                    stale = 0
                    prev_q = len(qs)
                    q_text = qs[-1].text.strip() if qs else ""
                    log.info(f"  Q: {q_text}")
                    ans = answer_question(q_text)

                    # Try in order: radio label → chip → text input → contenteditable
                    if not self._click_radio_label(ans):
                        if not self._click_chip_fast(ans):
                            self._fill_visible_inputs(q_text)
                            self._type_chatbot_input(q_text, ans)
                    time.sleep(0.15)
                    self._force_click_save()
                else:
                    # Non-chatbot popup (regular form)
                    filled = self._fill_visible_inputs("")
                    submitted = self._click_submit()
                    if not filled and not submitted:
                        stale += 1
                        if stale >= 2:
                            break
                    else:
                        stale = 0
            except Exception:
                continue

    # ── CLICK RADIO LABEL (Naukri chatbot ssrc labels) ─────────────────────
    def _click_radio_label(self, answer):
        al = answer.lower().strip()
        labels = self._els("label.ssrc__label")
        if not labels:
            labels = self._els("div.singleselect-radiobutton-container label")
        if not labels:
            labels = self._els("div.chatbot_DrawerContentWrapper label")
        best, best_s = None, 0
        for lbl in labels:
            try:
                lt = lbl.text.strip().lower()
                if not lt or not lbl.is_displayed():
                    continue
                if al == lt:
                    best, best_s = lbl, 100
                    break
                if al in lt:
                    s = 90
                elif lt in al:
                    s = 80
                else:
                    s = len(set(al.split()) & set(lt.split())) * 20
                if s > best_s:
                    best, best_s = lbl, s
            except Exception:
                pass
        if best and best_s >= 20:
            self._js("arguments[0].click();", best)
            log.info(f"  Radio: {best.text.strip()}")
            return True
        return False

    # ── CLICK CHIP (fast, minimal selectors) ───────────────────────────────
    def _click_chip_fast(self, answer):
        al = answer.lower()
        for c in self._els("div.chip, button.chip, span.chip, div.chipMsg button"):
            try:
                ct = c.text.strip().lower()
                if ct and c.is_displayed() and (al in ct or ct in al):
                    self._js("arguments[0].click();", c)
                    log.info(f"  Chip: {c.text.strip()}")
                    return True
            except Exception:
                pass
        # Fallback: click first visible chip
        for c in self._els("div.chip, button.chip"):
            try:
                if c.is_displayed() and c.text.strip():
                    self._js("arguments[0].click();", c)
                    return True
            except Exception:
                pass
        return False

    # ── TYPE INTO CHATBOT CONTENTEDITABLE ──────────────────────────────────
    def _type_chatbot_input(self, question, answer):
        q_lower = question.lower()
        is_num = any(w in q_lower for w in ["how many", "number", "in days", "in months", "in years", "in lpa", "in lakhs"])
        typed_ans = answer_question(question, numeric_only=True) if is_num else answer
        for s in ["div.textArea[contenteditable='true']", "div[contenteditable='true'].textArea",
                   "div.chatbot_InputContainer div[contenteditable]"]:
            try:
                inp = self._el(s)
                if inp.is_displayed():
                    self._js(
                        "var e=arguments[0];e.innerText=arguments[1];"
                        "e.dispatchEvent(new Event('input',{bubbles:true}));"
                        "e.dispatchEvent(new Event('change',{bubbles:true}));"
                        "e.dispatchEvent(new KeyboardEvent('keydown',{key:'a',bubbles:true}));"
                        "e.dispatchEvent(new KeyboardEvent('keyup',{key:'a',bubbles:true}));",
                        inp, typed_ans)
                    log.info(f"  Typed: {typed_ans}")
                    return True
            except Exception:
                pass
        return False

    # ── FORCE CLICK SAVE/SEND (remove disabled, click) ────────────────────
    def _force_click_save(self):
        try:
            self._js(
                "document.querySelectorAll('.send.disabled,.send').forEach(e=>{"
                "e.classList.remove('disabled');e.style.pointerEvents='auto'});"
                "var b=document.querySelector('div.sendMsg');"
                "if(b)b.click();"
            )
            return True
        except Exception:
            pass
        for x in ["//div[text()='Save']", "//div[text()='Send']", "//button[text()='Save']",
                   "//button[text()='Send']", "//button[text()='Submit']"]:
            try:
                b = self._xel(x)
                if b.is_displayed():
                    self._js("arguments[0].click();", b)
                    return True
            except Exception:
                pass
        return False

    # ── FILL VISIBLE INPUTS (text, number, select, radio, checkbox) ───────
    def _fill_visible_inputs(self, ctx=""):
        filled = False

        # Text / Number / Tel inputs
        for inp in self._els("input[type='text'], input[type='number'], input[type='tel'], "
                              "input[type='email'], input[type='url'], input:not([type]), textarea"):
            try:
                if not inp.is_displayed():
                    continue
                itype = (inp.get_attribute("type") or "").lower()
                if itype in ("hidden", "submit", "button", "radio", "checkbox", "file"):
                    continue
                if inp.get_attribute("readonly") or inp.get_attribute("disabled"):
                    continue
                if (inp.get_attribute("value") or "").strip():
                    continue
                label = self._get_label(inp)
                is_numeric = itype in ("number", "tel")
                ans = answer_question(label or ctx, numeric_only=is_numeric)
                inp.click()
                inp.clear()
                inp.send_keys(ans)
                time.sleep(0.15)
                # If field rejected text, retry numeric
                if not (inp.get_attribute("value") or "").strip() and not is_numeric:
                    inp.clear()
                    inp.send_keys(answer_question(label or ctx, numeric_only=True))
                # Pick autocomplete if any
                time.sleep(0.2)
                self._pick_autocomplete(inp, ans)
                filled = True
                log.info(f"  Input '{label}' → {ans}")
            except Exception:
                pass

        # Native <select>
        for sel_el in self._els("select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                cv = (select.first_selected_option.get_attribute("value") or "").strip().lower()
                ct = select.first_selected_option.text.strip().lower()
                skip = ("select", "--select--", "choose", "", "0", "-1")
                if cv not in skip and ct not in skip:
                    continue
                label = self._get_label(sel_el)
                ans = answer_question(label or ctx).lower()
                best_opt, best_score = None, 0
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot in skip:
                        continue
                    if ans == ot:
                        best_opt, best_score = opt, 100
                        break
                    if ans in ot:
                        s = 90
                    elif ot in ans:
                        s = 80
                    else:
                        s = len(set(ans.split()) & set(ot.split())) * 10
                    if s > best_score:
                        best_opt, best_score = opt, s
                if best_opt:
                    select.select_by_visible_text(best_opt.text)
                    filled = True
                    log.info(f"  Select '{label}' → {best_opt.text.strip()}")
                else:
                    valid = [o for o in select.options if (o.get_attribute("value") or "").strip() not in ("", "0", "-1")]
                    if valid:
                        select.select_by_visible_text(valid[-1].text)
                        filled = True
            except Exception:
                pass

        # Radio buttons
        groups = {}
        for rb in self._els("input[type='radio']"):
            try:
                n = rb.get_attribute("name")
                if n:
                    groups.setdefault(n, []).append(rb)
            except Exception:
                pass
        for name, radios in groups.items():
            try:
                if any(r.is_selected() for r in radios):
                    continue
                label = self._get_label(radios[0])
                ans = answer_question(label or ctx).lower()
                clicked = False
                for r in radios:
                    rl = self._get_label(r).lower()
                    if ans in rl or rl in ans or "yes" in rl:
                        self._js("arguments[0].click();", r)
                        clicked = True
                        filled = True
                        log.info(f"  Radio '{label}' → {rl}")
                        break
                if not clicked and radios:
                    self._js("arguments[0].click();", radios[0])
                    filled = True
            except Exception:
                pass

        # Checkboxes — check all unchecked
        for cb in self._els("input[type='checkbox']"):
            try:
                if not cb.is_selected():
                    if cb.is_displayed():
                        self._js("arguments[0].click();", cb)
                    else:
                        self._js("arguments[0].checked=true;arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", cb)
                        cid = cb.get_attribute("id")
                        if cid:
                            for lbl in self._els(f"label[for='{cid}']"):
                                if lbl.is_displayed():
                                    self._js("arguments[0].click();", lbl)
                                    break
                    filled = True
            except Exception:
                pass

        return filled

    # ── SUBMIT BUTTON ──────────────────────────────────────────────────────
    def _click_submit(self):
        for x in ["//button[contains(text(),'Submit')]", "//button[contains(text(),'Next')]",
                   "//button[contains(text(),'Apply')]", "//button[contains(text(),'Save')]",
                   "//button[contains(text(),'Continue')]", "//button[contains(text(),'Done')]",
                   "//input[@type='submit']", "//button[@type='submit']"]:
            try:
                b = self._xel(x)
                if b.is_displayed() and b.is_enabled():
                    self._js("arguments[0].click();", b)
                    return True
            except Exception:
                pass
        return False

    # ── LABEL EXTRACTION ───────────────────────────────────────────────────
    def _get_label(self, el):
        try:
            eid = el.get_attribute("id")
            if eid:
                for l in self._els(f"label[for='{eid}']"):
                    t = l.text.strip()
                    if t:
                        return t
        except Exception:
            pass
        for depth in ["./..", "./../.."]:
            try:
                p = el.find_element(By.XPATH, depth)
                for tag in ["label", "span", "p", "div.label", "div.lbl"]:
                    try:
                        l = p.find_element(By.CSS_SELECTOR, tag)
                        t = l.text.strip()
                        if t and len(t) < 200:
                            return t
                    except Exception:
                        pass
            except Exception:
                pass
        for attr in ["placeholder", "aria-label", "title", "name"]:
            try:
                v = el.get_attribute(attr)
                if v:
                    return v
            except Exception:
                pass
        return ""

    def _pick_autocomplete(self, inp, answer):
        al = answer.lower()
        for sel in ["ul[role='listbox'] li", "div[role='listbox'] div[role='option']",
                     "ul.typeahead li", "div.suggestions li", "div[class*='suggest'] li",
                     "div[class*='autocomplete'] li", "ul.ui-autocomplete li"]:
            options = self._els(sel)
            if not options:
                continue
            best, best_s = None, 0
            for opt in options:
                try:
                    if not opt.is_displayed():
                        continue
                    ot = opt.text.strip().lower()
                    if not ot:
                        continue
                    if al == ot:
                        best = opt
                        break
                    if al in ot and 90 > best_s:
                        best, best_s = opt, 90
                    elif ot in al and 80 > best_s:
                        best, best_s = opt, 80
                except Exception:
                    pass
            if best:
                self._js("arguments[0].click();", best)
                return True
            # Click first visible option
            for opt in options:
                try:
                    if opt.is_displayed() and opt.text.strip():
                        self._js("arguments[0].click();", opt)
                        return True
                except Exception:
                    pass
        try:
            inp.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.05)
            inp.send_keys(Keys.ENTER)
        except Exception:
            pass
        return False
