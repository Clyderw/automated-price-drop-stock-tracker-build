#!/usr/bin/env python3
"""
Small price and stock tracker for product pages.

The tracker reads products from a JSON config file, scrapes the current price and
availability, saves each check to SQLite, and sends an alert when a product moves
below its target price.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import smtplib
import sqlite3
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from email.message import EmailMessage
from pathlib import Path
from typing import Any


DEFAULT_CONFIG = "config.json"
DEFAULT_DATABASE = "price_history.sqlite3"
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)


@dataclass
class Product:
    name: str
    url: str
    target_price: float
    price_selector: str
    stock_selector: str | None = None
    in_stock_text: str | None = None
    currency: str = "USD"


@dataclass
class ProductSnapshot:
    product: Product
    price: float
    raw_price: str
    in_stock: bool | None
    raw_stock: str | None
    checked_at: str


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(
            f"Could not find {path}. Copy config.example.json to config.json first."
        )

    with path.open("r", encoding="utf-8") as config_file:
        config = json.load(config_file)

    if "products" not in config or not config["products"]:
        raise ValueError("Your config needs at least one product in the products list.")

    return config


def build_products(config: dict[str, Any]) -> list[Product]:
    products: list[Product] = []
    for item in config["products"]:
        products.append(
            Product(
                name=item["name"],
                url=item["url"],
                target_price=float(item["target_price"]),
                price_selector=item["price_selector"],
                stock_selector=item.get("stock_selector"),
                in_stock_text=item.get("in_stock_text"),
                currency=item.get("currency", config.get("currency", "USD")),
            )
        )
    return products


def init_database(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS price_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_name TEXT NOT NULL,
                url TEXT NOT NULL,
                price REAL NOT NULL,
                currency TEXT NOT NULL,
                raw_price TEXT NOT NULL,
                in_stock INTEGER,
                raw_stock TEXT,
                target_price REAL NOT NULL,
                checked_at TEXT NOT NULL
            )
            """
        )
        connection.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_price_checks_product_time
            ON price_checks (product_name, checked_at)
            """
        )


def save_snapshot(database_path: Path, snapshot: ProductSnapshot) -> None:
    stock_value = None if snapshot.in_stock is None else int(snapshot.in_stock)
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO price_checks (
                product_name, url, price, currency, raw_price, in_stock,
                raw_stock, target_price, checked_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                snapshot.product.name,
                snapshot.product.url,
                snapshot.price,
                snapshot.product.currency,
                snapshot.raw_price,
                stock_value,
                snapshot.raw_stock,
                snapshot.product.target_price,
                snapshot.checked_at,
            ),
        )


def get_previous_price(database_path: Path, product: Product) -> float | None:
    with sqlite3.connect(database_path) as connection:
        row = connection.execute(
            """
            SELECT price FROM price_checks
            WHERE product_name = ? AND url = ?
            ORDER BY checked_at DESC
            LIMIT 1
            """,
            (product.name, product.url),
        ).fetchone()
    return None if row is None else float(row[0])


def scrape_product(product: Product, timeout: int = 20) -> ProductSnapshot:
    import requests
    from bs4 import BeautifulSoup

    response = requests.get(
        product.url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=timeout,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    price_element = soup.select_one(product.price_selector)
    if price_element is None:
        raise ValueError(
            f"Could not find the price for {product.name!r}. "
            f"Check the CSS selector: {product.price_selector}"
        )

    raw_price = clean_text(price_element.get_text(" ", strip=True))
    price = parse_price(raw_price)

    raw_stock = None
    in_stock = None
    if product.stock_selector:
        stock_element = soup.select_one(product.stock_selector)
        if stock_element is not None:
            raw_stock = clean_text(stock_element.get_text(" ", strip=True))
            if product.in_stock_text:
                in_stock = product.in_stock_text.lower() in raw_stock.lower()
            else:
                in_stock = not contains_out_of_stock_words(raw_stock)

    return ProductSnapshot(
        product=product,
        price=price,
        raw_price=raw_price,
        in_stock=in_stock,
        raw_stock=raw_stock,
        checked_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )


def clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def parse_price(raw_price: str) -> float:
    match = re.search(r"(\d[\d,.]*(?:[,.]\d{1,2})?)", raw_price)
    if not match:
        raise ValueError(f"Could not read a price from: {raw_price!r}")

    value = match.group(1)
    if "," in value and "." in value:
        if value.rfind(",") > value.rfind("."):
            value = value.replace(".", "").replace(",", ".")
        else:
            value = value.replace(",", "")
    elif "," in value and "." not in value:
        value = value.replace(",", ".")

    return float(value)


def contains_out_of_stock_words(raw_stock: str) -> bool:
    text = raw_stock.lower()
    out_of_stock_markers = [
        "out of stock",
        "sold out",
        "unavailable",
        "currently unavailable",
        "not available",
    ]
    return any(marker in text for marker in out_of_stock_markers)


def should_alert(snapshot: ProductSnapshot, previous_price: float | None) -> bool:
    if snapshot.in_stock is False:
        return False

    if snapshot.price > snapshot.product.target_price:
        return False

    return previous_price is None or previous_price > snapshot.product.target_price


def send_alert(config: dict[str, Any], snapshot: ProductSnapshot, previous_price: float | None) -> None:
    alert_config = config.get("alerts", {})
    message = build_alert_message(snapshot, previous_price)

    sent_anything = False
    if alert_config.get("discord_webhook_url"):
        send_discord_alert(alert_config["discord_webhook_url"], message)
        sent_anything = True

    if alert_config.get("telegram_bot_token") and alert_config.get("telegram_chat_id"):
        send_telegram_alert(
            alert_config["telegram_bot_token"],
            alert_config["telegram_chat_id"],
            message,
        )
        sent_anything = True

    if alert_config.get("email", {}).get("enabled"):
        send_email_alert(alert_config["email"], snapshot.product.name, message)
        sent_anything = True

    if not sent_anything:
        print("Alert would send, but no alert channel is configured.")
        print(message)


def build_alert_message(snapshot: ProductSnapshot, previous_price: float | None) -> str:
    previous = "unknown" if previous_price is None else f"{snapshot.product.currency} {previous_price:.2f}"
    stock = "unknown" if snapshot.in_stock is None else ("in stock" if snapshot.in_stock else "out of stock")
    return (
        f"Price drop found: {snapshot.product.name}\n"
        f"Now: {snapshot.product.currency} {snapshot.price:.2f}\n"
        f"Target: {snapshot.product.currency} {snapshot.product.target_price:.2f}\n"
        f"Previous check: {previous}\n"
        f"Stock: {stock}\n"
        f"Link: {snapshot.product.url}"
    )


def send_discord_alert(webhook_url: str, message: str) -> None:
    import requests

    response = requests.post(webhook_url, json={"content": message}, timeout=20)
    response.raise_for_status()


def send_telegram_alert(bot_token: str, chat_id: str, message: str) -> None:
    import requests

    api_url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
    response = requests.post(
        api_url,
        json={"chat_id": chat_id, "text": message, "disable_web_page_preview": False},
        timeout=20,
    )
    response.raise_for_status()


def send_email_alert(email_config: dict[str, Any], product_name: str, message: str) -> None:
    smtp_host = email_config["smtp_host"]
    smtp_port = int(email_config.get("smtp_port", 587))
    username = email_config["username"]
    password = email_config.get("password") or os.environ.get("PRICE_TRACKER_EMAIL_PASSWORD")
    sender = email_config.get("from", username)
    recipient = email_config["to"]

    if not password:
        raise ValueError(
            "Email is enabled, but no password was provided. Set it in config.json "
            "or use the PRICE_TRACKER_EMAIL_PASSWORD environment variable."
        )

    email = EmailMessage()
    email["Subject"] = f"Price drop: {product_name}"
    email["From"] = sender
    email["To"] = recipient
    email.set_content(message)

    with smtplib.SMTP(smtp_host, smtp_port) as smtp:
        smtp.starttls()
        smtp.login(username, password)
        smtp.send_message(email)


def show_history(database_path: Path, product_name: str | None = None, limit: int = 20) -> None:
    query = """
        SELECT checked_at, product_name, price, currency, in_stock
        FROM price_checks
    """
    params: tuple[Any, ...] = ()
    if product_name:
        query += " WHERE product_name = ?"
        params = (product_name,)
    query += " ORDER BY checked_at DESC LIMIT ?"
    params = (*params, limit)

    with sqlite3.connect(database_path) as connection:
        rows = connection.execute(query, params).fetchall()

    if not rows:
        print("No history yet. Run a check first.")
        return

    for checked_at, name, price, currency, in_stock in rows:
        stock = "unknown" if in_stock is None else ("in stock" if in_stock else "out of stock")
        print(f"{checked_at} | {name} | {currency} {price:.2f} | {stock}")


def check_once(config_path: Path, dry_run: bool = False) -> int:
    config = load_config(config_path)
    database_path = Path(config.get("database", DEFAULT_DATABASE))
    init_database(database_path)

    failures = 0
    for product in build_products(config):
        try:
            previous_price = get_previous_price(database_path, product)
            snapshot = scrape_product(product)
            save_snapshot(database_path, snapshot)

            stock = "unknown" if snapshot.in_stock is None else ("in stock" if snapshot.in_stock else "out of stock")
            print(
                f"{product.name}: {product.currency} {snapshot.price:.2f} "
                f"({stock}) target {product.currency} {product.target_price:.2f}"
            )

            if should_alert(snapshot, previous_price):
                if dry_run:
                    print("Dry run alert:")
                    print(build_alert_message(snapshot, previous_price))
                else:
                    send_alert(config, snapshot, previous_price)
        except Exception as error:
            failures += 1
            print(f"Could not check {product.name}: {error}", file=sys.stderr)

    return 1 if failures else 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Track product prices and stock status.")
    parser.add_argument("--config", default=DEFAULT_CONFIG, help="Path to your JSON config file.")

    subparsers = parser.add_subparsers(dest="command")
    check_parser = subparsers.add_parser("check", help="Scrape every configured product once.")
    check_parser.add_argument("--dry-run", action="store_true", help="Print alerts instead of sending them.")

    history_parser = subparsers.add_parser("history", help="Show recent saved checks.")
    history_parser.add_argument("--product", help="Only show history for one product name.")
    history_parser.add_argument("--limit", type=int, default=20, help="How many rows to print.")

    args = parser.parse_args()
    config_path = Path(args.config)

    if args.command in (None, "check"):
        return check_once(config_path, dry_run=getattr(args, "dry_run", False))

    if args.command == "history":
        config = load_config(config_path)
        database_path = Path(config.get("database", DEFAULT_DATABASE))
        init_database(database_path)
        show_history(database_path, args.product, args.limit)
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
