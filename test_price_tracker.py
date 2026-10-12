import sqlite3
import tempfile
import unittest
from pathlib import Path
from price_tracker import (Product, ProductSnapshot, parse_price, should_alert,
                           init_database, save_snapshot, get_previous_price, load_config)

class TrackerTests(unittest.TestCase):
    def setUp(self):
        self.product = Product('Headphones', 'https://example.com/item', 100, '.price')
    def snapshot(self, price=90, stock=True, time='2026-01-01T10:00:00+00:00', product=None):
        return ProductSnapshot(product or self.product, price, str(price), stock, None, time)
    def test_us_and_european_price_formats(self):
        for text, expected in [('$1,234.56',1234.56),('EUR 1.234,56',1234.56),('99,95 EUR',99.95),('$99.95',99.95)]:
            with self.subTest(text=text): self.assertEqual(parse_price(text),expected)
    def test_unavailable_price_raises(self):
        with self.assertRaises(ValueError): parse_price('Contact us for price')
    def test_threshold_crossing_alerts(self):
        self.assertTrue(should_alert(self.snapshot(),110))
        self.assertTrue(should_alert(self.snapshot(),None))
        self.assertTrue(should_alert(self.snapshot(100),110))
    def test_repeated_below_threshold_check_does_not_alert(self):
        self.assertFalse(should_alert(self.snapshot(),95))
    def test_unavailable_and_expensive_products_do_not_alert(self):
        self.assertFalse(should_alert(self.snapshot(stock=False),110))
        self.assertFalse(should_alert(self.snapshot(price=101),110))
    def test_sqlite_history_is_scoped_to_product_url_and_ordered(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'history.sqlite3'; init_database(db); init_database(db)
            self.assertIsNone(get_previous_price(db,self.product))
            save_snapshot(db,self.snapshot(110,time='2026-01-01T10:00:00+00:00'))
            save_snapshot(db,self.snapshot(90,time='2026-01-02T10:00:00+00:00'))
            other=Product('Headphones','https://example.com/other',100,'.price')
            save_snapshot(db,self.snapshot(10,time='2026-01-03T10:00:00+00:00',product=other))
            self.assertEqual(get_previous_price(db,self.product),90)
            self.assertEqual(get_previous_price(db,other),10)
    def test_unknown_stock_is_saved_as_sql_null(self):
        with tempfile.TemporaryDirectory() as folder:
            db=Path(folder)/'history.sqlite3'; init_database(db)
            save_snapshot(db,self.snapshot(stock=None))
            with sqlite3.connect(db) as con:
                self.assertIsNone(con.execute('SELECT in_stock FROM price_checks').fetchone()[0])
    def test_config_without_products_is_rejected(self):
        with tempfile.TemporaryDirectory() as folder:
            config=Path(folder)/'config.json'; config.write_text('{"products": []}')
            with self.assertRaises(ValueError): load_config(config)

if __name__ == '__main__': unittest.main()
