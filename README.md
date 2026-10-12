# Price and Stock Tracker

A Python learning project that checks product pages, records price history in SQLite, and alerts when the price crosses a configured threshold. Built with Python, requests and BeautifulSoup; notifications support Discord, Telegram and SMTP email.

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp config.example.json config.json
python price_tracker.py check --dry-run
python price_tracker.py history --product "Example headphones"
```

Edit the product URL, CSS selectors and target price in `config.json`. The example URL is a placeholder, so replace it with a page you are permitted to check. `--dry-run` still downloads pages and writes SQLite history, but does not send alerts. Use `python price_tracker.py --config path/to/config.json check --dry-run` for a custom configuration.

## How it works

1. Load configured products and the previous stored price.
2. Fetch each page and parse the price and optional availability.
3. Save the check to `price_history.sqlite3`.
4. Alert when a product is at or below its target price and the previous price was above the target, or there is no prior check. An explicitly unavailable product does not alert.

Unknown stock status is recorded separately from an unavailable product. The database preserves the original price text and timestamp.

## Tests

```sh
python3 -m unittest -v
```

Eight offline tests cover US/European price formats, invalid prices, threshold crossing, duplicate-alert suppression, stock handling, configuration validation and SQLite history isolation. They require only the Python standard library and do not contact stores or notification services.

## Limitations

This is a local CLI learning project, not a production monitoring service. It parses HTML returned by the server; JavaScript-rendered prices need another approach. Price formats with spaces as thousands separators are not currently supported. Respect each site's terms and avoid frequent requests. Schedule checks externally if needed.

Keep `config.json`, local databases and credentials out of Git. Prefer `PRICE_TRACKER_EMAIL_PASSWORD` for SMTP credentials. Notification configuration uses the exact keys in `config.example.json`; no secrets are included in that example.
