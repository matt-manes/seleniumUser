import os
import random
import sys
import time
from pathlib import Path
from types import LambdaType
from typing import Any
from warnings import warn

from audioToText import getTextFromUrl
from bs4 import BeautifulSoup
from loopTimer import Timer
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support.ui import Select
from whosYourAgent import getAgent


class User:
    """Sits on top of selenium to streamline
    automation and scraping tasks."""

    def __init__(
        self,
        headless: bool = False,
        browserType: str = "firefox",
        implicitWait: int = 10,
        pageLoadTimeout: int = 60,
        openBrowser: bool = True,
        locatorMethod: str = "xpath",
        randomizeUserAgent: bool = True,
        userAgentRotationPeriod: int = None,
        moveWindowBy: tuple[int, int] = (0, -1000),
        downloadDir: str | Path = None,
        driverPath: str | Path = None,
    ):
        """
        :param headless: If True, browser window will not be visible.

        :param browserType: Which browser to use. Can be 'firefox' or 'chrome'.

        :param implicitWait: Number of seconds to look for a specified element before
        selenium considers it missing and throws an exception.

        :param pageLoadTimeout: Time in seconds for selenium to wait for a page to load
        before throwing an exception.

        :param openBrowser: If True, opens a browser window when a User object is created.
        If False, a manual call to self.openBrowser() must be made.

        :param locatorMethod: The locator type User should expect to be given.
        Can be 'xpath', 'id', 'className', 'name', or 'cssSelector'.
        Every member function with a 'locator' argument refers to a string matching
        the current locatorMethod.

        :param randomizeUserAgent: If True, a random useragent will be used whenever
        the browser is opened. If False, the native useragent will be used.

        :param userAgentRotationPeriod: If not None, the browser window will be closed
        and reopened with a new useragent every userAgentRotationPeriod number of minutes.
        Rotation occurs on the first call to self.get() after the time period has elapsed.
        Ignored if randomizeUserAgent is False.

        :param moveWindowBy: The x and y amount of pixels to move the browser window by after opening.

        :param downloadDir: The download folder to use. If None, the default folder will be used.

        :param driverPath: The path to the webdriver executable selenium should use.
        If None, the system PATH will be checked for the executable.
        If the executable isn't found, the parent directories and the immediate child directories
        of the current working directory will be searched.
        """
        self.headless = headless
        browserType = browserType.lower()
        if browserType in ["firefox", "chrome"]:
            self.browserType = browserType
        else:
            raise ValueError("'browserType' parameter must be 'firefox' or 'chrome'")
        self.browserOpen = False
        self.implicitWait = implicitWait
        self.pageLoadTimeout = pageLoadTimeout
        self.rotationTimer = Timer()
        self.timer = Timer()
        self.timer.start()
        self.randomizeUserAgent = randomizeUserAgent
        self.userAgentRotationPeriod = userAgentRotationPeriod
        self.locatorMethod = locatorMethod
        self.turbo()
        self.keys = Keys
        self.moveWindowBy = moveWindowBy
        self.downloadDir = downloadDir
        self.driverPath = driverPath
        if not self.driverPath:
            self.searchForDriver()
        if openBrowser:
            self.openBrowser()
        else:
            self.browser = None

    def configureFirefox(self) -> FirefoxService:
        """Configure options and profile for firefox."""
        self.options = FirefoxOptions()
        self.options.headless = self.headless
        self.options.set_preference(
            "widget.windows.window_occlusion_tracking.enabled", False
        )
        self.options.set_preference("dom.webaudio.enabled", False)
        if self.randomizeUserAgent:
            self.options.set_preference("general.useragent.override", getAgent())
        if self.downloadDir:
            Path(self.downloadDir).mkdir(parents=True, exist_ok=True)
            self.profile = FirefoxProfile()
            self.profile.set_preference("browser.download.dir", str(self.downloadDir))
            self.profile.set_preference("browser.download.folderList", 2)
        else:
            self.profile = None
        self.service = FirefoxService(
            executable_path=str(self.driverPath), log_path=os.devnull
        )

    def configureChrome(self) -> ChromeService:
        """Configure options and profile for chrome."""
        self.options = ChromeOptions()
        self.options.headless = self.headless
        self.options.add_argument("--disable-blink-features=AutomationControlled")
        self.options.add_argument("--mute-audio")
        self.options.add_argument("--disable-infobars")
        self.options.add_argument("--disable-notifications")
        self.options.add_argument("--log-level=3")
        if self.randomizeUserAgent:
            self.options.add_argument(f"--user-agent={getAgent()}")
        self.options.add_experimental_option("useAutomationExtension", False)
        if self.downloadDir:
            Path(self.downloadDir).mkdir(parents=True, exist_ok=True)
            self.options.add_experimental_option(
                "prefs", {"download.default_directory": str(self.downloadDir)}
            )
        self.service = ChromeService(
            executable_path=str(self.driverPath), log_path=os.devnull
        )

    def searchForDriver(self):
        """Searches for the webdriver executable."""
        cwd = Path.cwd()
        found = False
        match self.browserType:
            case "firefox":
                driver = "geckodriver.exe"
            case "chrome":
                driver = "chromedriver.exe"
        # search PATH
        envPath = os.environ["PATH"]
        if sys.platform == "win32":
            envPaths = envPath.split(";")
        else:
            envPaths = envPath.split(":")
        for path in envPaths:
            if (Path(path) / driver).exists():
                self.driverPath = Path(path) / driver
                found = True
                break
        # check current working directory and parent folders
        if not found:
            while cwd != cwd.parent:
                if (cwd / driver).exists():
                    self.driverPath = cwd / driver
                    found = True
                    break
                cwd = cwd.parent
            # check top most level
            if not found and (cwd / driver).exists():
                self.driverPath = cwd / driver
                found = True
        # check child folders (only 1 level down)
        if not found:
            for child in Path.cwd().iterdir():
                if child.is_dir() and (child / driver).exists():
                    self.driverPath = child / driver
                    found = True
        if not found:
            raise Exception(f"Could not find {driver}")

    def setImplicitWait(self, waitTime: int = None):
        """Sets to default time if no arg given."""
        if not waitTime:
            self.browser.implicitly_wait(self.implicitWait)
        else:
            self.browser.implicitly_wait(waitTime)

    def openBrowser(self):
        """Configures and opens selenium browser."""
        if not self.browserOpen:
            match self.browserType:
                case "firefox":
                    self.configureFirefox()
                    self.browser = webdriver.Firefox(
                        options=self.options,
                        service=self.service,
                        firefox_profile=self.profile,
                    )
                case "chrome":
                    self.configureChrome()
                    self.browser = webdriver.Chrome(
                        options=self.options, service=self.service
                    )
            self.setImplicitWait()
            self.browser.maximize_window()
            self.browser.set_window_position(self.moveWindowBy[0], self.moveWindowBy[1])
            self.browser.maximize_window()
            self.browser.set_page_load_timeout(self.pageLoadTimeout)
            self.browserOpen = True
            self.tabIndex = 0
            self.rotationTimer.start()
        else:
            warn("Browser already open.")

    def closeBrowser(self):
        """Close browser window."""
        self.browserOpen = False
        self.browser.quit()

    def openTab(self, url: str = "", switchToTab: bool = True):
        """Opens new tab and, if provided, goes to url.

        New tab is inserted after currently active tab."""
        self.script("window.open(arguments[0]);", url)
        if switchToTab:
            self.switchToTab(self.tabIndex + 1)

    def switchToTab(self, tabIndex: int):
        """Switch to a tab in browser, zero indexed."""
        self.browser.switch_to.window(self.browser.window_handles[tabIndex])
        self.tabIndex = tabIndex

    def getNumTabs(self) -> int:
        """Returns number of tabs open."""
        return len(self.browser.window_handles)

    def closeTab(self, tabIndex: int = 1):
        """Close specified tab and
        switches to tab index 0."""
        self.switchToTab(tabIndex)
        self.browser.close()
        self.switchToTab(0)

    def get(self, url: str):
        """Requests webpage at given url and rotates userAgent if necessary."""
        if not self.browserOpen:
            self.openBrowser()
        if (
            self.randomizeUserAgent
            and self.userAgentRotationPeriod is not None
            and self.rotationTimer.check(format=False)
            > (60 * self.userAgentRotationPeriod)
        ):
            self.rotationTimer.stop()
            self.closeBrowser()
            self.openBrowser()
        self.browser.get(url)
        self.script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
        self.chill(self.arrivalWait)

    def getSoup(self) -> BeautifulSoup:
        """Returns a BeautifulSoup object
        of the current page source."""
        return BeautifulSoup(self.browser.page_source, "html.parser")

    def currentUrl(self) -> str:
        """Returns current url of active tab."""
        return self.browser.current_url

    def deleteCookies(self):
        """Delete all cookies for
        this browser instance."""
        self.browser.delete_all_cookies()

    def turbo(self, engage: bool = True):
        """When engaged, strings will be sent
        to elements all at once and there will be
        no waiting after actions.

        When disengaged, strings will be sent to elements
        'one key at a time' with randomized amounts of
        time between successive keys and after actions."""
        if engage:
            self.afterKeyWait = (0, 0)
            self.afterFieldWait = (0, 0)
            self.afterClickWait = (0, 0)
            self.arrivalWait = (1, 1)
            self.oneKeyAtATime = False
            self.turboEngaged = True
        else:
            self.afterKeyWait = (0.1, 0.5)
            self.afterFieldWait = (1, 2)
            self.afterClickWait = (0.25, 1.5)
            self.arrivalWait = (4, 10)
            self.oneKeyAtATime = True
            self.turboEngaged = False

    def chill(self, minMax: tuple[float, float]):
        """Sleeps a random amount
        between minMax[0] and minMax[1]."""
        time.sleep(random.uniform(minMax[0], minMax[1]))

    def script(self, script: str, args: Any = None) -> Any:
        """Execute javascript code and returns result."""
        return self.browser.execute_script(script, args)

    def remove(self, locator: str):
        """Removes element from DOM."""
        self.script("arguments[0].remove();", self.find(locator))

    def getLength(self, locator: str) -> int:
        """Returns number of child elements for a given element."""
        return int(self.script("return arguments[0].length;", self.find(locator)))

    def find(self, locator: str) -> WebElement:
        """Finds and returns a WebElement."""
        match self.locatorMethod:
            case "xpath":
                return self.browser.find_element(By.XPATH, locator)
            case "id":
                return self.browser.find_element(By.ID, locator)
            case "className":
                return self.browser.find_element(By.CLASS_NAME, locator)
            case "name":
                return self.browser.find_element(By.NAME, locator)
            case "cssSelector":
                return self.browser.find_element(By.CSS_SELECTOR, locator)

    def findChildren(self, locator: str) -> list[WebElement]:
        """Returns a list of child WebElements
        for given locator arg."""
        element = self.find(locator)
        return element.find_elements("xpath", "./*")

    def scroll(self, amount: int = None, fraction: float = None):
        """Scroll web page.
        :param amount: The number of lines to scroll if not None.

        :param fraction: The amount between 0.0 and 1.0
        of the page height to scroll.

        If values are provided for both arguments,
        amount will be used.

        If values are provided for neither argument,
        the entire page length will be scrolled.

        Scrolls one line at a time if self.turbo is False."""
        if amount:
            amountToScroll = amount
        elif fraction:
            amountToScroll = int(
                fraction
                * (
                    int(self.script("return document.body.scrollHeight;"))
                    - int(self.script("return window.pageYOffset;"))
                )
            )
        else:
            amountToScroll = int(self.script("return document.body.scrollHeight;"))
        if self.turboEngaged:
            self.script("window.scrollBy(0,arguments[0]);", amountToScroll)
        else:
            for _ in range(abs(amountToScroll)):
                if amountToScroll >= 0:
                    self.script("window.scrollBy(0,1);")
                else:
                    self.script("window.scrollBy(0,-1);")
        self.chill(self.afterClickWait)

    def scrollIntoView(self, locator: str) -> WebElement:
        """Scrolls to a given element and returns the element."""
        element = self.find(locator)
        self.script("arguments[0].scrollIntoView();", element)
        self.chill(self.afterClickWait)
        return element

    def text(self, locator: str) -> str:
        """Returns text of WebElement."""
        return self.find(locator).text

    def click(self, locator: str) -> WebElement:
        """Clicks on and returns WebElement."""
        element = self.find(locator)
        element.click()
        self.chill(self.afterClickWait)
        return element

    def clear(self, locator: str) -> WebElement:
        """Clears content of WebElement if able
        and then returns WebElement."""
        element = self.find(locator)
        element.clear()
        self.chill(self.afterClickWait)
        return element

    def switchToIframe(self, locator: str):
        """Switch to an iframe from given locator."""
        self.browser.switch_to.frame(self.find(locator))

    def switchToParentFrame(self):
        """Move up a frame level from current frame."""
        self.browser.switch_to.parent_frame()

    def select(
        self, locator: str, method: str, choice: str | int | tuple
    ) -> WebElement:
        """Select a choice from Select element.
        Returns the Select element from the locator string,
        not the option element that is selected.

        :param method: Can be 'value' or 'index'

        :param choice: The option to select.

        If method is 'value', then choice should be
        the html 'value' attribute of the desired option.

        If method is 'index', choice can either be a single
        int for the desired option or it can be a two-tuple.
        If the tuple is provided, a random option between the
        two indicies (inclusive) will be selected."""
        element = self.click(locator)
        match method:
            case "value":
                Select(element).select_by_value(choice)
            case "index":
                if type(choice) == tuple:
                    choice = random.randint(choice[0], choice[1])
                Select(element).select_by_index(choice)
        self.chill(self.afterFieldWait)
        return element

    def clickElements(
        self, locators: list[str], maxSelections: int = None, minSelections: int = 1
    ) -> WebElement:
        """Click a random number of WebElements
        and return the last WebElement clicked.

        :param locators: A list of element locators to choose from.

        :param maxSelections: The maximum number of elements to click.
        If None, the maximum will be the length of the locators list.

        :param minSelections: The minimum number of elements to click.

        e.g. self.clickElements([xpath1, xpath2, xpath3, xpath4], maxSelections=3)
        will click between 1 and 3 random elements from the list.
        """
        if not maxSelections:
            maxSelections = len(locators)
        for option in random.sample(
            locators, k=random.randint(minSelections, maxSelections)
        ):
            element = self.click(option)
        return element

    def getClickList(
        self, numOptions: int, maxChoices: int = 1, minChoices: int = 1
    ) -> list[str]:
        """Similar to self.clickElements(), but for use with the self.fillNext() method.

        Creates a list of length 'numOptions' where every element is 'skip'.

        A random number of elements in the list between 'minChoices' and 'maxChoices' are
        replaced with 'keys.SPACE' (interpreted as a click by almost all web forms)."""
        clickList = ["skip"] * numOptions
        selectedIndexes = []
        for i in range(random.randint(minChoices, maxChoices)):
            index = random.randint(0, numOptions - 1)
            while index in selectedIndexes:
                index = random.randint(0, numOptions - 1)
            selectedIndexes.append(index)
            clickList[index] = self.keys.SPACE
        return clickList

    def sendKeys(
        self, locator: str, data: str, clickFirst: bool = True, clearFirst: bool = False
    ) -> WebElement:
        """Types data into element and returns the element.

        :param data: The string to send to the element.

        :param clickFirst: If True, the element is clicked on
        before the data is sent.

        :param clearFirst: If True, the current text of the element
        is cleared before the data is sent."""
        element = self.click(locator) if clickFirst else self.find(locator)
        if clearFirst:
            element.clear()
            self.chill(self.afterClickWait)
        if self.oneKeyAtATime:
            for ch in str(data):
                element.send_keys(ch)
                self.chill(self.afterKeyWait)
        else:
            element.send_keys(str(data))
        self.chill(self.afterFieldWait)
        return element

    def fillNext(
        self, data: list[str | tuple], startElement: WebElement = None
    ) -> WebElement:
        """Fills a form by tabbing from the current WebElement
        to the next one and using the corresponding item in data.
        Returns the last WebElement.

        :param data: A list of form data. If an item is a string (except for 'skip')
        it will be typed into the current WebElement.

        An item in data can be a two-tuple of the form
        ('downArrow', numberOfPresses:int|tuple[int, int]).

        If numberOfPresses is a single int, Keys.ARROW_DOWN will be sent
        that many times to the WebElement.

        If numberOfPresses is a tuple, Keys.ARROW_DOWN will be sent a random
        number of times between numberOfPresses[0] and numberOfPresses[1] inclusive.
        This is typically for use with Select elements.

        An item in data can also be 'skip', which will perform no action on the current
        WebElement and will continue to the next one.

        :param startElement: The WebElement to start tabbing from.
        The currently active element will be used if startElement is None.

        Note: The function tabs to the next element before sending data,
        so the startElement should the WebElement before the one
        that should receive data[0].
        """
        element = (
            self.browser.switch_to.active_element if not startElement else startElement
        )
        for datum in data:
            element.send_keys(Keys.TAB)
            element = self.browser.switch_to.active_element
            self.chill(self.afterKeyWait)
            if datum[0] == "downArrow":
                if type(datum[1]) == tuple:
                    times = random.randint(datum[1][0], datum[1][1])
                else:
                    times = datum[1]
                for _ in range(times):
                    element.send_keys(Keys.ARROW_DOWN)
                    self.chill(self.afterKeyWait)
            elif datum == "skip":
                self.chill(self.afterKeyWait)
            else:
                if self.turboEngaged:
                    element.send_keys(str(datum))
                else:
                    for ch in str(datum):
                        element.send_keys(ch)
                        self.chill(self.afterKeyWait)
            self.chill(self.afterFieldWait)
        return element

    def waitUntil(
        self, condition: LambdaType, maxWait: float = 10, pollingInterval: float = 0.1
    ):
        """Checks condition repeatedly until either it is true,
        or the maxWait is exceeded.

        Raises a TimeoutError if the condition doesn't success within maxWait.

        Useful for determing whether a form has been successfully submitted.

        :param condition: The condition function to check.

        :param maxWait: Number of seconds to continue checking condition
        before throwing a TimeoutError.

        :param pollingInterval: The number of seconds to sleep before
        checking the condition function again after it fails.

        e.g. self.waitUntil(lambda: 'Successfully Submitted' in self.text('//p[@id="form-output"]))"""
        startTime = time.time()
        while True:
            try:
                if condition():
                    time.sleep(1)
                    break
                elif (time.time() - startTime) > maxWait:
                    raise TimeoutError(f"maxWait exceeded in waitUntil({condition})")
                else:
                    time.sleep(pollingInterval)
            except:
                if (time.time() - startTime) > maxWait:
                    raise TimeoutError(f"maxWait exceeded in waitUntil({condition})")
                else:
                    time.sleep(pollingInterval)

    def dismissAlert(self):
        """Dismiss alert dialog."""
        self.browser.switch_to.alert.dismiss()

    def solveRecaptchaV3(
        self,
        outerIframeXpath: str = '//iframe[@title="reCAPTCHA"]',
        innerIframeXpath: str = '//iframe[@title="recaptcha challenge expires in two minutes"]',
    ):
        """Pass google recaptcha v3 by solving an audio puzzle.

        :param outerIframeXpath: Xpath to the iframe containing the recaptcha checkbox.
        If it's the recaptcha without the initial checkbox that just shows the image puzzle,
        pass None to this argument.

        """
        locatorMethod = self.locatorMethod
        self.locatorMethod = "xpath"
        try:
            if outerIframeXpath:
                self.switchToIframe(outerIframeXpath)
                self.click('//*[@id="recaptcha-anchor"]')
                self.switchToParentFrame()
            self.switchToIframe(innerIframeXpath)
            self.click('//*[@id="recaptcha-audio-button"]')
            mp3Url = self.find(
                '//a[@class="rc-audiochallenge-tdownload-link"]'
            ).get_attribute("href")
            text = getTextFromUrl(mp3Url, ".mp3")
            self.sendKeys('//*[@id="audio-response"]', text)
            self.click('//*[@id="recaptcha-verify-button"]')
        except Exception as e:
            print(e)
            raise Exception("Could not solve captcha")
        finally:
            self.switchToParentFrame()
            self.locatorMethod = locatorMethod
