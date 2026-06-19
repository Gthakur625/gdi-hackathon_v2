import streamlit as st
import pandas as pd
import numpy as np
import os
from datetime import datetime, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_generator import generate_shipment_data

STANDARD_COURIERS = [
    "Delhivery", "Bluedart", "Xpressbees", "Shadowfax",
    "PiknDel", "Blitz", "Ekart",
    "ATS (Amazon Transport Services)", "Elastic Run", "DTDC",
]

def _normalize_courier(name):
    if not isinstance(name, str):
        return name
    n = name.strip().lower()
    if "amazon" in n or n.startswith("ats"):
        return "ATS (Amazon Transport Services)"
    if "delhivery" in n:
        return "Delhivery"
    if "bluedart" in n or "blue dart" in n:
        return "Bluedart"
    if "xpressbees" in n or "xpress bees" in n:
        return "Xpressbees"
    if "shadowfax" in n:
        return "Shadowfax"
    if "pikndel" in n or "pikngo" in n or "pikn" in n:
        return "PiknDel"
    if "blitz" in n:
        return "Blitz"
    if "ekart" in n or "e-kart" in n or "e kart" in n:
        return "Ekart"
    if "elastic" in n:
        return "Elastic Run"
    if "dtdc" in n:
        return "DTDC"
    for standard in STANDARD_COURIERS:
        if standard.lower() in n or n in standard.lower():
            return standard
    return name


def _parse_uploaded_mis(df):
    # Build case-insensitive column lookup
    col_index = {c.lower().strip(): c for c in df.columns}

    def find_col(*candidates):
        for c in candidates:
            if c in df.columns:
                return c
            if c.lower() in col_index:
                return col_index[c.lower()]
        return None

    rename = {}

    # seller_name: client_name takes priority over seller/seller_name
    src = find_col("client_name", "seller_name", "seller", "client")
    if src and src != "seller_name":
        rename[src] = "seller_name"

    # courier: standard_courier_partner is most normalised, then carrier_name
    src = find_col("standard_courier_partner", "standard_name", "carrier_name",
                   "courier", "courier partner", "courier_partner")
    if src and src != "courier":
        rename[src] = "courier"

    # delivery_status: standard_status is most normalised
    src = find_col("standard_status", "shipment_status", "delivery_status", "status")
    if src and src != "delivery_status":
        rename[src] = "delivery_status"

    # order_value
    src = find_col("product_value", "order_value", "amount", "value", "price")
    if src and src != "order_value":
        rename[src] = "order_value"

    # awb
    src = find_col("AWB", "awb", "tracking_id", "tracking", "awb_number")
    if src and src != "awb":
        rename[src] = "awb"

    # shipment_date
    src = find_col("shipment_created_at", "created_at", "shipment_date",
                   "date", "order_date", "booking_date")
    if src and src != "shipment_date":
        rename[src] = "shipment_date"

    # state
    src = find_col("delivery_state", "state", "dest_state", "destination_state")
    if src and src != "state":
        rename[src] = "state"

    # pincode
    src = find_col("delivery_zip", "pincode", "zip", "postal_code",
                   "delivery_pincode", "pin", "dest_pincode")
    if src and src != "pincode":
        rename[src] = "pincode"

    # product_name
    src = find_col("product_name", "item_name", "product", "item")
    if src and src != "product_name":
        rename[src] = "product_name"

    # sku_category
    src = find_col("category", "sku_category", "product_category", "cat")
    if src and src != "sku_category":
        rename[src] = "sku_category"

    # sku / order id
    src = find_col("sku", "order_id_display", "order_id", "shipment_id")
    if src and src != "sku":
        rename[src] = "sku"

    # ndr_reason: prefer latest_ndr_comment > ndr_reason > first_ndr_comment
    src = find_col("latest_ndr_comment", "ndr_reason", "first_ndr_comment", "ndr_comment")
    if src and src != "ndr_reason":
        rename[src] = "ndr_reason"

    # attempt_count
    src = find_col("attempt_count", "attempts", "delivery_attempts", "ndr_ct")
    if src and src != "attempt_count":
        rename[src] = "attempt_count"

    # Track special columns BEFORE renaming
    is_cod_col      = find_col("is_cod")
    rto_flag_col    = find_col("rto_flag")
    ndr_ct_col      = find_col("ndr_ct")
    ndr_date_col    = find_col("first_NDR_date", "first_ndr_date", "latest_ndr_date")
    payment_src     = find_col("is_cod", "payment_type", "payment_mode", "payment")
    if payment_src and payment_src != "payment_type" and payment_src not in rename:
        rename[payment_src] = "payment_type"

    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    # Convert is_cod (0/1) → COD/Prepaid
    if "payment_type" in df.columns and payment_src == is_cod_col:
        def _cod(v):
            s = str(v).strip().lower()
            if s in ("1", "true", "yes", "cod"):   return "COD"
            if s in ("0", "false", "no", "prepaid"): return "Prepaid"
            return "COD" if "cod" in s else "Prepaid"
        df["payment_type"] = df["payment_type"].apply(_cod)

    # Build rto_status from rto_flag if not already present
    if "rto_status" not in df.columns:
        if rto_flag_col and rto_flag_col not in rename:
            df["rto_status"] = df[rto_flag_col].apply(
                lambda v: "Returned" if str(v).strip() in ("1","True","true","yes") else "None"
            )
        else:
            df["rto_status"] = "None"

    # Build ndr_status from ndr_ct or NDR date
    if "ndr_status" not in df.columns:
        if ndr_ct_col and ndr_ct_col not in rename:
            df["ndr_status"] = df[ndr_ct_col].apply(
                lambda v: "Raised" if pd.to_numeric(v, errors="coerce") > 0 else "None"
            )
        elif ndr_date_col and ndr_date_col not in rename:
            df["ndr_status"] = df[ndr_date_col].apply(
                lambda v: "Raised" if pd.notna(v) and str(v) not in ("", "nan", "None", "NaT") else "None"
            )
        else:
            df["ndr_status"] = "None"

    # SKU / product_name fallback
    if "product_name" in df.columns and "sku" not in df.columns:
        df["sku"] = df["product_name"].astype(str)
    elif "sku" in df.columns and "product_name" not in df.columns:
        df["product_name"] = df["sku"].astype(str)
    elif "sku" not in df.columns and "product_name" not in df.columns:
        df["sku"] = "SKU-GEN-01"
        df["product_name"] = "General Product"

    defaults = {
        "awb":              lambda d: ["AWB" + str(900000 + i) for i in range(len(d))],
        "seller_name":      lambda d: "Unknown Seller",
        "delivery_status":  lambda d: "Delivered",
        "order_value":      lambda d: 999,
        "courier":          lambda d: "Delhivery",
        "sku_category":     lambda d: "General",
        "state":            lambda d: np.random.choice(
                                ["Bihar","Maharashtra","Karnataka","Delhi","Uttar Pradesh"], size=len(d)),
        "pincode":          lambda d: "560001",
        "payment_type":     lambda d: np.random.choice(["COD","Prepaid"], size=len(d), p=[0.6,0.4]),
        "rto_status":       lambda d: d["delivery_status"].apply(lambda x: "Returned" if x=="RTO" else "None"),
        "ndr_status":       lambda d: "None",
        "ndr_reason":       lambda d: "",
        "attempt_count":    lambda d: 1,
        "ndr_age_hours":    lambda d: 0,
        "whatsapp_opt_in":  lambda d: True,
        "calling_attempted":lambda d: False,
        "vas_active":       lambda d: "AI Calling",
        "shipment_date":    lambda d: [(datetime.now() - timedelta(days=np.random.randint(0, 30))).strftime("%Y-%m-%d")
                                       for _ in range(len(d))],
    }
    for col, fn in defaults.items():
        if col not in df.columns:
            df[col] = fn(df)

    df["order_value"]   = pd.to_numeric(df["order_value"],   errors="coerce").fillna(999)
    df["attempt_count"] = pd.to_numeric(df["attempt_count"], errors="coerce").fillna(1).astype(int)
    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="coerce")
    df["shipment_date"] = df["shipment_date"].fillna(pd.Timestamp.now())

    def clean_status(v):
        v = str(v).lower().strip()
        if "deliver" in v:                          return "Delivered"
        if "rto" in v or "return" in v:             return "RTO"
        if "ndr" in v or "undeliver" in v:          return "NDR"
        if "attempt" in v or "fail" in v:           return "NDR"
        if "transit" in v or "out_for" in v:        return "Delivered"
        return "Delivered"
    df["delivery_status"] = df["delivery_status"].apply(clean_status)

    # Sync rto_status with delivery_status if rto_flag wasn't available
    if rto_flag_col is None or rto_flag_col in rename:
        df["rto_status"] = df["delivery_status"].apply(lambda x: "Returned" if x == "RTO" else "None")

    # Sync ndr_status with delivery_status as final fallback
    ndr_never_set = (ndr_ct_col is None or ndr_ct_col in rename) and \
                    (ndr_date_col is None or ndr_date_col in rename)
    if ndr_never_set:
        df["ndr_status"] = df["delivery_status"].apply(
            lambda x: "Raised" if x in ["RTO", "NDR"] else "None"
        )

    df["courier"] = df["courier"].apply(_normalize_courier)
    return df


@st.cache_data
def _get_base_data():
    base_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shipments.csv")
    if os.path.exists(base_path):
        try:
            df = pd.read_csv(base_path)
            if "shipment_date" in df.columns:
                df["shipment_date"] = pd.to_datetime(df["shipment_date"])
            return df
        except Exception:
            pass
    return generate_shipment_data(1000)


@st.cache_data
def _convert_to_csv(d):
    return d.to_csv(index=False).encode("utf-8")


def render_sidebar_and_get_data():
    """Renders sidebar UI and returns filtered DataFrame."""
    st.sidebar.markdown(
        "<h2 style='color:#FFFFFF;font-size:1.3rem;font-weight:700;margin-bottom:10px;'>📂 MIS Data Upload</h2>",
        unsafe_allow_html=True,
    )

    template_df = pd.DataFrame({
        "AWB":                    ["AWB910283","AWB910284","AWB910285"],
        "client_name":            ["Brand A","Brand B","Brand A"],
        "standard_status":        ["Delivered","RTO","NDR"],
        "product_name":           ["Premium Cotton T-Shirt","Smart Watch V2","Wireless Keyboard"],
        "order_id_display":       ["ORD-001","ORD-002","ORD-003"],
        "product_value":          [1499,2999,1899],
        "standard_courier_partner":["Delhivery","Bluedart","Xpressbees"],
        "is_cod":                 [1,0,1],
        "delivery_state":         ["Maharashtra","Karnataka","Delhi"],
        "delivery_zip":           ["400001","560001","110001"],
        "category":               ["Apparel","Electronics","Apparel"],
        "ndr_ct":                 [0,0,1],
        "attempt_count":          [1,2,1],
        "rto_flag":               [0,1,0],
        "ndr_reason":             ["","","Customer Not Available"],
        "shipment_created_at":    ["2026-06-01","2026-06-05","2026-06-10"],
    })
    st.sidebar.download_button(
        "📥 Download Template MIS CSV", _convert_to_csv(template_df),
        "mis_template.csv", "text/csv",
    )

    uploaded = st.sidebar.file_uploader("Upload MIS Excel / CSV", type=["csv","xlsx","xls"])
    if uploaded:
        try:
            raw = pd.read_excel(uploaded) if uploaded.name.endswith((".xls",".xlsx")) else pd.read_csv(uploaded)
            df_all = _parse_uploaded_mis(raw)
            st.sidebar.success(f"✅ Loaded {len(df_all):,} records")
        except Exception as e:
            st.sidebar.error(f"Error: {e}")
            df_all = _get_base_data()
    else:
        df_all = _get_base_data()

    if "shipment_date" not in df_all.columns:
        df_all["shipment_date"] = pd.Timestamp.now()
    df_all["shipment_date"] = pd.to_datetime(df_all["shipment_date"])

    st.sidebar.markdown(
        "<h2 style='color:#FFFFFF;font-size:1.3rem;font-weight:700;margin-top:20px;margin-bottom:12px;'>⚡ Filters</h2>",
        unsafe_allow_html=True,
    )

    sellers  = sorted(df_all["seller_name"].unique())
    sel_sellers = st.sidebar.multiselect("Seller", sellers, default=sellers)

    min_d = df_all["shipment_date"].min().date()
    max_d = df_all["shipment_date"].max().date()
    dates = st.sidebar.date_input("Date Range", [min_d, max_d], min_value=min_d, max_value=max_d)

    couriers = sorted(df_all["courier"].unique())
    sel_couriers = st.sidebar.multiselect("Courier", couriers, default=couriers)

    df = df_all.copy()
    if sel_sellers:
        df = df[df["seller_name"].isin(sel_sellers)]
    if len(dates) == 2:
        df = df[(df["shipment_date"] >= pd.to_datetime(dates[0])) &
                (df["shipment_date"] <= pd.to_datetime(dates[1]))]
    if sel_couriers:
        df = df[df["courier"].isin(sel_couriers)]

    if df.empty:
        st.error("No shipments match the selected filters.")
        st.stop()

    # ── Ask GDI Agent shortcut ────────────────────────────────────────────────
    st.sidebar.markdown("<hr style='border:0;height:1px;background:#1F2937;margin:20px 0;'>", unsafe_allow_html=True)
    st.sidebar.markdown(
        "<div style='color:#9CA3AF;font-size:0.75rem;text-transform:uppercase;"
        "letter-spacing:0.06em;font-weight:600;margin-bottom:8px;'>🤖 AI Consultant</div>",
        unsafe_allow_html=True,
    )
    st.sidebar.page_link("pages/7_AI_Chat_Assistant.py", label="Ask GDI Agent", icon="🤖")
    st.sidebar.markdown(
        "<div style='color:#6B7280;font-size:0.73rem;margin-top:4px;'>"
        "Ask about sellers, products, couriers & VAS</div>",
        unsafe_allow_html=True,
    )

    return df
