import time
import logging
from selenium import webdriver
from selenium.webdriver.edge.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)


def create_driver(headless=False):
    opts = Options()
    opts.add_argument("--start-maximized")
    opts.add_argument("--disable-blink-features=AutomationControlled")
    opts.add_experimental_option("excludeSwitches", ["enable-automation"])
    opts.add_argument(r"--user-data-dir=C:\Users\Gokul\AppData\Local\Microsoft\Edge\User Data")
    opts.add_argument("--profile-directory=Default")
    if headless:
        opts.add_argument("--headless=new")
    driver = webdriver.Edge(options=opts)
    driver.implicitly_wait(5)
    return driver


def wait_and_click(driver, by, value, timeout=10):
    el = WebDriverWait(driver, timeout).until(EC.element_to_be_clickable((by, value)))
    el.click()
    return el


def wait_for(driver, by, value, timeout=10):
    return WebDriverWait(driver, timeout).until(EC.presence_of_element_located((by, value)))


def slow_type(element, text, delay=0.05):
    for ch in text:
        element.send_keys(ch)
        time.sleep(delay)
