# seleniumUser
Install with:
<pre>
python -m pip install git+https://github.com/matt-manes/seleniumUser
</pre>
Git must be installed and in your PATH.<br><br>
A package that sits ontop of Selenium to streamline scraping and automation workflows.<br>
Currently supports using firefox or chrome.<br>
You will need to have the appropriate web driver executable for the browser and your system in either the system PATH or a location passed to the User class constructor.<br>
Firefox: https://github.com/mozilla/geckodriver/releases<br>
Chrome: https://chromedriver.chromium.org/downloads<br>

Basic usage submitting a generic form with fields for first name, last name, email address, and phone number:
<pre>
from seleniumUser import User
user = User(browserType="firefox")
user.get('https://somewebsite.com')
user.sendKeys('//input[@id="first-name"]', 'Bill')
user.fillNext(['Billson', 'bill@bill.com', '5345548486'])
user.click('//button[@id="submit"]')
try:
    user.waitUntil(lambda: 'Submission Received' in user.text('//p[@id="confirmation-message"]'))
    print('Submission success.')
except TimeoutError:
    print('Submission failed.')
user.closeBrowser()
</pre>
The User class supports being used with a context manager if you'd rather not worry about closing the browser before exiting the script:
<pre>
from seleniumUser import User
with User(browserType="firefox") as user:
    user.get('https://somewebsite.com')
    user.sendKeys('//input[@id="first-name"]', 'Bill')
    user.fillNext(['Billson', 'bill@bill.com', '5345548486'])
    user.click('//button[@id="submit"]')
    try:
        user.waitUntil(lambda: 'Submission Received' in user.text('//p[@id="confirmation-message"]'))
        print('Submission success.')
    except TimeoutError:
        print('Submission failed.')
</pre>
