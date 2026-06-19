import re
import streamlit as st
import pandas as pd
import numpy as np
import os
import io
import warnings
from datetime import datetime, timedelta
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from data_generator import generate_shipment_data

# Excel epoch (accounts for Excel's 1900 leap year bug)
_EXCEL_EPOCH = datetime(1899, 12, 30)

def _excel_to_datetime(v):
    """Convert Excel serial number OR date string to datetime."""
    try:
        f = float(str(v).replace(",","").strip())
        if 30000 < f < 60000:          # plausible Excel date (1982 – 2064)
            return _EXCEL_EPOCH + timedelta(days=f)
    except (ValueError, TypeError):
        pass
    return pd.to_datetime(v, errors="coerce", dayfirst=True)

STANDARD_COURIERS = [
    "Delhivery", "Bluedart", "Xpressbees", "Shadowfax",
    "PiknDel", "Blitz", "Ekart",
    "ATS (Amazon Transport Services)", "Elastic Run", "DTDC",
]


# ── courier normaliser ─────────────────────────────────────────────────────────

def _normalize_courier(name):
    if not isinstance(name, str):
        return name
    n = name.strip().lower()
    if "amazon" in n or n.startswith("ats"):   return "ATS (Amazon Transport Services)"
    if "delhivery" in n:                        return "Delhivery"
    if "bluedart" in n or "blue dart" in n:     return "Bluedart"
    if "xpressbees" in n or "xpress bees" in n: return "Xpressbees"
    if "shadowfax" in n:                        return "Shadowfax"
    if "pikndel" in n or "pikngo" in n or "pikn" in n: return "PiknDel"
    if "blitz" in n:                            return "Blitz"
    if "ekart" in n or "e-kart" in n or "e kart" in n: return "Ekart"
    if "elastic" in n:                          return "Elastic Run"
    if "dtdc" in n:                             return "DTDC"
    for s in STANDARD_COURIERS:
        if s.lower() in n or n in s.lower():
            return s
    return name


# ── Google Sheets helpers ──────────────────────────────────────────────────────

def _gsheet_to_csv_url(url_or_id: str):
    """Convert any Google Sheets share URL to a CSV export URL."""
    url_or_id = url_or_id.strip()
    m = re.search(r'/spreadsheets/d/([a-zA-Z0-9_-]+)', url_or_id)
    sheet_id = m.group(1) if m else url_or_id
    gid_m = re.search(r'[#&?]gid=(\d+)', url_or_id)
    gid   = gid_m.group(1) if gid_m else "0"
    return f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"


@st.cache_data(ttl=300)   # refresh every 5 minutes automatically
def _fetch_gsheet(csv_url: str):
    import requests, io, warnings
    warnings.filterwarnings("ignore")
    resp = requests.get(csv_url, verify=False, timeout=30)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text))
    return df


# ── MIS column parser ──────────────────────────────────────────────────────────

def _parse_uploaded_mis(df):
    col_index = {c.lower().strip(): c for c in df.columns}

    def find_col(*candidates):
        for c in candidates:
            if c in df.columns:             return c
            if c.lower() in col_index:      return col_index[c.lower()]
        return None

    rename = {}
    src = find_col("client_name","seller_name","seller","client")
    if src and src != "seller_name":           rename[src] = "seller_name"

    src = find_col("standard_courier_partner","standard_name","carrier_name","courier","courier partner")
    if src and src != "courier":               rename[src] = "courier"

    src = find_col("standard_status","shipment_status","delivery_status","status")
    if src and src != "delivery_status":       rename[src] = "delivery_status"

    src = find_col("product_value","order_value","amount","value","price")
    if src and src != "order_value":           rename[src] = "order_value"

    src = find_col("AWB","awb","tracking_id","awb_number")
    if src and src != "awb":                   rename[src] = "awb"

    src = find_col("shipment_created_at","created_at","shipment_date","date","order_date")
    if src and src != "shipment_date":         rename[src] = "shipment_date"

    src = find_col("delivery_state","state","dest_state")
    if src and src != "state":                 rename[src] = "state"

    src = find_col("delivery_zip","pincode","zip","postal_code","delivery_pincode")
    if src and src != "pincode":               rename[src] = "pincode"

    src = find_col("product_name","item_name","product")
    if src and src != "product_name":          rename[src] = "product_name"

    src = find_col("category","sku_category","product_category")
    if src and src != "sku_category":          rename[src] = "sku_category"

    src = find_col("sku","order_id_display","order_id","shipment_id")
    if src and src != "sku":                   rename[src] = "sku"

    src = find_col("latest_ndr_comment","ndr_reason","first_ndr_comment")
    if src and src != "ndr_reason":            rename[src] = "ndr_reason"

    src = find_col("attempt_count","attempts","ndr_ct")
    if src and src != "attempt_count":         rename[src] = "attempt_count"

    is_cod_col   = find_col("is_cod")
    rto_flag_col = find_col("rto_flag")
    ndr_ct_col   = find_col("ndr_ct")
    ndr_date_col = find_col("first_NDR_date","first_ndr_date","latest_ndr_date")
    payment_src  = find_col("is_cod","payment_type","payment_mode")
    if payment_src and payment_src != "payment_type" and payment_src not in rename:
        rename[payment_src] = "payment_type"

    df = df.rename(columns=rename)
    df = df.loc[:, ~df.columns.duplicated(keep="first")]

    if "payment_type" in df.columns and payment_src == is_cod_col:
        def _cod(v):
            s = str(v).strip().lower()
            if s in ("1","true","yes","cod"):      return "COD"
            if s in ("0","false","no","prepaid"):   return "Prepaid"
            return "COD" if "cod" in s else "Prepaid"
        df["payment_type"] = df["payment_type"].apply(_cod)

    if "rto_status" not in df.columns:
        if rto_flag_col and rto_flag_col not in rename:
            df["rto_status"] = df[rto_flag_col].apply(
                lambda v: "Returned" if str(v).strip() in ("1","True","true","yes") else "None")
        else:
            df["rto_status"] = "None"

    if "ndr_status" not in df.columns:
        if ndr_ct_col and ndr_ct_col not in rename:
            df["ndr_status"] = df[ndr_ct_col].apply(
                lambda v: "Raised" if pd.to_numeric(v, errors="coerce") > 0 else "None")
        elif ndr_date_col and ndr_date_col not in rename:
            df["ndr_status"] = df[ndr_date_col].apply(
                lambda v: "Raised" if pd.notna(v) and str(v) not in ("","nan","None","NaT") else "None")
        else:
            df["ndr_status"] = "None"

    if "product_name" in df.columns and "sku" not in df.columns:
        df["sku"] = df["product_name"].astype(str)
    elif "sku" in df.columns and "product_name" not in df.columns:
        df["product_name"] = df["sku"].astype(str)
    elif "sku" not in df.columns and "product_name" not in df.columns:
        df["sku"] = "SKU-GEN-01"; df["product_name"] = "General Product"

    defaults = {
        "awb":               lambda d: [f"AWB{900000+i}" for i in range(len(d))],
        "seller_name":       lambda d: "Unknown Seller",
        "delivery_status":   lambda d: "Delivered",
        "order_value":       lambda d: 999,
        "courier":           lambda d: "Delhivery",
        "sku_category":      lambda d: "General",
        "state":             lambda d: np.random.choice(
                                 ["Bihar","Maharashtra","Karnataka","Delhi","Uttar Pradesh"], size=len(d)),
        "pincode":           lambda d: "560001",
        "payment_type":      lambda d: np.random.choice(["COD","Prepaid"], size=len(d), p=[0.6,0.4]),
        "rto_status":        lambda d: d["delivery_status"].apply(lambda x: "Returned" if x=="RTO" else "None"),
        "ndr_status":        lambda d: "None",
        "ndr_reason":        lambda d: "",
        "attempt_count":     lambda d: 1,
        "ndr_age_hours":     lambda d: 0,
        "whatsapp_opt_in":   lambda d: True,
        "calling_attempted": lambda d: False,
        "vas_active":        lambda d: "AI Calling",
        "shipment_date":     lambda d: [(datetime.now()-timedelta(days=np.random.randint(0,30))).strftime("%Y-%m-%d")
                                        for _ in range(len(d))],
    }
    for col, fn in defaults.items():
        if col not in df.columns:
            df[col] = fn(df)

    df["order_value"]   = pd.to_numeric(df["order_value"],   errors="coerce").fillna(999)
    df["attempt_count"] = pd.to_numeric(df["attempt_count"], errors="coerce").fillna(1).astype(int)

    # Handle Excel serial dates AND regular date strings
    df["shipment_date"] = df["shipment_date"].apply(_excel_to_datetime)
    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="coerce")
    df["shipment_date"] = df["shipment_date"].fillna(pd.Timestamp.now())

    def clean_status(v):
        v = str(v).lower().strip()
        if "rto" in v:                   return "RTO"   # catch "rto delivered" before "deliver"
        if "deliver" in v:               return "Delivered"
        if "return" in v:                return "RTO"
        if "ndr" in v or "undeliver" in v or "attempt" in v or "fail" in v: return "NDR"
        if "transit" in v or "out_for" in v or "ofd" in v: return "Delivered"
        return "Delivered"
    df["delivery_status"] = df["delivery_status"].apply(clean_status)

    if rto_flag_col is None or rto_flag_col in rename:
        df["rto_status"] = df["delivery_status"].apply(lambda x: "Returned" if x=="RTO" else "None")

    ndr_never_set = (ndr_ct_col is None or ndr_ct_col in rename) and \
                    (ndr_date_col is None or ndr_date_col in rename)
    if ndr_never_set:
        df["ndr_status"] = df["delivery_status"].apply(
            lambda x: "Raised" if x in ["RTO","NDR"] else "None")

    df["courier"] = df["courier"].apply(_normalize_courier)
    return df


# ── base / fallback data ───────────────────────────────────────────────────────

@st.cache_data
def _get_base_data():
    base = os.path.join(os.path.dirname(os.path.dirname(__file__)), "shipments.csv")
    if os.path.exists(base):
        try:
            df = pd.read_csv(base)
            if "shipment_date" in df.columns:
                df["shipment_date"] = pd.to_datetime(df["shipment_date"])
            return df
        except Exception:
            pass
    return generate_shipment_data(1000)


@st.cache_data
def _convert_to_csv(d):
    return d.to_csv(index=False).encode("utf-8")


# ── template for download ──────────────────────────────────────────────────────
_TEMPLATE = pd.DataFrame({
    "AWB":                     ["AWB910283","AWB910284","AWB910285"],
    "client_name":             ["Brand A","Brand B","Brand A"],
    "standard_status":         ["Delivered","RTO","NDR"],
    "product_name":            ["Premium Cotton T-Shirt","Smart Watch V2","Wireless Keyboard"],
    "order_id_display":        ["ORD-001","ORD-002","ORD-003"],
    "product_value":           [1499,2999,1899],
    "standard_courier_partner":["Delhivery","Bluedart","Xpressbees"],
    "is_cod":                  [1,0,1],
    "delivery_state":          ["Maharashtra","Karnataka","Delhi"],
    "delivery_zip":            ["400001","560001","110001"],
    "category":                ["Apparel","Electronics","Apparel"],
    "ndr_ct":                  [0,0,1],
    "attempt_count":           [1,2,1],
    "rto_flag":                [0,1,0],
    "ndr_reason":              ["","","Customer Not Available"],
    "shipment_created_at":     ["2026-06-01","2026-06-05","2026-06-10"],
})


# ══════════════════════════════════════════════════════════════════════════════
# MAIN SIDEBAR RENDERER
# ══════════════════════════════════════════════════════════════════════════════

def render_sidebar_and_get_data():
    sb = st.sidebar

    # ── Header ────────────────────────────────────────────────────────────────
    sb.markdown("""
    <div style="padding:14px 0 6px;">
      <div style="font-size:1.1rem;font-weight:800;color:#FFFFFF;letter-spacing:-0.01em;">
        ⚡ Velocity GDI
      </div>
      <div style="font-size:0.73rem;color:#6B7280;margin-top:2px;">
        Growth & Delivery Intelligence
      </div>
    </div>""", unsafe_allow_html=True)
    sb.markdown("<hr style='border:0;height:1px;background:#1F2937;margin:8px 0 16px;'>",
                unsafe_allow_html=True)

    # ── Data Source Selector ──────────────────────────────────────────────────
    sb.markdown("<div style='color:#9CA3AF;font-size:0.75rem;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.06em;margin-bottom:8px;'>"
                "📊 Data Source</div>", unsafe_allow_html=True)

    src_choice = sb.radio(
        "Data Source",
        ["🔗 Google Sheet (Live)", "📁 Upload CSV / Excel", "📋 Demo Data"],
        label_visibility="collapsed",
    )

    df_all  = None
    src_label = ""

    # ── SOURCE 1: Google Sheet ────────────────────────────────────────────────
    if src_choice == "🔗 Google Sheet (Live)":
        sb.markdown(
            "<div style='font-size:0.78rem;color:#9CA3AF;margin-bottom:8px;line-height:1.5;'>"
            "Paste URL · Share sheet as <b style='color:#34D399;'>Anyone with link → Viewer</b>"
            "</div>", unsafe_allow_html=True)

        gsheet_url = sb.text_input(
            "Google Sheet URL",
            key="gsheet_url_input",
            placeholder="https://docs.google.com/spreadsheets/d/...",
            label_visibility="collapsed",
        )

        if sb.button("🔗 Connect & Load Data", use_container_width=True, type="primary"):
            if gsheet_url.strip():
                st.session_state["gsheet_url"] = gsheet_url.strip()
                st.cache_data.clear()
            else:
                sb.warning("Paste your Google Sheet URL above first")

        if sb.button("🔄 Refresh Now", use_container_width=True):
            st.cache_data.clear()

        active_url = st.session_state.get("gsheet_url", "")
        df_all = None
        if active_url:
            try:
                csv_url = _gsheet_to_csv_url(active_url)
                raw     = _fetch_gsheet(csv_url)
                df_all  = _parse_uploaded_mis(raw)
                src_label = "Google Sheet"
                sb.markdown(
                    f"<div style='background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.3);"
                    f"border-radius:8px;padding:8px 12px;margin-top:6px;'>"
                    f"<span style='color:#34D399;font-weight:700;'>✅ {len(df_all):,} rows loaded</span>"
                    f"<div style='color:#6B7280;font-size:0.7rem;margin-top:2px;'>Auto-refreshes every 5 min</div>"
                    f"</div>", unsafe_allow_html=True)
            except Exception as e:
                sb.error(f"❌ {e}")
                sb.caption("Make sure sheet is shared as Anyone with link → Viewer")
                df_all = None

        if df_all is None:
            sb.caption("Using demo data until sheet is connected")
            df_all    = _get_base_data()
            src_label = "Demo Data"

    # ── SOURCE 2: File Upload ─────────────────────────────────────────────────
    elif src_choice == "📁 Upload CSV / Excel":
        sb.download_button(
            "📥 Download Template CSV",
            _convert_to_csv(_TEMPLATE),
            "velocity_mis_template.csv", "text/csv",
        )
        uploaded = sb.file_uploader("Upload MIS file", type=["csv","xlsx","xls"],
                                    label_visibility="collapsed")
        if uploaded:
            try:
                if uploaded.name.endswith((".xls",".xlsx")):
                    raw = pd.read_excel(uploaded)
                else:
                    raw = pd.read_csv(uploaded)
                df_all = _parse_uploaded_mis(raw)
                src_label = uploaded.name
                sb.success(f"✅ {len(df_all):,} records loaded")
            except Exception as e:
                sb.error(f"Error reading file: {e}")
                df_all = _get_base_data()
                src_label = "Demo Data"
        else:
            df_all = _get_base_data()
            src_label = "Demo Data"

    # ── SOURCE 3: Demo Data ───────────────────────────────────────────────────
    else:
        df_all = _get_base_data()
        src_label = "Demo Data"
        sb.info("Showing demo data. Connect a Google Sheet or upload your CSV to analyse real data.")

    # ── Ensure date column ────────────────────────────────────────────────────
    if "shipment_date" not in df_all.columns:
        df_all["shipment_date"] = pd.Timestamp.now()
    df_all["shipment_date"] = pd.to_datetime(df_all["shipment_date"], errors="coerce")
    df_all["shipment_date"].fillna(pd.Timestamp.now(), inplace=True)

    # ── Filters ───────────────────────────────────────────────────────────────
    sb.markdown("<hr style='border:0;height:1px;background:#1F2937;margin:16px 0 12px;'>",
                unsafe_allow_html=True)
    sb.markdown("<div style='color:#9CA3AF;font-size:0.75rem;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.06em;margin-bottom:10px;'>"
                "⚡ Filters</div>", unsafe_allow_html=True)

    sellers     = sorted(df_all["seller_name"].unique().tolist())
    sel_sellers = sb.multiselect("Seller / Client", sellers, default=sellers)

    min_d = df_all["shipment_date"].min().date()
    max_d = df_all["shipment_date"].max().date()
    dates = sb.date_input("Date Range", [min_d, max_d], min_value=min_d, max_value=max_d)

    couriers     = sorted(df_all["courier"].unique().tolist())
    sel_couriers = sb.multiselect("Courier (3PL)", couriers, default=couriers)

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

    # ── Data source badge ─────────────────────────────────────────────────────
    badge_color = "#34D399" if src_label not in ("Demo Data","") else "#6B7280"
    sb.markdown(f"""
    <div style="margin-top:10px;font-size:0.72rem;color:{badge_color};">
      {'🟢' if src_label not in ('Demo Data','') else '⚫'} {src_label}
      &nbsp;·&nbsp; {len(df):,} rows in view
    </div>""", unsafe_allow_html=True)

    # ── Ask GDI Agent button ──────────────────────────────────────────────────
    sb.markdown("<hr style='border:0;height:1px;background:#1F2937;margin:16px 0 12px;'>",
                unsafe_allow_html=True)
    sb.markdown("""
    <a href="/7_AI_Chat_Assistant" target="_self"
       style="display:block;background:linear-gradient(135deg,#4F46E5,#7C3AED);
              color:#fff !important;padding:11px 16px;border-radius:10px;
              font-weight:700;font-size:0.88rem;text-decoration:none;
              text-align:center;margin-bottom:6px;">
      🤖 Ask GDI Agent
    </a>
    <div style='color:#6B7280;font-size:0.72rem;text-align:center;'>
      Ask about sellers · products · couriers · VAS
    </div>""", unsafe_allow_html=True)

    return df
