import time
import logging
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import *
from browser_utils import create_driver, wait_and_click, wait_for
from resume_data import answer_question, RESUME, is_relevant_job

log = logging.getLogger(__name__)


def safe(fn):
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
            while self.applied < self.max_apps:
                for kw in self.keywords:
                    for loc in self.locations:
                        if self.applied >= self.max_apps:
                            log.info(f"Reached {self.max_apps} applications, stopping")
                            return
                        try:
                            log.info(f"Search: '{kw}' in '{loc}'")
                            self._search_and_apply(kw, loc)
                        except Exception as e:
                            log.error(f"Search error: {e}")
                            continue
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
    def _search_and_apply(self, keywords, location):
        kw, loc = keywords.replace(" ", "-"), location.lower().replace(" ", "-")
        page = 1
        while True:
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
                    log.info(f"No jobs page {page}")
                    break
                log.info(f"Page {page}: {len(jobs)} jobs")
                for h, t in jobs:
                    try:
                        self._apply_to_job(h, t)
                    except Exception as e:
                        log.warning(f"Error on '{t}': {e}")
                        self.failed += 1
                        # Make sure we're back on main window
                        try:
                            if len(self.driver.window_handles) > 1:
                                self.driver.close()
                                self.driver.switch_to.window(self.driver.window_handles[0])
                        except Exception:
                            pass
                page += 1
            except Exception as e:
                log.error(f"Page {page} error: {e}")
                page += 1
                continue

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
            time.sleep(0.3)
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
    #  POPUP HANDLER — chatbot + form, never stops
    # ══════════════════════════════════════════════════════════════════════
    def _handle_all_popups(self):
        prev_q = 0
        for _ in range(30):
            time.sleep(0.2)
            try:
                if self._find_chatbot():
                    qs = self._els("div.botMsg span, li.botItem div.botMsg span, div.botMsg.msg span")
                    if len(qs) <= prev_q:
                        self._click_save_send()
                        time.sleep(0.2)
                        qs2 = self._els("div.botMsg span, li.botItem div.botMsg span, div.botMsg.msg span")
                        if len(qs2) <= prev_q:
                            break
                        qs = qs2
                    prev_q = len(qs)
                    latest = qs[-1].text.strip() if qs else ""
                    log.info(f"  Q: {latest}")
                    ans = answer_question(latest)
                    # Try all methods: chip → fields → contenteditable
                    if not self._click_chip(ans):
                        self._fill_all_fields(latest)
                        # For contenteditable, check if question asks for number
                        q_lower = latest.lower()
                        is_num_q = any(w in q_lower for w in ["how many", "number", "in days", "in months", "in years", "in lpa", "in lakhs"])
                        typed_ans = answer_question(latest, numeric_only=is_num_q) if is_num_q else ans
                        self._type_contenteditable(typed_ans)
                    self._click_save_send()
                else:
                    self._fill_all_fields("")
                    if not self._click_any_submit():
                        break
            except Exception as e:
                log.debug(f"Popup step error: {e}")
                continue

    def _find_chatbot(self):
        for s in ["div.chatbot_DrawerContentWrapper", "div.chatbot_MessageContainer", "div[class*='chatbot_Drawer']"]:
            try:
                e = self._el(s)
                if e.is_displayed():
                    return e
            except Exception:
                pass
        return None

    # ── CONTENTEDITABLE INPUT ──────────────────────────────────────────────
    def _type_contenteditable(self, answer):
        for s in ["div.textArea[contenteditable='true']", "div[contenteditable='true'].textArea",
                   "div.chatbot_InputContainer div[contenteditable]"]:
            try:
                inp = self._el(s)
                if inp.is_displayed():
                    self._scroll(inp)
                    inp.click()
                    self._js(
                        "var e=arguments[0];e.innerText=arguments[1];"
                        "e.dispatchEvent(new Event('input',{bubbles:true}));"
                        "e.dispatchEvent(new Event('change',{bubbles:true}));"
                        "e.dispatchEvent(new KeyboardEvent('keydown',{key:'a',bubbles:true}));"
                        "e.dispatchEvent(new KeyboardEvent('keyup',{key:'a',bubbles:true}));",
                        inp, answer)
                    log.info(f"  Typed: {answer}")
                    return True
            except Exception:
                pass
        return False

    # ── SAVE / SEND BUTTON ─────────────────────────────────────────────────
    def _click_save_send(self):
        # Force-enable all send buttons
        safe(lambda: self._js(
            "document.querySelectorAll('.send.disabled,.send').forEach(e=>{e.classList.remove('disabled');e.style.pointerEvents='auto';e.style.opacity='1'});"
            "document.querySelectorAll('.sendMsg').forEach(e=>{e.style.pointerEvents='auto';e.style.opacity='1'});"
        ))
        for s in ["div.sendMsg", "div.send div.sendMsg"]:
            try:
                b = self._el(s)
                if b.is_displayed():
                    self._scroll(b)
                    self._js("arguments[0].click();", b)
                    return True
            except Exception:
                pass
        for x in ["//div[text()='Save']", "//div[text()='Send']", "//button[text()='Save']",
                   "//button[text()='Send']", "//button[text()='Submit']"]:
            try:
                b = self._xel(x)
                if b.is_displayed():
                    self._scroll(b)
                    self._js("arguments[0].click();", b)
                    return True
            except Exception:
                pass
        return False

    # ── CHIP / OPTION CLICK ────────────────────────────────────────────────
    def _click_chip(self, answer):
        al = answer.lower()
        for s in ["div.chip", "button.chip", "span.chip", "div.option", "button.option",
                   "li.option", "div.selectable", "div.chipMsg button", "div.footerWrapper button",
                   "div.footerWrapper div.chip", "div.chatbot_SendMessageContainer button"]:
            for c in self._els(s):
                try:
                    ct = c.text.strip().lower()
                    if ct and c.is_displayed() and (al in ct or ct in al):
                        self._scroll(c)
                        self._click(c)
                        log.info(f"  Chip: {c.text.strip()}")
                        return True
                except Exception:
                    pass
        for s in ["div.chip", "button.chip"]:
            for c in self._els(s):
                try:
                    if c.is_displayed() and c.text.strip():
                        self._scroll(c)
                        self._click(c)
                        return True
                except Exception:
                    pass
        return False

    # ══════════════════════════════════════════════════════════════════════
    #  FILL EVERY FIELD TYPE — instant, scroll into view, JS clicks
    # ══════════════════════════════════════════════════════════════════════
    def _fill_all_fields(self, ctx=""):
        filled = False

        # ── 1. Expand accordions / collapsed sections ──
        for s in ["div[class*='accordion']", "div[class*='collaps']", "summary",
                   "div[role='button'][aria-expanded='false']", "button[aria-expanded='false']",
                   "div.section-header", "div[class*='expand']"]:
            for el in self._els(s):
                try:
                    if el.is_displayed():
                        self._click(el)
                except Exception:
                    pass

        # ── 2. Text / Number / Tel / Email / URL / Textarea ──
        for inp in self._els(
                "input[type='text'], input[type='number'], input[type='tel'], "
                "input[type='email'], input[type='url'], input:not([type]), textarea"):
            try:
                if not inp.is_displayed():
                    continue
                if inp.get_attribute("readonly") or inp.get_attribute("disabled"):
                    continue
                itype = (inp.get_attribute("type") or "").lower()
                if itype in ("hidden", "submit", "button", "radio", "checkbox", "file"):
                    continue
                val = (inp.get_attribute("value") or "").strip()
                if val:
                    continue
                label = self._get_label(inp)
                # Detect if field only accepts numbers
                is_numeric = itype in ("number", "tel") or inp.get_attribute("pattern") in ("[0-9]*", "\\d*", "\\d+")
                ans = answer_question(label or ctx, numeric_only=is_numeric)
                self._scroll(inp)
                inp.click()
                inp.clear()
                inp.send_keys(ans)
                # Verify: if field rejected text (value empty after typing), retry with numeric
                time.sleep(0.1)
                actual = (inp.get_attribute("value") or "").strip()
                if not actual and not is_numeric:
                    ans = answer_question(label or ctx, numeric_only=True)
                    inp.clear()
                    inp.send_keys(ans)
                filled = True
                log.info(f"  Input '{label}' → {ans}")
            except Exception:
                pass

        # ── 3. Native <select> ──
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
                self._scroll(sel_el)
                best_opt, best_score = None, 0
                ans_words = set(ans.split())
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot in skip:
                        continue
                    # Exact match
                    if ans == ot:
                        best_opt, best_score = opt, 100
                        break
                    # Answer contained in option or vice versa (full phrase)
                    if len(ans) > 2 and ans in ot:
                        score = 90
                        if score > best_score:
                            best_opt, best_score = opt, score
                    elif len(ot) > 2 and ot in ans:
                        score = 80
                        if score > best_score:
                            best_opt, best_score = opt, score
                    else:
                        # Word overlap scoring
                        ot_words = set(ot.split())
                        common = ans_words & ot_words
                        if common:
                            score = len(common) * 10
                            if score > best_score:
                                best_opt, best_score = opt, score
                if best_opt:
                    select.select_by_visible_text(best_opt.text)
                    filled = True
                    log.info(f"  Select '{label}' → {best_opt.text.strip()} (score:{best_score})")
                else:
                    # Last resort: pick last option (usually highest value)
                    valid = [o for o in select.options if (o.get_attribute("value") or "").strip() not in ("", "0", "-1")]
                    if valid:
                        select.select_by_visible_text(valid[-1].text)
                        filled = True
                        log.info(f"  Select '{label}' → {valid[-1].text.strip()} (fallback last)")
            except Exception:
                pass

        # ── 4. Custom div dropdowns ──
        for dd in self._els(
                "div.customSelect, div.dropdownMainContainer, div[class*='dropdown'], "
                "div[class*='Dropdown'], div[class*='select-wrapper'], div[class*='SelectBox']"):
            try:
                if not dd.is_displayed():
                    continue
                dt = dd.text.strip().lower()
                if dt and dt not in ("select", "choose", "--select--", ""):
                    continue
                label = self._get_label(dd)
                ans = answer_question(label or ctx).lower()
                self._scroll(dd)
                self._click(dd)
                time.sleep(0.15)
                for opt in self._els("li, div.optionItem, div[class*='option'], div[class*='Option'], ul li"):
                    try:
                        ot = opt.text.strip().lower()
                        if ot and opt.is_displayed() and (ans in ot or ot in ans):
                            self._scroll(opt)
                            self._click(opt)
                            filled = True
                            log.info(f"  Dropdown '{label}' → {opt.text.strip()}")
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        # ── 5. Radio buttons ──
        groups = {}
        for rb in self._els("input[type='radio']"):
            try:
                n = rb.get_attribute("name")
                if n:
                    groups.setdefault(n, []).append(rb)
            except Exception:
                pass
        for n, radios in groups.items():
            try:
                if any(safe(lambda r=r: r.is_selected()) for r in radios):
                    continue
                label = self._get_label(radios[0])
                ans = answer_question(label or ctx).lower()
                clicked = False
                for r in radios:
                    try:
                        rl = self._get_label(r).lower()
                        if ans in rl or rl in ans or "yes" in rl:
                            self._scroll(r)
                            self._js("arguments[0].click();", r)
                            clicked = True
                            filled = True
                            log.info(f"  Radio '{label}' → {rl}")
                            break
                    except Exception:
                        pass
                if not clicked and radios:
                    try:
                        self._scroll(radios[0])
                        self._js("arguments[0].click();", radios[0])
                        filled = True
                    except Exception:
                        pass
            except Exception:
                pass

        # ── 6. ALL checkboxes — native + custom styled ──
        # 6a. Native checkboxes (visible)
        for cb in self._els("input[type='checkbox']"):
            try:
                if not cb.is_selected():
                    if cb.is_displayed():
                        self._scroll(cb)
                        self._js("arguments[0].click();", cb)
                        filled = True
                        log.info("  Checkbox checked (native visible)")
                    else:
                        # Hidden native checkbox — click its label or force check via JS
                        self._js("arguments[0].checked=true;arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", cb)
                        # Also click the associated label
                        cid = cb.get_attribute("id")
                        if cid:
                            for lbl in self._els(f"label[for='{cid}']"):
                                try:
                                    if lbl.is_displayed():
                                        self._scroll(lbl)
                                        self._js("arguments[0].click();", lbl)
                                except Exception:
                                    pass
                        # Click parent label if wrapping
                        try:
                            parent_label = cb.find_element(By.XPATH, "ancestor::label")
                            if parent_label.is_displayed():
                                self._scroll(parent_label)
                                self._js("arguments[0].click();", parent_label)
                        except Exception:
                            pass
                        filled = True
                        log.info("  Checkbox checked (native hidden)")
            except Exception:
                pass

        # 6b. Custom styled checkboxes (Naukri uses spans/divs as checkboxes)
        for sel in [
            "span.checkmark", "span.customCheckbox", "span[class*='check']",
            "div.checkmark", "div.customCheckbox", "div[class*='checkbox']",
            "label.checkbox", "label[class*='check']",
            "div[class*='Checkbox']", "span[class*='Checkbox']",
            "div[role='checkbox']", "span[role='checkbox']",
            "div.check-box", "span.check-box",
        ]:
            for el in self._els(sel):
                try:
                    if not el.is_displayed():
                        continue
                    ac = (el.get_attribute("aria-checked") or "").lower()
                    cls = (el.get_attribute("class") or "").lower()
                    # Skip if already checked
                    if ac == "true" or "checked" in cls or "selected" in cls or "active" in cls:
                        continue
                    self._scroll(el)
                    self._js("arguments[0].click();", el)
                    filled = True
                    log.info(f"  Custom checkbox checked: {sel}")
                except Exception:
                    pass

        # 6c. Click any unchecked label that wraps a checkbox-like element
        for lbl in self._els("label"):
            try:
                if not lbl.is_displayed():
                    continue
                inner_cb = lbl.find_elements(By.CSS_SELECTOR, "input[type='checkbox']")
                if inner_cb and not inner_cb[0].is_selected():
                    self._scroll(lbl)
                    self._js("arguments[0].click();", lbl)
                    filled = True
                    log.info("  Label-wrapped checkbox checked")
            except Exception:
                pass

        # ── 7. Toggle switches ──
        for tog in self._els("div[class*='toggle'], div[class*='switch'], label.switch, span[class*='toggle']"):
            try:
                if tog.is_displayed():
                    ac = tog.get_attribute("aria-checked") or ""
                    if ac == "false" or not ac:
                        self._scroll(tog)
                        self._js("arguments[0].click();", tog)
                        filled = True
            except Exception:
                pass

        # ── 8. Date inputs ──
        for di in self._els("input[type='date'], input[type='month']"):
            try:
                if di.is_displayed() and not (di.get_attribute("value") or "").strip():
                    self._scroll(di)
                    di.send_keys("2025-01-01")
                    filled = True
            except Exception:
                pass

        # ── 9. Contenteditable divs ──
        for ce in self._els("div[contenteditable='true']"):
            try:
                if ce.is_displayed() and not (ce.text or "").strip():
                    label = self._get_label(ce)
                    ans = answer_question(label or ctx)
                    self._scroll(ce)
                    self._js(
                        "var e=arguments[0];e.innerText=arguments[1];"
                        "e.dispatchEvent(new Event('input',{bubbles:true}));", ce, ans)
                    filled = True
            except Exception:
                pass

        # ── 10. Range / slider inputs ──
        for sl in self._els("input[type='range']"):
            try:
                if sl.is_displayed():
                    self._scroll(sl)
                    mx = sl.get_attribute("max") or "100"
                    self._js(f"arguments[0].value={int(mx)//2};arguments[0].dispatchEvent(new Event('change'));", sl)
                    filled = True
            except Exception:
                pass

        return filled

    def _click_any_submit(self):
        for x in ["//button[contains(text(),'Submit')]", "//button[contains(text(),'submit')]",
                   "//button[contains(text(),'Next')]", "//button[contains(text(),'Apply')]",
                   "//button[contains(text(),'Save')]", "//button[contains(text(),'Continue')]",
                   "//button[contains(text(),'Done')]", "//button[contains(text(),'Confirm')]",
                   "//input[@type='submit']", "//button[@type='submit']"]:
            try:
                b = self._xel(x)
                if b.is_displayed() and b.is_enabled():
                    self._scroll(b)
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
