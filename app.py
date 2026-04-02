import math
import sqlite3
from contextlib import closing
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st
from geopy.geocoders import Nominatim

DB_FILE = "orders.db"

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

        .small-card {
            border: 1px solid #e5e7eb;
            border-radius: 14px;
            padding: 0.8rem 1rem;
            margin-bottom: 0.7rem;
            background: #ffffff;
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


@st.cache_resource
def get_geolocator():
    return Nominatim(user_agent="orders_route_planner_app")


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def geocode_address(address: str):
    geolocator = get_geolocator()
    try:
        query = f"{address}, ישראל"
        location = geolocator.geocode(query, timeout=10)
        if location:
            return {
                "address": address,
                "lat": location.latitude,
                "lon": location.longitude,
                "display_name": location.address,
                "ok": True,
            }
    except Exception:
        pass

    return {
        "address": address,
        "lat": None,
        "lon": None,
        "display_name": "לא נמצאה התאמה מדויקת",
        "ok": False,
    }


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1 = math.radians(lat1)
    p2 = math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def nearest_neighbor_route(start_point, stops):
    if not stops:
        return []

    remaining = stops.copy()
    route = []
    current = start_point

    while remaining:
        next_stop = min(
            remaining,
            key=lambda s: haversine_km(current["lat"], current["lon"], s["lat"], s["lon"]),
        )
        distance = haversine_km(current["lat"], current["lon"], next_stop["lat"], next_stop["lon"])
        next_stop["distance_from_previous_km"] = round(distance, 2)
        route.append(next_stop)
        current = next_stop
        remaining.remove(next_stop)

    return route


def build_waze_link_by_coords(lat, lon):
    return f"https://www.waze.com/ul?ll={lat},{lon}&navigate=yes"


def build_waze_link_by_text(address):
    return f"https://www.waze.com/ul?q={quote(address)}&navigate=yes"


def get_order_rows_for_table(search_text: str = ""):
    orders = get_orders(search_text)
    df = pd.DataFrame(
        orders,
        columns=["מזהה", "שם", "כתובת", "הזמנה", "שולם", "נוצר בתאריך"],
    )
    if not df.empty:
        df["שולם"] = df["שולם"].astype(bool)
    return df


init_db()
st.set_page_config(page_title="רישום הזמנות", page_icon="🧾", layout="centered")
inject_rtl_css()

st.title("🧾 רישום הזמנות")
st.caption("אפליקציה פשוטה בעברית עם רשימת הזמנות, אימות כתובת בסיסי ומסלול יומי")

with st.expander("רשימת פריטים קבועה", expanded=True):
    cols = st.columns(2)
    half = (len(ITEMS) + 1) // 2
    for item in ITEMS[:half]:
        cols[0].write(f"• {item}")
    for item in ITEMS[half:]:
        cols[1].write(f"• {item}")

form_tab, orders_tab, route_tab = st.tabs(["הזמנה חדשה", "רשימת הזמנות", "מסלול יומי"])

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

    st.markdown("### בדיקת כתובת לפני שמירה")
    verify_address = st.text_input(
        "בדוק כתובת",
        placeholder="כתוב כתובת בישראל כדי לבדוק אם נמצאה התאמה",
        key="verify_address_input",
    )
    if st.button("בדוק כתובת", use_container_width=True):
        if verify_address.strip():
            result = geocode_address(verify_address.strip())
            if result["ok"]:
                st.success("נמצאה כתובת.")
                st.write(result["display_name"])
                st.markdown(f"[פתח בוויז]({build_waze_link_by_coords(result['lat'], result['lon'])})")
            else:
                st.warning("לא נמצאה התאמה מדויקת. נסה לכתוב עיר, רחוב ומספר.")
        else:
            st.warning("צריך להזין כתובת לבדיקה.")

    st.info("האימות כאן הוא בסיסי. למסלול מומלץ מלא עם אופטימיזציה אמיתית עדיף בעתיד לחבר API ייעודי של מפות/מסלולים.")

with orders_tab:
    st.subheader("רשימת הזמנות")
    search_text = st.text_input("חיפוש לפי שם / כתובת / פריטים", placeholder="חפש הזמנה...")
    df = get_order_rows_for_table(search_text)

    if df.empty:
        st.info("אין עדיין הזמנות שמורות.")
    else:
        edited_df = st.data_editor(
            df,
            use_container_width=True,
            hide_index=True,
            num_rows="fixed",
            column_config={
                "מזהה": st.column_config.NumberColumn("מזהה", disabled=True),
                "שם": st.column_config.TextColumn("שם", disabled=True),
                "כתובת": st.column_config.TextColumn("כתובת", disabled=True, width="large"),
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

with route_tab:
    st.subheader("מסלול יומי")
    st.caption("הסדר כאן הוא המלצה מקורבת לפי כתובות שזוהו, לא אופטימיזציית כבישים מלאה.")

    all_orders_df = get_order_rows_for_table("")
    unpaid_only = st.checkbox("הצג רק הזמנות שלא שולמו", value=False)

    if all_orders_df.empty:
        st.info("אין הזמנות להצגת מסלול.")
    else:
        route_source_df = all_orders_df.copy()
        if unpaid_only:
            route_source_df = route_source_df[route_source_df["שולם"] == False]

        if route_source_df.empty:
            st.info("אין כרגע הזמנות מתאימות למסלול.")
        else:
            start_address = st.text_input(
                "נקודת התחלה",
                placeholder="למשל: הבית, רחוב האלון 5, באר שבע",
                key="route_start_address",
            )

            if st.button("חשב סדר נסיעה מומלץ", use_container_width=True):
                if not start_address.strip():
                    st.warning("צריך להזין נקודת התחלה.")
                else:
                    start_geo = geocode_address(start_address.strip())
                    if not start_geo["ok"]:
                        st.error("לא הצלחתי לזהות את נקודת ההתחלה.")
                    else:
                        geocoded_stops = []
                        unresolved = []

                        for _, row in route_source_df.iterrows():
                            geo = geocode_address(str(row["כתובת"]).strip())
                            if geo["ok"]:
                                geocoded_stops.append(
                                    {
                                        "id": int(row["מזהה"]),
                                        "name": row["שם"],
                                        "address": row["כתובת"],
                                        "items": row["הזמנה"],
                                        "paid": bool(row["שולם"]),
                                        "created_at": row["נוצר בתאריך"],
                                        "lat": geo["lat"],
                                        "lon": geo["lon"],
                                        "matched_address": geo["display_name"],
                                    }
                                )
                            else:
                                unresolved.append(f"{row['שם']} — {row['כתובת']}")

                        if not geocoded_stops:
                            st.error("לא הצלחתי לזהות אף כתובת למסלול.")
                        else:
                            route = nearest_neighbor_route(start_geo, geocoded_stops)

                            result_rows = []
                            map_rows = []
                            for i, stop in enumerate(route, start=1):
                                stop["order_index"] = i
                                result_rows.append(
                                    {
                                        "סדר": i,
                                        "שם": stop["name"],
                                        "כתובת": stop["address"],
                                        "התאמה": stop["matched_address"],
                                        "הזמנה": stop["items"],
                                        "מרחק מהנקודה הקודמת (קמ)": stop["distance_from_previous_km"],
                                        "שולם": stop["paid"],
                                        "וויז": build_waze_link_by_coords(stop["lat"], stop["lon"]),
                                    }
                                )
                                map_rows.append({"lat": stop["lat"], "lon": stop["lon"]})

                            result_df = pd.DataFrame(result_rows)
                            st.session_state["route_result_df"] = result_df
                            st.session_state["route_map_rows"] = pd.DataFrame(map_rows)
                            st.session_state["route_unresolved"] = unresolved
                            st.session_state["start_waze"] = build_waze_link_by_coords(start_geo["lat"], start_geo["lon"])

            if "route_result_df" in st.session_state:
                result_df = st.session_state["route_result_df"]
                st.markdown(f"[פתח את נקודת ההתחלה בוויז]({st.session_state['start_waze']})")
                st.dataframe(result_df.drop(columns=["וויז"]), use_container_width=True, hide_index=True)

                st.markdown("### פתיחה מהירה בוויז")
                for _, row in result_df.iterrows():
                    st.markdown(
                        f"<div class='small-card'><b>{int(row['סדר'])}. {row['שם']}</b><br>"
                        f"{row['כתובת']}<br>"
                        f"מרחק מהנקודה הקודמת: {row['מרחק מהנקודה הקודמת (קמ)']} קמ<br>"
                        f"<a href='{row['וויז']}' target='_blank'>פתח בוויז</a></div>",
                        unsafe_allow_html=True,
                    )

                if "route_map_rows" in st.session_state and not st.session_state["route_map_rows"].empty:
                    st.markdown("### מפה")
                    st.map(st.session_state["route_map_rows"])

                unresolved = st.session_state.get("route_unresolved", [])
                if unresolved:
                    st.warning("הכתובות הבאות לא זוהו ולכן לא נכנסו למסלול:")
                    for item in unresolved:
                        st.write(f"• {item}")

                st.info("כפתור וויז פותח כל תחנה בנפרד. בהמשך אפשר לשלב מנוע מסלולים חיצוני כדי לקבל מסלול כבישים מדויק יותר.")
