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
    col_mapping = {}; mapped = set()
    for col in df.columns:
        c = col.lower().strip(); target = None
        if "awb" in c:                            target = "awb"
        elif "seller" in c:                        target = "seller_name"
        elif "status" in c:                        target = "delivery_status"
        elif "product" in c or "item" in c:        target = "product_name"
        elif "sku" in c:                           target = "sku"
        elif "value" in c or "amount" in c or "price" in c: target = "order_value"
        elif "courier" in c or "partner" in c:     target = "courier"
        if target and target not in mapped:
            col_mapping[col] = target; mapped.add(target)
    df = df.rename(columns=col_mapping)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]
    if "product_name" in df.columns and "sku" not in df.columns:
        df["sku"] = df["product_name"].astype(str)
    elif "sku" in df.columns and "product_name" not in df.columns:
        df["product_name"] = df["sku"].astype(str)
    elif "sku" not in df.columns and "product_name" not in df.columns:
        df["sku"] = "SKU-GEN-01"; df["product_name"] = "General Product"
    defaults = {
        "awb":            lambda d: ["AWB"+str(900000+i) for i in range(len(d))],
        "seller_name":    lambda d: "Apex Retail",
        "delivery_status":lambda d: "Delivered",
        "order_value":    lambda d: 999,
        "courier":        lambda d: "Delhivery",
        "sku_category":   lambda d: "General",
        "state":          lambda d: np.random.choice(["Bihar","Maharashtra","Karnataka","Delhi","Uttar Pradesh"], size=len(d)),
        "pincode":        lambda d: "560001",
        "payment_type":   lambda d: np.random.choice(["COD","Prepaid"], size=len(d), p=[0.6,0.4]),
        "rto_status":     lambda d: d["delivery_status"].apply(lambda x: "Returned" if x=="RTO" else "None"),
        "ndr_status":     lambda d: d["delivery_status"].apply(lambda x: "Raised" if x in ["RTO","NDR"] else "None"),
        "ndr_reason":     lambda d: "",
        "attempt_count":  lambda d: 1,
        "ndr_age_hours":  lambda d: 0,
        "whatsapp_opt_in":lambda d: True,
        "calling_attempted":lambda d: False,
        "vas_active":     lambda d: "ATS Core Routing",
        "shipment_date":  lambda d: [(datetime.now()-timedelta(days=np.random.randint(0,30))).strftime("%Y-%m-%d") for _ in range(len(d))],
    }
    for col, fn in defaults.items():
        if col not in df.columns:
            df[col] = fn(df)
    df["order_value"] = pd.to_numeric(df["order_value"], errors="coerce").fillna(999)
    df["shipment_date"] = pd.to_datetime(df["shipment_date"])
    if "courier" in df.columns:
        df["courier"] = df["courier"].apply(_normalize_courier)
    def clean_status(v):
        v = str(v).lower().strip()
        if "deliver" in v: return "Delivered"
        if "rto" in v or "return" in v: return "RTO"
        if "ndr" in v or "attempt" in v or "fail" in v: return "NDR"
        return "Delivered"
    df["delivery_status"] = df["delivery_status"].apply(clean_status)
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
        "AWB":["AWB910283","AWB910284","AWB910285"],
        "Seller Name":["Apex Retail","Zenith Fashion","Apex Retail"],
        "Shipping Status":["Delivered","RTO","NDR"],
        "Product Name":["Premium Cotton T-Shirt","Smart Watch V2","Wireless Keyboard & Mouse"],
        "SKU ID":["SKU-APP-01","SKU-FSH-10","SKU-ELC-51"],
        "Amount":[1499,2999,1899],
        "Courier Partner":["Delhivery","Bluedart","Xpressbees"],
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

    return df
