# Automated Price Drop & Stock Tracker

This is a small Python tracker for that one product you keep checking manually.
It opens a product page, reads the current price and stock text, stores every
check in a local SQLite database, and can ping you when the price finally drops
under your target.

It is intentionally simple. No account system, no dashboard, no mystery service
running in the background. Just a script, a config file, and your own machine.

## What it does

- Scrapes one or more product pages with `requests` and `BeautifulSoup`
- Saves every price check to `price_history.sqlite3`
- Tracks stock text when the page exposes it
- Alerts through Discord, Telegram, or email
- Lets you print recent price history from the command line

## 1. Install it

Create a virtual environment first. It keeps the project tidy and makes it easy
to remove later.

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 2. Create your config file

Copy the example config:

```bash
cp config.example.json config.json
```

Open `config.json` and replace the example product with the real one you want to
track.

```json
{
  "name": "My headphones",
  "url": "https://store.example.com/headphones",
  "target_price": 129.99,
  "currency": "USD",
  "price_selector": ".product-price",
  "stock_selector": ".stock-status",
  "in_stock_text": "in stock"
}
```

The most important part is `price_selector`. It is a CSS selector that points to
the price on the product page.

A quick way to find it:

1. Open the product page in your browser.
2. Right click the price and choose **Inspect**.
3. Look for a useful class or id near the highlighted HTML.
4. Put that selector in `config.json`.

For example:

- `".price"` means an element with `class="price"`
- `"#priceblock_ourprice"` means an element with `id="priceblock_ourprice"`
- `"[data-testid='price']"` means an element with that exact attribute

If the website renders prices only after JavaScript runs, this basic version may
not see the price. That is when you would swap the scraper to Playwright later.

## 3. Run one check

```bash
python price_tracker.py check --dry-run
```

Dry run mode still scrapes and saves the price, but it prints alerts instead of
sending them. I like doing the first few checks this way so I can confirm the
selector is right before my phone starts buzzing.

You should see something like:

```text
My headphones: USD 119.99 (in stock) target USD 129.99
Dry run alert:
Price drop found: My headphones
...
```

## 4. Pick an alert method

You only need one of these. Leave the others blank.

### Discord webhook

Create a webhook in your Discord server, then paste the URL into:

```json
"discord_webhook_url": "https://discord.com/api/webhooks/..."
```

This is the easiest option if you already use Discord on your phone.

### Telegram bot

Create a bot with BotFather, get the bot token, then put the token and your chat
id into:

```json
"telegram_bot_token": "123456:ABC...",
"telegram_chat_id": "123456789"
```

### Email

Turn email on in the config:

```json
"email": {
  "enabled": true,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "username": "you@example.com",
  "password": "",
  "from": "you@example.com",
  "to": "you@example.com"
}
```

For Gmail, use an app password rather than your normal account password. You can
store it directly in `config.json`, but using an environment variable is safer:

```bash
export PRICE_TRACKER_EMAIL_PASSWORD="your-app-password"
```

`config.json` is ignored by Git so your private URLs and tokens do not get
committed by accident.

## 5. Check the saved history

```bash
python price_tracker.py history
```

Or for one product:

```bash
python price_tracker.py history --product "My headphones"
```

The database is just SQLite, so you can also open it with any SQLite browser if
you want to poke around.

## 6. Run it automatically

On macOS or Linux, cron is enough:

```bash
crontab -e
```

Run it every hour:

```cron
0 * * * * cd /path/to/this/project && .venv/bin/python price_tracker.py check
```

On Windows, use Task Scheduler and point it at:

```text
python price_tracker.py check
```

Run it politely. Checking every few minutes is usually overkill and some shops
will block noisy traffic. Every hour or every few hours is a better default.

## Adding more products

Add another object to the `products` list:

```json
{
  "name": "Keyboard",
  "url": "https://store.example.com/keyboard",
  "target_price": 79.99,
  "price_selector": ".sale-price",
  "stock_selector": ".availability",
  "in_stock_text": "available"
}
```

Each product can have its own selectors and target price.

## A couple of honest notes

Some stores change their HTML often. If the script suddenly says it cannot find a
price, inspect the page again and update the selector.

Some stores also dislike scraping. Keep the check interval reasonable, do not try
to bypass logins or anti-bot protections, and respect the site's terms. This is
meant for personal price watching, not hammering a shop's servers.
