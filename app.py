import math
import re
import sqlite3
from contextlib import closing
from datetime import datetime
from urllib.parse import quote

import pandas as pd
import streamlit as st
from geopy.geocoders import ArcGIS, Nominatim

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

COMMON_CITIES = [
    "",
    "תל אביב-יפו",
    "ירושלים",
    "חיפה",
    "באר שבע",
    "ראשון לציון",
    "פתח תקווה",
    "אשדוד",
    "נתניה",
    "אשקלון",
    "חולון",
    "בני ברק",
    "רמת גן",
    "רחובות",
    "הרצליה",
    "כפר סבא",
    "מודיעין-מכבים-רעות",
    "רעננה",
    "לוד",
    "רמלה",
    "בית שמש",
    "אילת",
    "קריית גת",
    "דימונה",
    "אופקים",
    "מיתר",
    "להבים",
    "עומר",
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
def get_geolocators():
    return {
        "arcgis": ArcGIS(timeout=10),
        "nominatim": Nominatim(user_agent="orders_route_planner_app", timeout=10),
    }


def normalize_address_text(text: str) -> str:
    value = (text or "").strip()
    value = re.sub(r"\s+", " ", value)
    value = value.replace("רח'", "רחוב ")
    value = value.replace("רח ", "רחוב ")
    value = value.replace("מס'", "")
    value = value.replace("דירה", "")
    value = value.replace("ישראל ישראל", "ישראל")
    value = value.replace(",,", ",")
    value = re.sub(r"\s+,", ",", value)
    value = re.sub(r",\s*,", ", ", value)
    return value.strip(" ,")


def build_full_address(street: str, house_number: str, city: str, extra: str = "") -> str:
    street = normalize_address_text(street)
    house_number = normalize_address_text(house_number)
    city = normalize_address_text(city)
    extra = normalize_address_text(extra)

    main = " ".join([part for part in [street, house_number] if part]).strip()
    parts = [part for part in [main, city, extra, "ישראל"] if part]
    return ", ".join(parts)


def build_geocode_candidates(address: str):
    normalized = normalize_address_text(address)
    base = normalized.replace("תא", "תל אביב")
    candidates = [normalized]

    if "ישראל" not in normalized:
        candidates.append(f"{normalized}, ישראל")

    if base != normalized:
        candidates.append(base)
        if "ישראל" not in base:
            candidates.append(f"{base}, ישראל")

    if "," not in normalized and "ישראל" not in normalized:
        candidates.append(f"{normalized}, Israel")

    seen = set()
    result = []
    for item in candidates:
        clean = normalize_address_text(item)
        if clean and clean not in seen:
            seen.add(clean)
            result.append(clean)
    return result


def score_location(candidate_text: str, display_name: str, lat, lon) -> int:
    score = 0
    display = (display_name or "").lower()
    cand = candidate_text.lower()

    if lat is not None and lon is not None:
        score += 20
    if any(ch.isdigit() for ch in cand):
        score += 20
    if "israel" in display or "ישראל" in display:
        score += 15
    if any(word in display for word in ["street", "st", "road", "רחוב", "דרך", "שדרות"]):
        score += 10
    if any(word in cand for word in [",", "רחוב", "שדרות", "דרך"]):
        score += 10
    if len(display) > 20:
        score += 5
    return score


@st.cache_data(show_spinner=False, ttl=60 * 60 * 24)
def geocode_address(address: str):
    geolocators = get_geolocators()
    candidates = build_geocode_candidates(address)
    best = None
    attempts = []

    for candidate in candidates:
        for provider_name in ["arcgis", "nominatim"]:
            try:
                provider = geolocators[provider_name]
                if provider_name == "arcgis":
                    location = provider.geocode(candidate)
                else:
                    location = provider.geocode(candidate, country_codes="il", addressdetails=True, language="he")

                if location:
                    display_name = getattr(location, "address", candidate)
                    lat = getattr(location, "latitude", None)
                    lon = getattr(location, "longitude", None)
                    score = score_location(candidate, display_name, lat, lon)
                    item = {
                        "address": address,
                        "query": candidate,
                        "provider": provider_name,
                        "lat": lat,
                        "lon": lon,
                        "display_name": display_name,
                        "ok": lat is not None and lon is not None,
                        "score": score,
                    }
                    attempts.append(item)
                    if item["ok"] and (best is None or item["score"] > best["score"]):
                        best = item
            except Exception:
                continue

    if best:
        return best

    return {
        "address": address,
        "query": candidates[0] if candidates else address,
        "provider": "",
        "lat": None,
        "lon": None,
        "display_name": "לא נמצאה התאמה מספקת",
        "ok": False,
        "score": 0,
        "attempts": attempts,
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

    remaining = [dict(stop) for stop in stops]
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
        remaining = [s for s in remaining if s["id"] != next_stop["id"]]

    return route


def build_waze_link_by_coords(lat, lon):
    return f"https://www.waze.com/ul?ll={lat},{lon}&navigate=yes"


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
st.caption("אפליקציה פשוטה בעברית עם זיהוי כתובות משופר, רשימת הזמנות ומסלול יומי")

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
    st.caption("כדי לשפר זיהוי כתובת, עדיף להזין עיר, רחוב ומספר בית בנפרד.")

    with st.form("new_order_form", clear_on_submit=True):
        customer_name = st.text_input("שם", placeholder="למשל: משה כהן")
        city = st.selectbox("עיר", COMMON_CITIES, index=0)
        city_free = st.text_input("או עיר אחרת", placeholder="אם העיר לא מופיעה ברשימה")
        col1, col2 = st.columns([3, 1])
        with col1:
            street = st.text_input("רחוב", placeholder="למשל: הרצל")
        with col2:
            house_number = st.text_input("מספר", placeholder="12")
        extra_address = st.text_input("פרטים נוספים", placeholder="כניסה, שכונה, יישוב קטן וכו'")
        selected_items = st.multiselect("פריטים בהזמנה", ITEMS, placeholder="בחר פריטים")
        is_paid = st.checkbox("שולם")
        submitted = st.form_submit_button("שמור הזמנה", use_container_width=True)

        final_city = city_free.strip() if city_free.strip() else city
        full_address = build_full_address(street, house_number, final_city, extra_address)

        if submitted:
            if not customer_name.strip():
                st.error("צריך להזין שם.")
            elif not street.strip():
                st.error("צריך להזין רחוב.")
            elif not house_number.strip():
                st.error("צריך להזין מספר בית.")
            elif not final_city.strip():
                st.error("צריך לבחור או להזין עיר.")
            elif not selected_items:
                st.error("צריך לבחור לפחות פריט אחד.")
            else:
                address_check = geocode_address(full_address)
                add_order(customer_name.strip(), full_address, selected_items, is_paid)
                if address_check["ok"]:
                    st.success(f"ההזמנה נשמרה. הכתובת זוהתה דרך {address_check['provider']}.")
                else:
                    st.warning("ההזמנה נשמרה, אבל הכתובת לא זוהתה היטב. כדאי לבדוק את הניסוח.")
                st.rerun()

    st.markdown("### בדיקת כתובת")
    verify_city = st.selectbox("עיר לבדיקה", COMMON_CITIES, index=0, key="verify_city")
    verify_city_free = st.text_input("או עיר אחרת לבדיקה", key="verify_city_free")
    verify_street = st.text_input("רחוב לבדיקה", key="verify_street", placeholder="למשל: בן גוריון")
    verify_house = st.text_input("מספר בית לבדיקה", key="verify_house", placeholder="10")
    verify_extra = st.text_input("פרטים נוספים לבדיקה", key="verify_extra", placeholder="שכונה / יישוב קטן / כניסה")

    if st.button("בדוק כתובת", use_container_width=True):
        final_verify_city = verify_city_free.strip() if verify_city_free.strip() else verify_city
        if verify_street.strip() and verify_house.strip() and final_verify_city.strip():
            verify_address = build_full_address(verify_street, verify_house, final_verify_city, verify_extra)
            result = geocode_address(verify_address)
            if result["ok"]:
                st.success(f"נמצאה התאמה דרך {result['provider']}.")
                st.write(result["display_name"])
                st.markdown(f"[פתח בוויז]({build_waze_link_by_coords(result['lat'], result['lon'])})")
            else:
                st.warning("לא נמצאה התאמה מספקת. נסה לקצר או לדייק את שם העיר והרחוב.")
        else:
            st.warning("צריך להזין עיר, רחוב ומספר בית.")

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
    st.caption("הסדר כאן הוא המלצה מקורבת. זיהוי הכתובות שופר, אבל עדיין זו לא אופטימיזציית כבישים מלאה כמו שירות ניווט ייעודי.")

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
            st.markdown("### נקודת התחלה")
            start_city = st.selectbox("עיר התחלה", COMMON_CITIES, index=0, key="start_city")
            start_city_free = st.text_input("או עיר התחלה אחרת", key="start_city_free")
            start_col1, start_col2 = st.columns([3, 1])
            with start_col1:
                start_street = st.text_input("רחוב התחלה", key="start_street")
            with start_col2:
                start_house = st.text_input("מספר התחלה", key="start_house")
            start_extra = st.text_input("פרטים נוספים לנקודת התחלה", key="start_extra")

            if st.button("חשב סדר נסיעה מומלץ", use_container_width=True):
                final_start_city = start_city_free.strip() if start_city_free.strip() else start_city
                if not start_street.strip() or not start_house.strip() or not final_start_city.strip():
                    st.warning("צריך להזין לעמדת ההתחלה עיר, רחוב ומספר.")
                else:
                    start_address = build_full_address(start_street, start_house, final_start_city, start_extra)
                    start_geo = geocode_address(start_address)
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
                                        "provider": geo["provider"],
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
                                result_rows.append(
                                    {
                                        "סדר": i,
                                        "שם": stop["name"],
                                        "כתובת": stop["address"],
                                        "התאמה": stop["matched_address"],
                                        "מקור זיהוי": stop["provider"],
                                        "הזמנה": stop["items"],
                                        "מרחק מהנקודה הקודמת (קמ)": stop["distance_from_previous_km"],
                                        "שולם": stop["paid"],
                                        "וויז": build_waze_link_by_coords(stop["lat"], stop["lon"]),
                                    }
                                )
                                map_rows.append({"lat": stop["lat"], "lon": stop["lon"]})

                            st.session_state["route_result_df"] = pd.DataFrame(result_rows)
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
                        f"זוהה דרך: {row['מקור זיהוי']}<br>"
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

                st.info("עכשיו האפליקציה מנסה לזהות כתובות בכמה דרכים ובשני ספקי מיפוי. אם תרצה, השלב הבא יהיה מעבר ל-API ייעודי עם מפתח כדי להגיע לרמת דיוק גבוהה יותר בישראל.")
