import sqlite3
from contextlib import closing
from datetime import datetime
import streamlit as st

DB_FILE = "orders.db"

# רשימת פריטים קבועה בראש
ITEMS = [
    "קולה",
    "ספרייט",
    "מים",
    "במבה",
    "ביסלי",
    "שוקולד",
    "לחם",
    "חלב",
    "ביצים",
    "גבינה",
]


def get_connection():
    return sqlite3.connect(DB_FILE, check_same_thread=False)


def init_db():
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                customer_name TEXT NOT NULL,
                address TEXT NOT NULL,
                items TEXT NOT NULL,
                is_paid INTEGER NOT NULL DEFAULT 0,
                created_at TEXT NOT NULL
            )
            """
        )
        conn.commit()


def add_order(customer_name: str, address: str, items: list[str], is_paid: bool):
    items_text = ", ".join(items)
    created_at = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO orders (customer_name, address, items, is_paid, created_at)
            VALUES (?, ?, ?, ?, ?)
            """,
            (customer_name, address, items_text, int(is_paid), created_at),
        )
        conn.commit()


def get_orders(search_text: str = ""):
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        if search_text.strip():
            like_value = f"%{search_text.strip()}%"
            cur.execute(
                """
                SELECT id, customer_name, address, items, is_paid, created_at
                FROM orders
                WHERE customer_name LIKE ? OR address LIKE ? OR items LIKE ?
                ORDER BY id DESC
                """,
                (like_value, like_value, like_value),
            )
        else:
            cur.execute(
                """
                SELECT id, customer_name, address, items, is_paid, created_at
                FROM orders
                ORDER BY id DESC
                """
            )
        return cur.fetchall()


def update_paid_status(order_id: int, is_paid: bool):
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute(
            "UPDATE orders SET is_paid = ? WHERE id = ?",
            (int(is_paid), order_id),
        )
        conn.commit()


def delete_order(order_id: int):
    with closing(get_connection()) as conn:
        cur = conn.cursor()
        cur.execute("DELETE FROM orders WHERE id = ?", (order_id,))
        conn.commit()


init_db()
st.set_page_config(page_title="רישום הזמנות", layout="wide")
st.title("רישום הזמנות")
st.caption("אפליקציה קצרה עם זיכרון מקומי באמצעות SQLite")

with st.sidebar:
    st.header("רשימת פריטים קבועה")
    for item in ITEMS:
        st.write(f"• {item}")

st.subheader("הזמנה חדשה")
with st.form("new_order_form", clear_on_submit=True):
    customer_name = st.text_input("שם")
    address = st.text_input("כתובת")
    selected_items = st.multiselect("פריטים בהזמנה", ITEMS)
    is_paid = st.checkbox("שולם")
    submitted = st.form_submit_button("שמור הזמנה")

    if submitted:
        if not customer_name.strip():
            st.error("צריך להזין שם.")
        elif not address.strip():
            st.error("צריך להזין כתובת.")
        elif not selected_items:
            st.error("צריך לבחור לפחות פריט אחד.")
        else:
            add_order(customer_name.strip(), address.strip(), selected_items, is_paid)
            st.success("ההזמנה נשמרה.")
            st.rerun()

st.divider()
st.subheader("הזמנות שמורות")
search_text = st.text_input("חיפוש לפי שם / כתובת / פריטים")
orders = get_orders(search_text)

if not orders:
    st.info("אין עדיין הזמנות שמורות.")
else:
    for order_id, customer_name, address, items, is_paid, created_at in orders:
        with st.container(border=True):
            col1, col2, col3 = st.columns([4, 2, 1])

            with col1:
                st.markdown(f"**{customer_name}**")
                st.write(f"כתובת: {address}")
                st.write(f"הזמנה: {items}")
                st.caption(f"נוצר בתאריך: {created_at}")

            with col2:
                paid_now = st.checkbox(
                    "שולם",
                    value=bool(is_paid),
                    key=f"paid_{order_id}",
                )
                if paid_now != bool(is_paid):
                    update_paid_status(order_id, paid_now)
                    st.rerun()

            with col3:
                if st.button("מחק", key=f"delete_{order_id}"):
                    delete_order(order_id)
                    st.rerun()
