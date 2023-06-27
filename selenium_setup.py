from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from selenium.webdriver import ActionChains
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.by import By
from selenium.common.exceptions import NoSuchElementException
from selenium.common.exceptions import StaleElementReferenceException
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.chrome.service import Service

# def setup(headless=False, download_dir=None):


# CHROME VERSION

def setup(headless=True, download_dir=None, browser='Chrome'):

    if browser == 'Chrome':
        # Initialize driver setup
        options = Options()
        options.headless = headless
        options.add_argument("--log-level=3")
        options.add_argument('--ignore-certificate-errors-spki-list')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument("--start-maximized")
        options.add_argument("enable-experimental-web-platform-features")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        if dir:
            options.add_experimental_option('prefs', {'download.default_directory': download_dir})

        # Create instance of webdriver using webdriver_manager library (chrome)
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=options)

        # change download directory
        driver.command_executor._commands["send_command"] = ("POST", '/session/$sessionId/chromium/send_command')
        params = {'cmd': 'Page.setDownloadBehavior', 'params': {'behavior': 'allow', 'downloadPath': download_dir}}
        command_result = driver.execute("send_command", params)

        driver.implicitly_wait(1)
        ignored_exceptions=(NoSuchElementException, StaleElementReferenceException)
        wait = WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions)
        actions = ActionChains(driver)

        return driver, wait, actions

    else:
        # Initialize driver setup
        options = FirefoxOptions()
        options.headless = headless
        options.add_argument("--log-level=3")
        options.add_argument('--ignore-certificate-errors-spki-list')
        options.add_argument('--ignore-certificate-errors')
        options.add_argument('--ignore-ssl-errors')
        options.add_argument("--start-maximized")
        options
        if dir:
            options.set_preference("browser.download.dir", download_dir)

        # Create instance of webdriver using webdriver_manager library (firefox)
        service = Service(GeckoDriverManager().install())
        driver = webdriver.Firefox(service=service, options=options)


        driver.implicitly_wait(1)
        ignored_exceptions=(NoSuchElementException, StaleElementReferenceException)
        wait = WebDriverWait(driver, 5, ignored_exceptions=ignored_exceptions)
        actions = ActionChains(driver)

        return driver, wait, actions
