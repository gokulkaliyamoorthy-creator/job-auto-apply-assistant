import logging
import re
import time
from urllib.parse import quote

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import Select

from browser_utils import create_driver, wait_and_click, wait_for
from resume_data import answer_question, is_relevant_job

log = logging.getLogger(__name__)


def safe(fn):
    try:
        return fn()
    except Exception:
        return None


class FounditApplier:
    BASE = "https://www.foundit.in"

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
        self.target_roles = {self._normalize_role_text(role) for role in self.keywords}

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
            for keyword in self.keywords:
                if self.applied >= self.max_apps:
                    break
                self._search_keyword(keyword)
        except KeyboardInterrupt:
            log.info("Stopped by user")
        except Exception as e:
            log.error(f"Fatal: {e}")
        finally:
            log.info(f"Done - Applied:{self.applied} Skipped:{self.skipped} Failed:{self.failed}")
            try:
                self.driver.quit()
            except Exception:
                pass

    def _login(self):
        d = self.driver
        d.get(self.BASE)
        time.sleep(2)

        if self._is_logged_in():
            log.info("Already logged in to Foundit")
            return

        d.get(f"{self.BASE}/seeker-profile/login")
        time.sleep(2)

        if self._is_logged_in():
            log.info("Already logged in to Foundit")
            return

        if not self.email or not self.password:
            log.warning("Foundit credentials not configured; relying on existing browser session")
            return

        try:
            email_input = None
            for by, value in [
                (By.CSS_SELECTOR, "input[type='email']"),
                (By.CSS_SELECTOR, "input[name='email']"),
                (By.CSS_SELECTOR, "input[placeholder*='Email']"),
                (By.XPATH, "//input[contains(@placeholder,'Email') or contains(@placeholder,'email')]"),
            ]:
                try:
                    email_input = wait_for(d, by, value, timeout=6)
                    if email_input and email_input.is_displayed():
                        break
                except Exception:
                    email_input = None
            if not email_input:
                raise RuntimeError("Foundit email field not found")

            email_input.clear()
            email_input.send_keys(self.email)

            password_input = None
            for by, value in [
                (By.CSS_SELECTOR, "input[type='password']"),
                (By.CSS_SELECTOR, "input[name='password']"),
                (By.XPATH, "//input[contains(@placeholder,'Password') or contains(@placeholder,'password')]"),
            ]:
                try:
                    password_input = wait_for(d, by, value, timeout=4)
                    if password_input and password_input.is_displayed():
                        break
                except Exception:
                    password_input = None
            if not password_input:
                raise RuntimeError("Foundit password field not found")

            password_input.clear()
            password_input.send_keys(self.password)

            for by, value in [
                (By.XPATH, "//button[@type='submit']"),
                (By.XPATH, "//button[contains(.,'Login') or contains(.,'Sign in')]"),
                (By.CSS_SELECTOR, "button[type='submit']"),
            ]:
                try:
                    wait_and_click(d, by, value, timeout=4)
                    break
                except Exception:
                    continue

            time.sleep(4)
            if self._is_logged_in():
                log.info("Foundit login OK")
            else:
                log.warning("Foundit login could not be confirmed; continuing with current session")
        except Exception as e:
            log.warning(f"Foundit login failed: {e}")

    def _is_logged_in(self):
        current_url = self.driver.current_url.lower()
        if "login" in current_url and "foundit.in" in current_url:
            return False
        for sel in [
            "img[alt*='profile']",
            "a[href*='seeker-profile']",
            "div[class*='user']",
            "button[class*='profile']",
        ]:
            try:
                if self._el(sel).is_displayed():
                    return True
            except Exception:
                pass
        return "foundit.in" in current_url and "login" not in current_url

    def _search_keyword(self, keyword):
        page = 1
        while self.applied < self.max_apps:
            jobs = self._search_page(keyword, page)
            if not jobs:
                break
            page += 1

    def _search_page(self, keyword, page):
        url = self._build_search_url(keyword, page)
        self.driver.get(url)
        time.sleep(2)
        self._dismiss_popups()

        jobs = self._collect_jobs()
        if not jobs:
            return 0

        log.info(f"Foundit '{keyword}' page {page}: {len(jobs)} jobs")

        for job in jobs:
            if self.applied >= self.max_apps:
                break
            try:
                self._apply_to_job(job)
            except Exception as e:
                log.warning(f"Foundit apply error: {e}")
                self.failed += 1
                self._cleanup_windows()
                self._dismiss_popups()
        return len(jobs)

    def _build_search_url(self, keyword, page):
        slug = re.sub(r"[^a-z0-9]+", "-", keyword.lower()).strip("-") or "jobs"
        page_suffix = "" if page == 1 else f"-{page}"
        query = quote(keyword)
        return f"{self.BASE}/search/{slug}-jobs{page_suffix}?query={query}"

    def _collect_jobs(self):
        jobs = []
        seen = set()
        selectors = [
            "//button[contains(.,'Quick Apply') or contains(.,'Apply Now') or contains(.,'Apply')]",
            "//a[contains(.,'Quick Apply') or contains(.,'Apply Now')]",
        ]
        for xpath in selectors:
            for control in self._xels(xpath):
                try:
                    if not control.is_displayed():
                        continue
                    title = self._extract_job_title(control)
                    normalized_title = self._normalize_role_text(title)
                    if normalized_title and normalized_title not in self.target_roles:
                        if not any(role in normalized_title for role in self.target_roles):
                            if not is_relevant_job(title):
                                self.skipped += 1
                                continue
                    key = (title, control.text.strip())
                    if key in seen:
                        continue
                    seen.add(key)
                    jobs.append({"title": title or "Foundit Job", "kind": "control", "element": control})
                except Exception:
                    continue

        if jobs:
            return jobs

        for anchor in self._els("a[href]"):
            try:
                if not anchor.is_displayed():
                    continue
                href = (anchor.get_attribute("href") or "").strip()
                title = (anchor.text or "").strip()
                if not href or "foundit.in" not in href:
                    continue
                if any(skip in href.lower() for skip in ["/search/", "/login", "/register", "/jobs-by-"]):
                    continue
                if len(title) < 4:
                    continue
                normalized_title = self._normalize_role_text(title)
                if normalized_title not in self.target_roles and not any(role in normalized_title for role in self.target_roles):
                    continue
                if href in seen:
                    continue
                seen.add(href)
                jobs.append({"title": title, "kind": "link", "href": href})
            except Exception:
                continue

        return jobs

    def _apply_to_job(self, job):
        title = job["title"]
        if not self._is_target_role(title):
            log.info(f"Skipped Foundit job (role mismatch): {title}")
            self.skipped += 1
            return

        main_window = self.driver.current_window_handle
        windows_before = list(self.driver.window_handles)
        start_url = self.driver.current_url

        if job["kind"] == "link":
            self.driver.execute_script("window.open(arguments[0], '_blank');", job["href"])
            self.driver.switch_to.window(self.driver.window_handles[-1])
        else:
            self._scroll(job["element"])
            self._click(job["element"])
            time.sleep(1.5)
            if len(self.driver.window_handles) > len(windows_before):
                self.driver.switch_to.window(self.driver.window_handles[-1])

        try:
            self._dismiss_popups()
            current_url = self.driver.current_url
            if current_url == start_url and job["kind"] == "control":
                if self._walk_apply_flow(title):
                    self.applied += 1
                    log.info(f"[{self.applied}] Applied on Foundit: {title}")
                    return
            if self._walk_apply_flow(title):
                self.applied += 1
                log.info(f"[{self.applied}] Applied on Foundit: {title}")
            else:
                self.skipped += 1
                log.info(f"Skipped Foundit job: {title}")
        except Exception as e:
            log.warning(f"Failed Foundit job '{title}': {e}")
            self.failed += 1
        finally:
            self._close_apply_context(main_window)

    def _walk_apply_flow(self, title):
        self._dismiss_popups()
        clicked_any = False

        for _ in range(12):
            time.sleep(0.6)
            self._fill_all_fields(title)

            if self._application_success():
                return True

            action = self._click_action_button()
            if action:
                clicked_any = True
                time.sleep(1.2)
                self._dismiss_popups()
                if action in {"submit", "apply"} and self._application_success():
                    return True
                continue

            if clicked_any and not self._has_apply_ui():
                return True

            if not clicked_any and self._has_apply_ui():
                continue

            break

        return clicked_any and not self._has_apply_ui()

    def _click_action_button(self):
        actions = [
            ("submit", "//button[contains(.,'Submit')]"),
            ("apply", "//button[contains(.,'Apply now') or contains(.,'Apply Now') or contains(.,'Quick Apply')]"),
            ("apply", "//button[contains(.,'Apply')]"),
            ("next", "//button[contains(.,'Next') or contains(.,'Continue') or contains(.,'Review')]"),
            ("submit", "//a[contains(.,'Submit')]"),
            ("apply", "//a[contains(.,'Apply now') or contains(.,'Apply Now') or contains(.,'Quick Apply')]"),
        ]
        for action, xpath in actions:
            for btn in self._xels(xpath):
                try:
                    if not btn.is_displayed() or not btn.is_enabled():
                        continue
                    text = (btn.text or "").strip().lower()
                    if any(skip in text for skip in ["company site", "external", "recruiter"]):
                        continue
                    self._click(btn)
                    return action
                except Exception:
                    continue
        return None

    def _fill_all_fields(self, ctx=""):
        for inp in self._els(
            "input[type='text'], input[type='number'], input[type='tel'], input[type='email'], "
            "input[type='url'], input:not([type]), textarea"
        ):
            try:
                if not inp.is_displayed():
                    continue
                if inp.get_attribute("readonly") or inp.get_attribute("disabled"):
                    continue
                itype = (inp.get_attribute("type") or "").lower()
                if itype in ("hidden", "submit", "button", "radio", "checkbox", "file"):
                    continue
                current = (inp.get_attribute("value") or "").strip()
                if current:
                    continue
                label = self._get_label(inp) or ctx
                is_numeric = itype in ("number", "tel") or (inp.get_attribute("pattern") or "") in ("[0-9]*", "\\d*", "\\d+")
                ans = answer_question(label, numeric_only=is_numeric)
                self._scroll(inp)
                inp.click()
                inp.clear()
                inp.send_keys(ans)
                time.sleep(0.1)
            except Exception:
                continue

        for sel_el in self._els("select"):
            try:
                if not sel_el.is_displayed():
                    continue
                select = Select(sel_el)
                current = (select.first_selected_option.text or "").strip().lower()
                if current and current not in {"select", "choose", "select an option"}:
                    continue
                label = self._get_label(sel_el) or ctx
                ans = answer_question(label).lower()
                best = None
                for opt in select.options:
                    text = (opt.text or "").strip().lower()
                    if not text or text in {"select", "choose", "select an option"}:
                        continue
                    if ans == text or ans in text or text in ans:
                        best = opt
                        break
                if best:
                    select.select_by_visible_text(best.text)
            except Exception:
                continue

        for radio in self._els("input[type='radio']"):
            try:
                if not radio.is_displayed() or radio.is_selected():
                    continue
                label = self._get_label(radio) or ctx
                ans = answer_question(label).lower()
                option_text = self._get_option_text(radio).lower()
                if not option_text:
                    continue
                if ans in option_text or option_text in ans or (ans == "yes" and "yes" in option_text):
                    self._click(radio)
            except Exception:
                continue

        for checkbox in self._els("input[type='checkbox']"):
            try:
                if not checkbox.is_displayed() or checkbox.is_selected():
                    continue
                label = (self._get_label(checkbox) or "").lower()
                if any(word in label for word in ["terms", "condition", "consent", "agree", "authorize", "privacy"]):
                    self._click(checkbox)
            except Exception:
                continue

    def _application_success(self):
        page_text = safe(lambda: self.driver.find_element(By.TAG_NAME, "body").text.lower()) or ""
        indicators = [
            "applied successfully",
            "application submitted",
            "applied",
            "successfully applied",
            "already applied",
        ]
        return any(ind in page_text for ind in indicators)

    def _has_apply_ui(self):
        for xpath in [
            "//button[contains(.,'Apply')]",
            "//button[contains(.,'Submit')]",
            "//button[contains(.,'Continue')]",
            "//button[contains(.,'Next')]",
            "//form",
        ]:
            try:
                for el in self._xels(xpath):
                    if el.is_displayed():
                        return True
            except Exception:
                continue
        return False

    def _dismiss_popups(self):
        for xpath in [
            "//button[@aria-label='Close']",
            "//button[contains(.,'Close')]",
            "//button[contains(.,'Skip')]",
            "//button[contains(.,'Maybe later')]",
            "//span[contains(.,'Close')]/ancestor::button[1]",
        ]:
            for btn in self._xels(xpath):
                try:
                    if btn.is_displayed():
                        self._click(btn)
                        time.sleep(0.2)
                except Exception:
                    continue

    def _close_apply_context(self, main_window):
        try:
            if len(self.driver.window_handles) > 1 and self.driver.current_window_handle != main_window:
                self.driver.close()
        except Exception:
            pass
        try:
            if main_window in self.driver.window_handles:
                self.driver.switch_to.window(main_window)
        except Exception:
            self._cleanup_windows()

    def _cleanup_windows(self):
        try:
            while len(self.driver.window_handles) > 1:
                self.driver.switch_to.window(self.driver.window_handles[-1])
                self.driver.close()
            if self.driver.window_handles:
                self.driver.switch_to.window(self.driver.window_handles[0])
        except Exception:
            pass

    def _extract_job_title(self, element):
        scripts = [
            "return arguments[0].closest('article, section, li, div')?.innerText || '';",
            "return arguments[0].parentElement?.innerText || '';",
        ]
        for script in scripts:
            try:
                text = (self._js(script, element) or "").strip()
                title = self._pick_best_title_line(text)
                if title:
                    return title
            except Exception:
                continue
        try:
            return (element.text or "").splitlines()[0].strip()
        except Exception:
            return ""

    def _pick_best_title_line(self, text):
        for line in [part.strip() for part in text.splitlines() if part.strip()]:
            if self._is_target_role(line):
                return line
        for line in [part.strip() for part in text.splitlines() if part.strip()]:
            if len(line) > 6:
                return line
        return ""

    def _is_target_role(self, title):
        normalized = self._normalize_role_text(title)
        if normalized in self.target_roles:
            return True
        return any(role in normalized for role in self.target_roles)

    def _normalize_role_text(self, text):
        return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()

    def _get_label(self, element):
        try:
            label = element.get_attribute("aria-label")
            if label:
                return label.strip()
        except Exception:
            pass
        try:
            element_id = element.get_attribute("id")
            if element_id:
                linked = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{element_id}']")
                for label_el in linked:
                    txt = (label_el.text or "").strip()
                    if txt:
                        return txt
        except Exception:
            pass
        try:
            txt = self._js(
                "var e=arguments[0];"
                "var l=e.closest('label'); if(l && l.innerText) return l.innerText;"
                "var p=e.parentElement; while(p){ if(p.innerText) return p.innerText; p=p.parentElement; }"
                "return '';",
                element,
            )
            if txt:
                return self._pick_best_title_line(txt) or txt.strip().splitlines()[0]
        except Exception:
            pass
        return ""

    def _get_option_text(self, element):
        try:
            text = self._js(
                "var e=arguments[0];"
                "var l=e.closest('label'); if(l && l.innerText) return l.innerText;"
                "return e.parentElement && e.parentElement.innerText ? e.parentElement.innerText : '';",
                element,
            )
            return (text or "").strip()
        except Exception:
            return ""
