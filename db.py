import sqlite3
from contextlib import contextmanager

# Keep the database beside this file in the project directory.
DB_NAME = "hardware_khata.db"


@contextmanager
def get_connection():
    """Yield a configured SQLite connection, commit safely, and always close it."""
    conn = sqlite3.connect(DB_NAME, timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 30000")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def _columns(conn, table_name):
    return {row[1] for row in conn.execute(f"PRAGMA table_info({table_name})")}


def initialize_database():
    """Create missing tables and add missing compatible columns without deleting existing data."""
    with get_connection() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                category TEXT,
                unit TEXT NOT NULL DEFAULT 'pcs',
                cost_price REAL NOT NULL DEFAULT 0,
                selling_price REAL NOT NULL DEFAULT 0,
                stock REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS customers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                pan_number TEXT,
                opening_balance REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS suppliers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                phone TEXT,
                pan_number TEXT,
                opening_balance REAL NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sales (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                invoice_no TEXT NOT NULL UNIQUE,
                sale_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                customer_name TEXT NOT NULL DEFAULT 'Walk-in Customer',
                customer_phone TEXT,
                subtotal REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                amount_paid REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'Cash'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sale_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                sale_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_price REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (sale_id) REFERENCES sales(id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS stock_movements (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                movement_type TEXT NOT NULL,
                quantity_change REAL NOT NULL,
                stock_before REAL NOT NULL,
                stock_after REAL NOT NULL,
                reason TEXT NOT NULL,
                notes TEXT,
                created_by TEXT NOT NULL DEFAULT 'system',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchases (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                supplier_name TEXT NOT NULL,
                supplier_phone TEXT,
                supplier_invoice TEXT,
                subtotal REAL NOT NULL DEFAULT 0,
                discount REAL NOT NULL DEFAULT 0,
                total REAL NOT NULL DEFAULT 0,
                amount_paid REAL NOT NULL DEFAULT 0,
                payment_method TEXT NOT NULL DEFAULT 'Cash',
                notes TEXT,
                created_by TEXT NOT NULL DEFAULT 'owner'
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS purchase_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                purchase_id INTEGER NOT NULL,
                product_id INTEGER,
                product_name TEXT NOT NULL,
                quantity REAL NOT NULL,
                unit_cost REAL NOT NULL,
                line_total REAL NOT NULL,
                FOREIGN KEY (purchase_id) REFERENCES purchases(id),
                FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE SET NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                expense_date TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                amount REAL NOT NULL CHECK(amount >= 0),
                payment_method TEXT NOT NULL DEFAULT 'Cash',
                created_by TEXT NOT NULL DEFAULT 'owner',
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Non-destructive compatibility migrations for earlier versions.
        # Existing data is kept; columns are added only when missing.
        existing_sales = _columns(conn, "sales")
        for name, definition in {
            "sale_date": "TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP",
            "customer_name": "TEXT NOT NULL DEFAULT 'Walk-in Customer'",
            "customer_phone": "TEXT",
            "subtotal": "REAL NOT NULL DEFAULT 0",
            "discount": "REAL NOT NULL DEFAULT 0",
            "total": "REAL NOT NULL DEFAULT 0",
            "amount_paid": "REAL NOT NULL DEFAULT 0",
            "payment_method": "TEXT NOT NULL DEFAULT 'Cash'",
        }.items():
            if name not in existing_sales:
                conn.execute(f"ALTER TABLE sales ADD COLUMN {name} {definition}")

        existing_sale_items = _columns(conn, "sale_items")
        for name, definition in {
            "sale_id": "INTEGER",
            "product_id": "INTEGER",
            "product_name": "TEXT NOT NULL DEFAULT ''",
            "quantity": "REAL NOT NULL DEFAULT 0",
            "unit_price": "REAL NOT NULL DEFAULT 0",
            "line_total": "REAL NOT NULL DEFAULT 0",
        }.items():
            if name not in existing_sale_items:
                conn.execute(f"ALTER TABLE sale_items ADD COLUMN {name} {definition}")
