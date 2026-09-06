# Automated Price Drop & Stock Tracker

This is a small Python tracker for that one product that you are constantly checking manually.
You simply point it at the page with your product in it, have it parse the price and stock
text for each product. Each price check gets added to a local SQLite database, and it can ping
you when the price finally drops under the specified threshold.

It is extremely simple. There is no account management, no dashboard of prices or stock level, no
hidden mystery service running on some other server. There is just a single python script, a single config
file, and your computer.

What the script can do

- Scrapes one or more product pages. This uses the excellent requests library and BeautifulSoup.
- Records every price check made to price_history.sqlite3.
- Tracks the stock status if that text is clearly available on the page.
- Alerts using Discord, Telegram or Email.
- Allows for printing the saved price history to the console.

1. Getting setup

It is best practice to use a virtual environment so you don't install it in your global
Python. This allows you to install whatever you need for specific projects without cluttering.

``bash

python3 -m venv .venv

source .venv/bin/activate

pip install -r requirements.txt

`

2. Creating your config file

Simply copy the example file:

`bash

cp config.example.json config.json

`

Then edit config.json. You'll want to replace the example product with the one(s)
that you want to track. Below is an example of how your config.json will look.

`json

{

"name": "My headphones",

"url": "https://store.example.com/headphones",

"target_price": 129.99,

"currency": "USD",

"price_selector": ".product-price",

"stock_selector": ".stock-status",

"instocktext": "in stock"

}

`

Most importantly is price_selector. This should be a valid CSS selector for your
product's price on the page. I would generally recommend one of two approaches for this:

1. Open your target product page. Right click the price and hit 'Inspect'. Find an
  element in the HTML structure of that price in your web inspector and copy its class
  or id. Put it into the price_selector field of your config file. E.g.:

- ".price" means find an element with the class name "price".
  - "#priceblockourprice" means find the element with the id "priceblockourprice".
  - "[data-testid='price']" means find the element that has the attribute data-testid
    and that attribute's value is exactly price.

2. If your price is only displayed after the page finishes loading with JavaScript
  you'll need to eventually switch to a JavaScript renderer like Playwright. You can
  then use similar techniques but those are considerably more advanced than what this
  script does currently.

3. Running a test check

You can run a test check to ensure you have entered your selectors properly.

`bash

python price_tracker.py check --dry-run

`

This will run the check, save the price in your local database, but it will just print the alerts
rather than sending any messages or emails. I'd recommend the few initial checks like this.

4. Picking an alerting method

You'll only need to fill out one of the following two depending on which alerting system you choose. Leave the
unnecessary fields empty.

# Discord webhook

From your desired server on Discord, right-click and create a new webhook, then paste the URL

you're given into this field in your config.json file:

`json

"discordwebhookurl": "https://discord.com/api/webhooks/..."

`

# Telegram bot

On Telegram, start a chat with BotFather. He'll guide you through creating a new bot and will
give you an API token for that bot. Then, after you send your bot a message in the Telegram app, you can
access it with BotFather and see your "Chat ID" in there. Fill in both fields:

`json

"telegrambottoken": "123456:ABC...",

"telegramchatid": "123456789"

`

# Email

You'll first need to have email enabled and to supply your SMTP details.

`json

"email": {

"enabled": true,

"smtp_host": "smtp.gmail.com",

"smtp_port": 587,

"username": "you@example.com",

"password": "",

"from": "you@example.com",

"to": "you@example.com"

}

`

If you're using Gmail you'll need to create an app password for this since its
normal password won't work when run from outside of Google's own applications. If your
account has 2-factor authentication then even app passwords don't work, in which case
you'll want to find a workaround like forwarding to a service that accepts simpler
logins if you desperately want email alerts. You can also store your password here
(though it is checked into git) or by setting it as an environment variable, which is generally

more secure:

`bash

export PRICETRACKEREMAIL_PASSWORD="your-app-password"

`

config.json is already set up to be ignored by Git, so you won't push your private URLs,
passwords, or tokens accidentally.

5. Reading the history

You can read any recorded prices for any tracked products.

`bash

python price_tracker.py history

`

Or specify a single product name.

`bash

python price_tracker.py history --product "My headphones"

`

As all the data is in SQLite, you're also able to open the price_history.sqlite3 file
and browse it with a DB browser if you would like to take a closer look.

6. Automated checking

Now set your machine to run it regularly. On Linux/macOS this is typically done with cron.

`bash

crontab -e

`

Enter this line to run every hour. Remember to replace /path/to/this/project with your
project's actual path and to make sure the virtual environment is activated with the full path to python.

`cron

0     cd /path/to/this/project && .venv/bin/python price_tracker.py check

`

On Windows you can do this with Task Scheduler. Set the action to be
'Start a program'. In 'Program/script' put: python price_tracker.py check. If python
is not added to the PATH, then specify the full path to python.

It's recommended to not have it check too frequently. Most websites frown upon you
hammering their servers, and the more checks you perform, the more network traffic you
have. Check hourly or on a similar cycle depending on the urgency and the website.

Adding more products

You just need to add more objects to the products list in your config.json file. Each product can have its own selectors and target price:

`json

{

"name": "Keyboard",

"url": "https://store.example.com/keyboard",

"target_price": 79.99,

"price_selector": ".sale-price",

"stock_selector": ".availability",

"instocktext": "available"

}

``

A word to the wise

Websites often update their HTML structure without prior notice. If you find your script stops working, it means the selectors in your config file are outdated. You'll just need to find new selectors and update them. 

Also, be mindful of the terms and conditions of the website you are monitoring, and don't push the limits or over-utilize your request frequency, as websites will frequently block abusive clients. 

This script is designed for personal price monitoring.
