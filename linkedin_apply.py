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


class LinkedInApplier:
    BASE = "https://www.linkedin.com"

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

    def _xels(self, xpath):
        return self.driver.find_elements(By.XPATH, xpath)

    def _xel(self, xpath):
        return self.driver.find_element(By.XPATH, xpath)

    def run(self):
        self.driver = create_driver()
        try:
            self._login()
            combos = [(kw, loc) for kw in self.keywords for loc in self.locations]
            page = 0
            while self.applied < self.max_apps:
                found_any = False
                for kw, loc in combos:
                    if self.applied >= self.max_apps:
                        log.info(f"Reached {self.max_apps} applications, stopping")
                        return
                    try:
                        count = self._search_page(kw, loc, page)
                        if count > 0:
                            found_any = True
                    except Exception as e:
                        log.error(f"Search error: {e}")
                        continue
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

        # Check if already logged in (Edge profile has session)
        if self._is_logged_in():
            log.info("Already logged in")
            return

        d.get(f"{self.BASE}/login")
        time.sleep(1.5)

        # Check again after redirect
        if self._is_logged_in():
            log.info("Already logged in")
            return

        # Try Google sign-in
        for sel in ["//button[contains(text(),'Google')]", "//a[contains(@href,'google')]",
                     "//span[contains(text(),'Google')]"]:
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
                        for a in [f"//div[@data-email='{self.email}']", f"//div[contains(text(),'{self.email}')]"]:
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

        # Email/password login
        try:
            wait_for(d, By.ID, "username", timeout=5).send_keys(self.email)
            wait_for(d, By.ID, "password", timeout=5).send_keys(self.password)
            wait_and_click(d, By.XPATH, "//button[@type='submit']", timeout=5)
            time.sleep(3)

            # CAPTCHA / 2FA check
            if "checkpoint" in d.current_url or "challenge" in d.current_url:
                log.warning("CAPTCHA/2FA detected — solve it in the browser")
                input("Press ENTER after verification...")

            log.info("Password login OK")
        except Exception as e:
            log.error(f"Login failed: {e}")
            raise

    def _is_logged_in(self):
        u = self.driver.current_url
        if "/feed" in u or "/jobs" in u or "/mynetwork" in u:
            return True
        for s in ["div.feed-identity-module", "img.global-nav__me-photo",
                   "div.global-nav__me", "nav.global-nav"]:
            try:
                if self._el(s).is_displayed():
                    return True
            except Exception:
                pass
        return False

    # ── SEARCH ─────────────────────────────────────────────────────────────
    def _search_page(self, keywords, location, page):
        """Search one page of results. Returns number of jobs found."""
        try:
            start = page * 25
            url = (
                f"{self.BASE}/jobs/search/?keywords={keywords}"
                f"&location={location}&f_AL=true&sortBy=DD&start={start}"
            )
            self.driver.get(url)
            time.sleep(1.5)

            cards = self._els("div.job-card-container, li.jobs-search-results__list-item, "
                              "div.job-card-list, li.ember-view.jobs-search-results__list-item")
            if not cards:
                cards = self._els("ul.scaffold-layout__list-container > li")
            if not cards:
                return 0

            log.info(f"'{keywords}' in '{location}' page {page + 1}: {len(cards)} jobs")

            for i, card in enumerate(cards):
                if self.applied >= self.max_apps:
                    return len(cards)
                try:
                    self._scroll(card)
                    self._click(card)
                    time.sleep(0.5)
                    self._try_easy_apply()
                except Exception as e:
                    log.warning(f"Card {i} error: {e}")
                    self.failed += 1
                    self._close_modal()

            return len(cards)
        except Exception as e:
            log.error(f"Page {page + 1} error: {e}")
            return 0

    # ── EASY APPLY ─────────────────────────────────────────────────────────
    def _try_easy_apply(self):
        # Find Easy Apply button
        btn = None
        for sel in [
            "//button[contains(@class,'jobs-apply-button')]",
            "//button[contains(.,'Easy Apply')]",
            "//button[contains(@aria-label,'Easy Apply')]",
        ]:
            try:
                b = self._xel(sel)
                if b.is_displayed():
                    btn = b
                    break
            except Exception:
                pass

        if not btn:
            self.skipped += 1
            return

        txt = btn.text.strip().lower()
        if "easy apply" not in txt and "apply" not in txt:
            self.skipped += 1
            return

        # Get job title
        title = "Unknown"
        for sel in ["h1.t-24", "h2.t-24", "h1.job-details-jobs-unified-top-card__job-title",
                     "h1.jobs-unified-top-card__job-title", "a.job-card-container__link"]:
            try:
                title = self._el(sel).text.strip()
                if title:
                    break
            except Exception:
                pass

        # Check if job is AI/ML related
        if not is_relevant_job(title):
            log.info(f"Skipped (not AI/ML): {title}")
            self.skipped += 1
            return

        self._click(btn)
        time.sleep(0.5)

        if self._walk_easy_apply_modal():
            self.applied += 1
            log.info(f"[{self.applied}] Applied: {title}")
        else:
            self.skipped += 1
            log.info(f"Skipped: {title}")
            self._close_modal()

    # ── WALK THROUGH EASY APPLY MODAL ──────────────────────────────────────
    def _walk_easy_apply_modal(self):
        for step in range(15):
            time.sleep(0.4)

            # Fill all visible form fields
            self._fill_all_fields()

            # Check for Submit button
            for sel in [
                "//button[contains(@aria-label,'Submit application')]",
                "//button[contains(@aria-label,'Submit')]",
                "//button[contains(text(),'Submit application')]",
                "//button[contains(text(),'Submit')]",
            ]:
                try:
                    btn = self._xel(sel)
                    if btn.is_displayed() and btn.is_enabled():
                        self._scroll(btn)
                        self._click(btn)
                        time.sleep(0.5)
                        self._close_post_apply()
                        return True
                except Exception:
                    pass

            # Check for Next / Review / Continue button
            clicked_next = False
            for sel in [
                "//button[contains(@aria-label,'Continue to next step')]",
                "//button[contains(@aria-label,'Review your application')]",
                "//button[contains(@aria-label,'Next')]",
                "//button[contains(text(),'Next')]",
                "//button[contains(text(),'Continue')]",
                "//button[contains(text(),'Review')]",
            ]:
                try:
                    btn = self._xel(sel)
                    if btn.is_displayed() and btn.is_enabled():
                        self._scroll(btn)
                        self._click(btn)
                        time.sleep(0.4)
                        clicked_next = True
                        break
                except Exception:
                    pass

            if not clicked_next:
                # No next/submit button found — might be stuck
                # Try filling again and look for any button
                self._fill_all_fields()
                for sel in ["//button[contains(@class,'artdeco-button--primary')]"]:
                    try:
                        btn = self._xel(sel)
                        if btn.is_displayed() and btn.is_enabled():
                            self._click(btn)
                            time.sleep(0.4)
                            break
                    except Exception:
                        pass
                else:
                    return False

            # Check for error messages (required fields not filled)
            errors = self._els("div.artdeco-inline-feedback--error, span.artdeco-inline-feedback__message")
            if errors:
                # Try filling again
                self._fill_all_fields()

        return False

    # ══════════════════════════════════════════════════════════════════════
    #  FILL ALL FORM FIELDS — LinkedIn Easy Apply specific
    # ══════════════════════════════════════════════════════════════════════
    def _fill_all_fields(self):
        filled = False

        # ── 1. Text / Number / Tel / Email inputs ──
        for inp in self._els(
                "input[type='text'], input[type='number'], input[type='tel'], "
                "input[type='email'], input[type='url'], input:not([type])"):
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
                if not label:
                    continue
                is_numeric = itype in ("number", "tel") or inp.get_attribute("pattern") in ("[0-9]*", "\\d*", "\\d+")
                ans = answer_question(label, numeric_only=is_numeric)
                self._scroll(inp)
                inp.click()
                inp.clear()
                inp.send_keys(ans)
                time.sleep(0.1)
                actual = (inp.get_attribute("value") or "").strip()
                if not actual and not is_numeric:
                    ans = answer_question(label, numeric_only=True)
                    inp.clear()
                    inp.send_keys(ans)

                # Handle autocomplete/typeahead dropdown
                time.sleep(0.4)
                if self._pick_autocomplete(inp, ans):
                    log.info(f"  Autocomplete '{label}' → {ans}")
                else:
                    log.info(f"  Input '{label}' → {ans}")
                filled = True
            except Exception:
                pass

        # ── 2. Textareas ──
        for ta in self._els("textarea"):
            try:
                if not ta.is_displayed():
                    continue
                if ta.get_attribute("readonly") or ta.get_attribute("disabled"):
                    continue
                val = (ta.get_attribute("value") or ta.text or "").strip()
                if val:
                    continue
                label = self._get_label(ta)
                ans = answer_question(label or "summary")
                self._scroll(ta)
                ta.click()
                ta.clear()
                ta.send_keys(ans)
                filled = True
                log.info(f"  Textarea '{label}' → {ans[:50]}...")
            except Exception:
                pass

        # ── 3. Native <select> dropdowns ──
        for sel_el in self._els("select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                cv = (select.first_selected_option.get_attribute("value") or "").strip().lower()
                ct = select.first_selected_option.text.strip().lower()
                skip = ("select", "--select--", "choose", "select an option", "", "0", "-1")
                if cv not in skip and ct not in skip:
                    continue
                label = self._get_label(sel_el)
                ans = answer_question(label or "").lower()
                self._scroll(sel_el)

                # Scored matching
                best_opt, best_score = None, 0
                ans_words = set(ans.split())
                for opt in select.options:
                    ot = opt.text.strip().lower()
                    if ot in skip:
                        continue
                    if ans == ot:
                        best_opt, best_score = opt, 100
                        break
                    if len(ans) > 2 and ans in ot:
                        s = 90
                        if s > best_score:
                            best_opt, best_score = opt, s
                    elif len(ot) > 2 and ot in ans:
                        s = 80
                        if s > best_score:
                            best_opt, best_score = opt, s
                    else:
                        common = ans_words & set(ot.split())
                        if common:
                            s = len(common) * 10
                            if s > best_score:
                                best_opt, best_score = opt, s

                if best_opt:
                    select.select_by_visible_text(best_opt.text)
                    filled = True
                    log.info(f"  Select '{label}' → {best_opt.text.strip()}")
                else:
                    # LinkedIn often has Yes/No — pick Yes
                    for opt in select.options:
                        ot = opt.text.strip().lower()
                        if ot == "yes":
                            select.select_by_visible_text(opt.text)
                            filled = True
                            break
                    else:
                        valid = [o for o in select.options if (o.get_attribute("value") or "").strip() not in ("", "0", "-1")]
                        if valid:
                            select.select_by_visible_text(valid[-1].text)
                            filled = True
            except Exception:
                pass

        # ── 4. LinkedIn custom dropdowns (artdeco) ──
        for dd in self._els("div[data-test-text-selectable-option], "
                            "div.artdeco-dropdown, div[class*='dropdown']"):
            try:
                if not dd.is_displayed():
                    continue
                self._scroll(dd)
                self._click(dd)
                time.sleep(0.2)
                label = self._get_label(dd)
                ans = answer_question(label or "").lower()
                for opt in self._els("li[data-test-text-selectable-option__option], "
                                     "div.artdeco-dropdown__item, li.artdeco-dropdown__item"):
                    try:
                        ot = opt.text.strip().lower()
                        if ot and opt.is_displayed() and (ans in ot or ot in ans or "yes" in ot):
                            self._click(opt)
                            filled = True
                            break
                    except Exception:
                        pass
            except Exception:
                pass

        # ── 5. Radio buttons (LinkedIn uses fieldset > input[type=radio]) ──
        fieldsets = self._els("fieldset")
        for fs in fieldsets:
            try:
                radios = fs.find_elements(By.CSS_SELECTOR, "input[type='radio']")
                if not radios:
                    continue
                if any(safe(lambda r=r: r.is_selected()) for r in radios):
                    continue
                # Get fieldset legend/label as question
                q = ""
                for tag in ["legend", "span", "label"]:
                    try:
                        q = fs.find_element(By.CSS_SELECTOR, tag).text.strip()
                        if q:
                            break
                    except Exception:
                        pass
                ans = answer_question(q).lower()

                clicked = False
                for r in radios:
                    try:
                        # Get radio label
                        rl = ""
                        rid = r.get_attribute("id")
                        if rid:
                            try:
                                rl = self.driver.find_element(By.CSS_SELECTOR, f"label[for='{rid}']").text.strip().lower()
                            except Exception:
                                pass
                        if not rl:
                            try:
                                rl = r.find_element(By.XPATH, "./..").text.strip().lower()
                            except Exception:
                                pass
                        if rl and (ans in rl or rl in ans or "yes" in rl):
                            self._scroll(r)
                            self._js("arguments[0].click();", r)
                            clicked = True
                            filled = True
                            log.info(f"  Radio '{q}' → {rl}")
                            break
                    except Exception:
                        pass
                if not clicked and radios:
                    # Default: click first radio
                    try:
                        self._scroll(radios[0])
                        self._js("arguments[0].click();", radios[0])
                        filled = True
                    except Exception:
                        pass
            except Exception:
                pass

        # Also handle standalone radios not in fieldset
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
                ans = answer_question(label or "").lower()
                clicked = False
                for r in radios:
                    try:
                        rl = self._get_label(r).lower()
                        if ans in rl or rl in ans or "yes" in rl:
                            self._scroll(r)
                            self._js("arguments[0].click();", r)
                            clicked = True
                            filled = True
                            break
                    except Exception:
                        pass
                if not clicked and radios:
                    try:
                        self._js("arguments[0].click();", radios[0])
                        filled = True
                    except Exception:
                        pass
            except Exception:
                pass

        # ── 6. Checkboxes ──
        # 6a. Native visible
        for cb in self._els("input[type='checkbox']"):
            try:
                if not cb.is_selected():
                    if cb.is_displayed():
                        self._scroll(cb)
                        self._js("arguments[0].click();", cb)
                        filled = True
                    else:
                        self._js("arguments[0].checked=true;arguments[0].dispatchEvent(new Event('change',{bubbles:true}));", cb)
                        cid = cb.get_attribute("id")
                        if cid:
                            for lbl in self._els(f"label[for='{cid}']"):
                                try:
                                    if lbl.is_displayed():
                                        self._scroll(lbl)
                                        self._js("arguments[0].click();", lbl)
                                except Exception:
                                    pass
                        try:
                            pl = cb.find_element(By.XPATH, "ancestor::label")
                            if pl.is_displayed():
                                self._scroll(pl)
                                self._js("arguments[0].click();", pl)
                        except Exception:
                            pass
                        filled = True
            except Exception:
                pass

        # 6b. Custom styled checkboxes
        for sel in ["div[role='checkbox']", "span[role='checkbox']",
                     "div[class*='checkbox']", "span[class*='checkbox']",
                     "label[class*='checkbox']"]:
            for el in self._els(sel):
                try:
                    if not el.is_displayed():
                        continue
                    ac = (el.get_attribute("aria-checked") or "").lower()
                    cls = (el.get_attribute("class") or "").lower()
                    if ac == "true" or "checked" in cls or "selected" in cls:
                        continue
                    self._scroll(el)
                    self._js("arguments[0].click();", el)
                    filled = True
                except Exception:
                    pass

        # ── 7. Toggle switches ──
        for tog in self._els("div[class*='toggle'], label.switch, span[class*='toggle'], "
                             "button[role='switch']"):
            try:
                if tog.is_displayed():
                    ac = (tog.get_attribute("aria-checked") or "").lower()
                    if ac != "true":
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

        # ── 9. File upload (resume) ──
        for fu in self._els("input[type='file']"):
            try:
                label = self._get_label(fu)
                if label and any(w in label.lower() for w in ["resume", "cv", "document"]):
                    fu.send_keys(r"C:\Users\fe901f\Downloads\Gokul_Kaliyamoorthy_AI_ML_Engineer.pdf")
                    filled = True
                    log.info("  Uploaded resume")
            except Exception:
                pass

        # ── 10. Contenteditable divs ──
        for ce in self._els("div[contenteditable='true']"):
            try:
                if ce.is_displayed() and not (ce.text or "").strip():
                    label = self._get_label(ce)
                    ans = answer_question(label or "summary")
                    self._scroll(ce)
                    self._js("var e=arguments[0];e.innerText=arguments[1];"
                             "e.dispatchEvent(new Event('input',{bubbles:true}));", ce, ans)
                    filled = True
            except Exception:
                pass

        return filled

    # ── CLOSE MODAL ────────────────────────────────────────────────────────
    def _close_modal(self):
        for sel in [
            "//button[contains(@aria-label,'Dismiss')]",
            "//button[contains(@aria-label,'discard')]",
            "//button[contains(text(),'Discard')]",
            "//button[contains(text(),'Save')]",
            "//button[@data-test-modal-close-btn]",
            "//button[contains(@class,'artdeco-modal__dismiss')]",
        ]:
            try:
                btn = self._xel(sel)
                if btn.is_displayed():
                    self._click(btn)
                    time.sleep(0.3)
            except Exception:
                pass
        # Handle "Discard application?" confirmation
        for sel in [
            "//button[contains(text(),'Discard')]",
            "//button[contains(@data-test-dialog-primary-btn,'')]",
        ]:
            try:
                btn = self._xel(sel)
                if btn.is_displayed():
                    self._click(btn)
                    time.sleep(0.3)
            except Exception:
                pass

    def _close_post_apply(self):
        time.sleep(0.3)
        for sel in [
            "//button[contains(@aria-label,'Dismiss')]",
            "//button[contains(text(),'Done')]",
            "//button[contains(text(),'Close')]",
            "//button[contains(@class,'artdeco-modal__dismiss')]",
        ]:
            try:
                btn = self._xel(sel)
                if btn.is_displayed():
                    self._click(btn)
                    return
            except Exception:
                pass

    # ── AUTOCOMPLETE / TYPEAHEAD HANDLER ────────────────────────────────────
    def _pick_autocomplete(self, inp, answer):
        """After typing in an input, check if a dropdown appeared and pick best match."""
        al = answer.lower()
        # LinkedIn autocomplete selectors
        for sel in [
            "div.basic-typeahead__triggered-content li",
            "div.search-typeahead-v2__hit",
            "ul[role='listbox'] li",
            "div[role='listbox'] div[role='option']",
            "ul.typeahead-results li",
            "div.artdeco-typeahead__results-list li",
            "div[class*='typeahead'] li",
            "div[class*='Typeahead'] li",
            "ul[id*='typeahead'] li",
            "div.jobs-easy-apply-form-element__typeahead li",
        ]:
            options = self._els(sel)
            if not options:
                continue
            # Try best match first
            best, best_score = None, 0
            for opt in options:
                try:
                    if not opt.is_displayed():
                        continue
                    ot = opt.text.strip().lower()
                    if not ot:
                        continue
                    if al == ot:
                        best, best_score = opt, 100
                        break
                    if al in ot:
                        s = 90
                        if s > best_score:
                            best, best_score = opt, s
                    elif ot in al:
                        s = 80
                        if s > best_score:
                            best, best_score = opt, s
                    else:
                        common = set(al.split()) & set(ot.split())
                        if common:
                            s = len(common) * 10
                            if s > best_score:
                                best, best_score = opt, s
                except Exception:
                    pass
            if best:
                self._scroll(best)
                self._click(best)
                return True
            # No match — just click first visible option
            for opt in options:
                try:
                    if opt.is_displayed() and opt.text.strip():
                        self._scroll(opt)
                        self._click(opt)
                        return True
                except Exception:
                    pass
        # Also try pressing arrow down + enter as fallback
        try:
            inp.send_keys(Keys.ARROW_DOWN)
            time.sleep(0.1)
            inp.send_keys(Keys.ENTER)
            return True
        except Exception:
            pass
        return False

    # ── LABEL EXTRACTION ───────────────────────────────────────────────────
    def _get_label(self, el):
        # LinkedIn uses label[for=id] extensively
        try:
            eid = el.get_attribute("id")
            if eid:
                for l in self._els(f"label[for='{eid}']"):
                    t = l.text.strip()
                    if t:
                        return t
        except Exception:
            pass
        # aria-label
        try:
            al = el.get_attribute("aria-label")
            if al:
                return al
        except Exception:
            pass
        # aria-describedby
        try:
            adb = el.get_attribute("aria-describedby")
            if adb:
                for did in adb.split():
                    try:
                        desc = self.driver.find_element(By.ID, did)
                        t = desc.text.strip()
                        if t:
                            return t
                    except Exception:
                        pass
        except Exception:
            pass
        # Walk up parents
        for depth in ["./..", "./../.."]:
            try:
                p = el.find_element(By.XPATH, depth)
                for tag in ["label", "legend", "span.visually-hidden", "span", "p"]:
                    try:
                        l = p.find_element(By.CSS_SELECTOR, tag)
                        t = l.text.strip()
                        if t and len(t) < 200:
                            return t
                    except Exception:
                        pass
            except Exception:
                pass
        # Placeholder / title
        for attr in ["placeholder", "title", "name"]:
            try:
                v = el.get_attribute(attr)
                if v:
                    return v
            except Exception:
                pass
        return ""
