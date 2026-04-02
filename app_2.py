import sqlite3
from contextlib import closing
from datetime import datetime

import pandas as pd
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


def inject_rtl_css():
    st.markdown(
        """
        <style>
        html, body, [class*="css"] {
            direction: rtl;
            text-align: right;
        }

        .stApp {
            direction: rtl;
        }

        h1, h2, h3, h4, h5, h6, p, label, div, span {
            direction: rtl;
            text-align: right;
        }

        .stTextInput input, .stTextArea textarea, .stMultiSelect div[data-baseweb="select"] > div {
            direction: rtl !important;
            text-align: right !important;
        }

        div[data-testid="stForm"] {
            border: 1px solid #e5e7eb;
            border-radius: 16px;
            padding: 1rem;
        }

        div[data-testid="stDataFrame"] {
            direction: rtl;
        }

        @media (max-width: 768px) {
            .block-container {
                padding-top: 1rem;
                padding-right: 0.8rem;
                padding-left: 0.8rem;
                padding-bottom: 2rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


init_db()
st.set_page_config(page_title="רישום הזמנות", page_icon="🧾", layout="centered")
inject_rtl_css()

st.title("🧾 רישום הזמנות")
st.caption("אפליקציה פשוטה בעברית עם זיכרון מקומי")

with st.expander("רשימת פריטים קבועה", expanded=True):
    cols = st.columns(2)
    half = (len(ITEMS) + 1) // 2
    for i, item in enumerate(ITEMS[:half]):
        cols[0].write(f"• {item}")
    for item in ITEMS[half:]:
        cols[1].write(f"• {item}")

form_tab, orders_tab = st.tabs(["הזמנה חדשה", "רשימת הזמנות"])

with form_tab:
    st.subheader("הוספת הזמנה")
    with st.form("new_order_form", clear_on_submit=True):
        customer_name = st.text_input("שם", placeholder="למשל: משה כהן")
        address = st.text_input("כתובת", placeholder="למשל: הרצל 12, תל אביב")
        selected_items = st.multiselect("פריטים בהזמנה", ITEMS, placeholder="בחר פריטים")
        is_paid = st.checkbox("שולם")
        submitted = st.form_submit_button("שמור הזמנה", use_container_width=True)

        if submitted:
            if not customer_name.strip():
                st.error("צריך להזין שם.")
            elif not address.strip():
                st.error("צריך להזין כתובת.")
            elif not selected_items:
                st.error("צריך לבחור לפחות פריט אחד.")
            else:
                add_order(customer_name.strip(), address.strip(), selected_items, is_paid)
                st.success("ההזמנה נשמרה בהצלחה.")
                st.rerun()

    st.info(
        "אפשר להוסיף השלמה אוטומטית לכתובות כמו וייז/גוגל, אבל זה דורש חיבור ל-API חיצוני. "
        "בשלב הבא אפשר לשלב Google Places או שירות מפות אחר."
    )

with orders_tab:
    st.subheader("רשימת הזמנות")
    search_text = st.text_input("חיפוש לפי שם / כתובת / פריטים", placeholder="חפש הזמנה...")
    orders = get_orders(search_text)

    if not orders:
        st.info("אין עדיין הזמנות שמורות.")
    else:
        df = pd.DataFrame(
            orders,
            columns=["מזהה", "שם", "כתובת", "הזמנה", "שולם", "נוצר בתאריך"],
        )
        df["שולם"] = df["שולם"].astype(bool)

        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "מזהה": st.column_config.NumberColumn("מזהה", disabled=True),
                "שם": st.column_config.TextColumn("שם", disabled=True),
                "כתובת": st.column_config.TextColumn("כתובת", disabled=True),
                "הזמנה": st.column_config.TextColumn("הזמנה", disabled=True, width="medium"),
                "שולם": st.column_config.CheckboxColumn("שולם"),
                "נוצר בתאריך": st.column_config.TextColumn("נוצר בתאריך", disabled=True),
            },
            disabled=["מזהה", "שם", "כתובת", "הזמנה", "נוצר בתאריך"],
            key="orders_editor",
        )

        for _, row in edited_df.iterrows():
            original_paid = bool(df.loc[df["מזהה"] == row["מזהה"], "שולם"].iloc[0])
            if bool(row["שולם"]) != original_paid:
                update_paid_status(int(row["מזהה"]), bool(row["שולם"]))
                st.rerun()

        st.markdown("### מחיקת הזמנה")
        order_options = {
            f"#{row['מזהה']} - {row['שם']} - {row['כתובת']}": int(row["מזהה"])
            for _, row in df.iterrows()
        }
        selected_label = st.selectbox("בחר הזמנה למחיקה", list(order_options.keys()))
        if st.button("מחק הזמנה", type="secondary", use_container_width=True):
            delete_order(order_options[selected_label])
            st.success("ההזמנה נמחקה.")
            st.rerun()
