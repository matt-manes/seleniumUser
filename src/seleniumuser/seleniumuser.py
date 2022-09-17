from types import LambdaType
from selenium import webdriver
from selenium.webdriver.firefox.options import Options as OptionsFirefox
from selenium.webdriver.firefox.firefox_profile import FirefoxProfile
from selenium.webdriver.support.ui import Select
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.firefox.service import Service
from pathlib import Path
import time
import random
import os
from timer import Timer
import useragent
from warnings import warn
import sys
from shutil import rmtree

class User:
    """Sits on top of selenium to streamline 
    various tasks used in navigating webpages 
    and filling out forms as well as some
    javascript functions."""
    def __init__(self,
                headless:bool=False,
                implicitWait:int=10,
                openBrowser:bool=True,
                locatorMethod:str='xpath',
                userAgentRotationPeriod:int=None,
                shiftWindow:bool=True,
                downloadDir:str=None,
                driverPath:str=None):
        """If headless = True selenium runs without a browser gui window.\n
        'implicitWait' is the default and what subsequent calls to
        'setImplicitWait()' use when no arg is passed (in seconds).\n
        If openBrowser = False a browser window isn't opened until a page
        is requested or a manual call to openBrowser() is made.\n
        'locatorMethod' can be 'xpath', 'id', 'className', 'name', or 'cssSelector'.\n
        If userAgentRotationPeriod is not None, the browser will be closed
        and reopened with a new userAgent approx. every userAgentRotationPeriod number of minutes.
        Time check happens in get(), so rotation will occur on the next call to get() after
        userAgentRotationPeriod minutes has elapsed.\n
        'shiftWindow' will attempt to move the browser window, if not headless,
        to a second monitor above the monitor the instance was spawned from.
        If no such monitor exists, the window will stay on the monitor where it was spawned.
        'downloadDir' sets the download directory firefox will use for any download buttons that are clicked.\n
        'driverPath' is the path to the 'geckodriver.exe'. If 'geckodriver.exe' is in your system path or
        in either your current working directory or one of it's parent folders, no value needs to be passed."""
        
        self.headless = headless
        self.browserOpen = False
        self.implicitWait = implicitWait
        self.rotationTimer = Timer()
        self.userAgentRotationPeriod = userAgentRotationPeriod 
        self.locatorMethod = locatorMethod
        self.turbo()
        self.keys=Keys
        self.shiftWindow = shiftWindow
        self.downloadDir = downloadDir if downloadDir else str(Path.cwd()/'temp')
        self.driverPath = driverPath
        if not self.driverPath:
            self.searchForDriver()
        if openBrowser:
            self.openBrowser()
        else:
            self.browser = None
    
    def configureBrowser(self):
        """Configure options and profile for the browser."""
        self.options = OptionsFirefox()
        self.options.headless = self.headless
        self.options.add_argument('--disable-blink-features=AutomationControlled')
        self.options.add_argument('--mute-audio')
        self.options.add_argument('--disable-infobars')
        self.options.add_argument('--disable-popup-blocking')
        self.options.set_preference('general.useragent.override', useragent.getRand())
        self.options.set_preference('useAutomationExtension', False)
        if self.downloadDir:
            Path(self.downloadDir).mkdir(parents=True, exist_ok=True)
            self.profile = FirefoxProfile()
            self.profile.set_preference('browser.download.dir', self.downloadDir)
            self.profile.set_preference('browser.download.folderList', 2)
        else:
            self.profile = None
    
    def searchForDriver(self):
        """ Searches for geckodriver.exe in
        current working directory (and parent folders) and the system path.
        Raises a warning if the executable is not found.
        If you don't have it, it can be obtained here:
        https://github.com/mozilla/geckodriver/releases/"""
        cwd = Path.cwd()
        #search cwd and parent folders
        while cwd != cwd.parent:
            if (cwd/'geckodriver.exe').exists():
                self.driverPath = cwd/'geckodriver.exe'
                break
            else:
                cwd = cwd.parent
                if (cwd/'geckodriver.exe').exists():
                    self.driverPath = cwd/'geckodriver.exe'
                    break
        if not self.driverPath:
            envPath = os.environ['PATH']
            found = False
            if sys.platform == 'win32':
                envPaths = envPath.split(';')
            else:
                envPaths = envPath.split(':')
            for path in envPaths:
                if (Path(path)/'geckodriver.exe').exists():
                    found = True
                    break
            if not found:
                warn('Could not find geckodriver.exe\n\
                    It can be obtained for your system here:\n\
                    https://github.com/mozilla/geckodriver/releases/\n\
                    Either add it to your system PATH or place it in\
                    the current working directory seleniumuser is being\
                    invoked from.')
    
    def getBrowserService(self)->Service:
        """ Returns a Service object with logging turned off
        and the path to 'geckodriver.exe' if it was found in the
        current working directory.\n
        If geckodriver.exe is not in your cwd, selenium will
        look for it in your environment's PATH."""
        if self.driverPath:
            service = Service(executable_path=str(self.driverPath), log_path=os.devnull)
        else:
            service = Service(log_path=os.devnull)
        return service
    
    def setImplicitWait(self, waitTime:int=None):
        """ Sets to default time if no arg given. """
        if not waitTime:
            self.browser.implicitly_wait(self.implicitWait)
        else:
            self.browser.implicitly_wait(waitTime)    
    
    def openBrowser(self):
        """ Configures and opens selenium browser. """
        if not self.browserOpen:
            self.configureBrowser()
            service = self.getBrowserService()
            self.browser = webdriver.Firefox(options=self.options, service=service, firefox_profile=self.profile)
            self.setImplicitWait()
            self.browser.maximize_window()
            if self.shiftWindow:
                self.browser.set_window_position(0, -1000)
            self.browser.maximize_window()
            self.browser.set_page_load_timeout(120)
            self.browserOpen = True
            self.tabIndex = 0
            self.script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
            self.rotationTimer.start()
        else:
            warn('Browser already open.')
    
    def closeBrowser(self):
        """ Close browser window and delete temp folder if empty. """
        self.browserOpen = False
        self.browser.quit()
        if len(list(Path(self.downloadDir).iterdir())) == 0:
            rmtree(self.downloadDir)
    
    def openTab(self, url:str='', switchToTab:bool=True):
        """Opens new tab and goes to url.\n
        New tab is inserted after 
        currently active tab."""
        self.script("window.open(arguments[0]);", url)
        if switchToTab:
            self.switchToTab(self.tabIndex+1)
    
    def switchToTab(self, tabIndex:int):
        """ Switch to a tab in browser, zero indexed."""
        self.browser.switch_to.window(self.browser.window_handles[tabIndex])
        self.tabIndex = tabIndex
    
    def getNumTabs(self)->int:
        """ Returns number of tabs open. """
        return len(self.browser.window_handles)
        
    def closeTab(self, tabIndex:int=1):
        """ Close specified tab and
        switches to tab index 0."""
        self.switchToTab(tabIndex)
        self.browser.close()
        self.switchToTab(0)
    
    def get(self, url:str):
        """ Requests webpage at given url and rotates userAgent if necessary. """
        if not self.browserOpen:
            self.openBrowser()
        if self.userAgentRotationPeriod is not None\
        and self.rotationTimer.check(format=False) > (60*self.userAgentRotationPeriod):
            self.rotationTimer.stop()
            self.closeBrowser()
            self.openBrowser()
        self.browser.get(url)
        self.script("Object.defineProperty(navigator, 'webdriver', {get: () => false})")
        self.chill(self.arrivalWait)
        
    def currentUrl(self)->str:
        """ Returns current url. """
        return self.browser.current_url
    
    def deleteCookies(self):
        """ Delete all cookies for
        this browser instance."""
        self.browser.delete_all_cookies()
    
    def turbo(self, engage:bool=True):
        """ When engaged, strings will be sent
        to elements all at once and there will be
        no waiting after actions.\n
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
            self.afterKeyWait = (0.01, 0.5)
            self.afterFieldWait = (1, 2)
            self.afterClickWait = (0.25, 1.5)
            self.arrivalWait = (4, 10)
            self.oneKeyAtATime = True
            self.turboEngaged = False
    
    def chill(self, minMax:tuple):
        """ Sleeps a random amount between minMax[0],minMax[1]. """
        time.sleep(random.uniform(minMax[0], minMax[1]))
    
    def script(self, script:str, args:any=None)->any:
        """ Execute javascript code and returns result. """
        return self.browser.execute_script(script, args)
    
    def remove(self, locator:str):
        """ Removes element from DOM. """
        self.script('arguments[0].remove();', self.find(locator))
    
    def getLength(self, locator:str)->int:
        """ Returns number of child elements for a given element. """
        return int(self.script('return arguments[0].length;', self.find(locator)))
    
    def find(self, locator:str)->WebElement:
        """ Finds web element by locator arg.\n
        Default in class constructor is by xpath.\n
        Other options are 'id', 'className', 'name', and 'cssSelector'.\n
        Returns the webelement."""
        match self.locatorMethod:
            case 'xpath':
                return self.browser.find_element(By.XPATH, locator)
            case 'id':
                return self.browser.find_element(By.ID, locator)
            case 'className':
                return self.browser.find_element(By.CLASS_NAME, locator)
            case 'name':
                return self.browser.find_element(By.NAME, locator)
            case 'cssSelector':
                return self.browser.find_element(By.CSS_SELECTOR, locator)
    
    def findChildren(self, locator:str)->list[WebElement]:
        """ Returns a list of child elements for given locator arg. """
        element = self.find(locator)
        return element.find_elements('xpath', './*')
    
    def scroll(self, amount:int=None, fraction:float=None):
        """ Scroll down page by a line amount if amount is given
        or by a fraction of the page between current position
        and bottom if fraction is given. \n
        Will use 'amount' arg if amount and fraction are both given. \n
        Will scroll entire page height if neither are given. \n
        Scrolls one line at a time if turboEngaged == False."""
        if amount:
            amountToScroll = amount
        elif fraction:
            amountToScroll = int(fraction*(int(self.script('return document.body.scrollHeight;'))-int(self.script('return window.pageYOffset;'))))
        else:
            amountToScroll = int(self.script('return document.body.scrollHeight;'))
        if self.turboEngaged:
            self.script('window.scrollBy(0,arguments[0]);', amountToScroll)
        else:
            for _ in range(abs(amountToScroll)):
                if amountToScroll >= 0:
                    self.script('window.scrollBy(0,1);')
                else:
                    self.script('window.scrollBy(0,-1);')
        self.chill(self.afterClickWait)
    
    def scrollIntoView(self,locator:str)->WebElement:
        """ Scrolls to a given element and returns element.\n
        Note: this will bring the element to the top of the window if able.\n 
        If a webpage has a sticky header element, this
        can obscure the element and cause a crash \n
        if you try to interact with the element without removing the header/obscuring element."""
        element = self.find(locator)
        self.script('arguments[0].scrollIntoView();', element)
        self.chill(self.afterClickWait)
        return element
    
    def text(self,locator:str)->str:
        """ Returns text of WebElement. """
        return self.find(locator).text
    
    def click(self,locator:str)->WebElement:
        """ Finds, clicks on, and then returns WebElement. """
        element = self.find(locator)
        element.click()
        self.chill(self.afterClickWait)
        return element
    
    def clear(self,locator:str)->WebElement:
        """ Clears content of WebElement and then returns WebElement. """
        element = self.find(locator)
        element.clear()
        self.chill(self.afterClickWait)
        return element
    
    def switchToIframe(self,locator:str):
        """ Switch to an iframe from given locator. """
        self.browser.switch_to.frame(self.find(locator))
    
    def switchToParentFrame(self):
        """ Move up a frame level from current frame. """
        self.browser.switch_to.parent_frame()
    
    def select(self, locator:str, method:str, choice:str|int|tuple)->WebElement:
        """ Select a choice from Select element by value
        or index and return element.\n
        If using index method, choice can be a 
        tuple of length 2 where a random number between
        the given numbers (inclusive bounds) is chosen."""
        element = self.click(locator)
        match method:
            case 'value':
                Select(element).select_by_value(choice)
            case 'index':
                if type(choice) == tuple:
                    choice = random.randint(choice[0], choice[1])
                Select(element).select_by_index(choice)
        self.chill(self.afterFieldWait)
        return element
    
    def selectOptions(self, locators:list[str], maxSelections:int=None,
                    minSelections:int=1)->WebElement:
        """ Clicks a random number of options b/t min and max from locators.\n
        Typically used for a set of checkboxes or similar field element.\n
        If only 'locators' arg passed, maxSelectionswill be entire list.\n
        Returns last WebElement."""
        if not maxSelections:
            maxSelections = len(locators)
        for option in random.sample(locators, k=random.randint(minSelections, maxSelections)):
            element = self.click(option)
        return element
    
    def getOptionsClickList(self, numOptions:int, maxChoices:int=1, minChoices:int=1)->list[str]:
        """ Similar to 'selectOptions()', but for use with the 'fillNext()' method.\n
        Creates a list of length 'numOptions' where every element is 'skip'.\n
        A random number of elements between 'minChoices' and 'maxChoices' are
        replaced with 'keys.SPACE' (interpreted as a click by almost all web forms)."""
        l = ['skip']*numOptions
        selectedIndexes = []
        for i in range(random.randint(minChoices, maxChoices)):
            index = random.randint(0, numOptions-1)
            while index in selectedIndexes:
                index = random.randint(0, numOptions-1)
            selectedIndexes.append(index)
            l[index] = self.keys.SPACE
        return l
    
    def sendKeys(self, locator:str, data:str, clickFirst:bool=True,
                clearFirst:bool=False)->WebElement:
        """ Types data into element and returns the element."""
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
    
    def fill(self, data:dict)->WebElement:
        """ Takes a dict of the form {locator:string}
        or {locator:('action',data)} and fills all fields accordingly.\n 
        Useable tuples are ('select','value'), ('downArrow',numberOfPresses).\n
        Returns last WebElement."""
        for locator,datum in data.items():
            if datum[0] == 'select':
                element = self.selectByValue(locator, datum[1])
            elif datum[0] == 'downArrow':
                element = self.click(locator)
                for _ in range(datum[1]):
                    element.send_keys(Keys.ARROW_DOWN)
                    self.chill(self.afterKeyWait)
                element.send_keys(Keys.SPACE)
            else:
                element = self.sendKeys(locator, datum)
        return element
    
    def fillNext(self, data:list, startElement:WebElement=None)->WebElement:
        """ Tabs from current element to next element and fills field with data[i].\n
        Uses active_element if startElement isn't given.\n
        An item in data can be a tuple: ('downArrow',numberOfPresses) or 'skip' to tab to next
        element without performing any actions.\n
        If 'numberOfPresses' is a tuple of two numbers, a random number between the two (inclusive)
        will be chosen.\n
        Returns last WebElement."""
        element = self.browser.switch_to.active_element if not startElement else startElement
        for datum in data:
            element.send_keys(Keys.TAB)
            element = self.browser.switch_to.active_element
            self.chill(self.afterKeyWait)
            if datum[0] == 'downArrow':
                if type(datum[1]) == tuple:
                    times = random.randint(datum[1][0], datum[1][1])
                else:
                    times = datum[1]
                for _ in range(times):
                    element.send_keys(Keys.ARROW_DOWN)
                    self.chill(self.afterKeyWait)
            elif datum == 'skip':
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
    
    def waitUntil(self, condition:LambdaType, maxWait:float=10, pollRate:float=0.1):
        """ Checks condition repeatedly until either it is true, 
        or the maxWait is exceeded.\n
        Useful for determing whether a form has been successfully submitted."""
        startTime = time.time()
        while True:
            try:
                if condition():
                    time.sleep(1)
                    break
                elif (time.time() - startTime) > maxWait:
                    raise TimeoutError(f'maxWait exceeded in waitUntil({condition})')
                else:
                    time.sleep(pollRate)
            except:
                if (time.time()-startTime) > maxWait:
                    raise TimeoutError(f'maxWait exceeded in waitUntil({condition})')
                else:
                    time.sleep(pollRate)
    
    def dismissAlert(self):
        """ Dismiss alert dialog. """
        self.browser.switch_to.alert.dismiss()

if __name__ == '__main__':
    user = User(headless=True)
    input('...')
    user.closeBrowser()