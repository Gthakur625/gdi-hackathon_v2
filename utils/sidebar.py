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

# Default live database — auto-loads on every session start
DEFAULT_GSHEET_URL = "https://docs.google.com/spreadsheets/d/13hsbrb6Zyb7IgXCSMk-a4hl_vGCajVt6q66n3cVVDfo/edit?gid=0#gid=0"

DEFAULT_METABASE_URL     = "https://metabase.velocity.in"
DEFAULT_METABASE_API_KEY = "mb_oU89lFlIKpa+35xdrqWsIK241R+Qxiegh56BZjxItrU="
DEFAULT_METABASE_QID     = "4570"

# ── Metabase helpers ──────────────────────────────────────────────────────────

@st.cache_data(ttl=300)
def _fetch_metabase(base_url: str, question_id: int, auth_value: str,
                    auth_type: str = "api_key",
                    start_date: str = None, end_date: str = None):
    import requests, io, warnings
    from datetime import datetime, timedelta
    warnings.filterwarnings("ignore")
    if auth_type == "api_key":
        headers = {"x-api-key": auth_value}
    else:
        headers = {"X-Metabase-Session": auth_value}

    if not start_date:
        start_date = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    if not end_date:
        end_date = datetime.now().strftime("%Y-%m-%d")

    url = f"{base_url.rstrip('/')}/api/card/{question_id}/query/csv"
    body = {"parameters": [
        {"type": "date/single", "target": ["variable", ["template-tag", "shipping_start_date"]], "value": start_date},
        {"type": "date/single", "target": ["variable", ["template-tag", "shipping_end_date"]],   "value": end_date},
    ]}
    resp = requests.post(url, headers=headers, json=body, timeout=120)
    resp.raise_for_status()
    df = pd.read_csv(io.StringIO(resp.text), on_bad_lines="skip", low_memory=False)
    return df


def _metabase_login(base_url: str, username: str, password: str):
    import requests
    url = f"{base_url.rstrip('/')}/api/session"
    resp = requests.post(url, json={"username": username, "password": password}, timeout=15)
    resp.raise_for_status()
    return resp.json().get("id", "")


def _metabase_verify_api_key(base_url: str, api_key: str):
    import requests
    headers = {"x-api-key": api_key}
    url = f"{base_url.rstrip('/')}/api/user/current"
    resp = requests.get(url, headers=headers, timeout=15)
    resp.raise_for_status()
    return resp.json()

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

    # pickup_date — primary cohort date for delivery % analysis
    src = find_col("pickup_date","pickup_Created_at","pickup_created_at","pickup_time","pickupdate","picked_date")
    if src and src != "pickup_date":           rename[src] = "pickup_date"

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

    # Handle Excel serial dates AND regular date strings for shipment_date
    df["shipment_date"] = df["shipment_date"].apply(_excel_to_datetime)
    df["shipment_date"] = pd.to_datetime(df["shipment_date"], errors="coerce")
    df["shipment_date"] = df["shipment_date"].fillna(pd.Timestamp.now())

    # Parse pickup_date (primary cohort date for delivery % analysis)
    if "pickup_date" in df.columns:
        df["pickup_date"] = df["pickup_date"].apply(_excel_to_datetime)
        df["pickup_date"] = pd.to_datetime(df["pickup_date"], errors="coerce")
        # Fill missing pickup_date from shipment_date
        df["pickup_date"] = df["pickup_date"].fillna(df["shipment_date"])
    else:
        df["pickup_date"] = df["shipment_date"]

    def clean_status(v):
        v = str(v).lower().strip()

        # ── Exact matches first (Metabase ShipFast statuses) ──
        if v == "delivered":                                  return "Delivered"
        if v == "lost":                                       return "RTO"
        if v == "cancelled":                                  return "Cancelled"

        # ── RTO family (rto_in_transit, rto_delivered, rto_initiated, rto_out_for_delivery, rto_need_attention) ──
        if v.startswith("rto"):                               return "RTO"

        # ── Return family (return_in_transit, return_delivered, return_pickup_scheduled, return_not_picked, return_qc_failed, return_ndr_raised) ──
        if v.startswith("return"):                            return "RTO"

        # ── NDR family (ndr_raised, reattempt_delivery, need_attention) ──
        if v in ("ndr_raised", "reattempt_delivery", "need_attention"):
            return "NDR"
        if "ndr" in v or "undeliver" in v:                    return "NDR"

        # ── Pending Pickup (ready_for_pickup, not_picked) ──
        if v in ("ready_for_pickup", "not_picked", "pending", "awaiting pickup",
                 "pickup pending", "pending_pickup"):         return "Pending Pickup"
        if "pending" in v and "pickup" in v:                  return "Pending Pickup"

        # ── In Transit / OFD ──
        if v in ("in_transit", "out_for_delivery"):           return "In Transit"
        if "transit" in v or "ofd" in v or "out for" in v:    return "In Transit"

        # ── Delivered (fuzzy — only if not caught above) ──
        if v in ("delivery successful",):                     return "Delivered"
        if v == "delivered":                                   return "Delivered"

        # ── Fallback patterns ──
        if "rto" in v:                                        return "RTO"
        if "attempt" in v or "fail" in v:                     return "NDR"
        if "picked" in v or ("pickup" in v and "pending" not in v): return "In Transit"
        if "booked" in v or "manifest" in v or "shipped" in v: return "In Transit"
        if "cancel" in v:                                     return "Cancelled"
        return "In Transit"
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

    # Auto-set defaults on first session load
    if "gsheet_url" not in st.session_state:
        st.session_state["gsheet_url"]     = DEFAULT_GSHEET_URL
    if "metabase_url" not in st.session_state:
        st.session_state["metabase_url"]       = DEFAULT_METABASE_URL
        st.session_state["metabase_api_key"]   = DEFAULT_METABASE_API_KEY
        st.session_state["metabase_auth_type"] = "api_key"
        st.session_state["metabase_qid"]       = DEFAULT_METABASE_QID
        st.session_state["src_choice_idx"]     = 1   # Metabase tab

    # Remember the last selected source across page navigations
    default_src_idx = st.session_state.get("src_choice_idx", 0)
    SRC_OPTIONS = ["🔗 Google Sheet (Live)", "📊 Metabase (Live)", "📁 Upload CSV / Excel", "📋 Demo Data"]
    src_choice = sb.radio(
        "Data Source",
        SRC_OPTIONS,
        index=st.session_state.get("src_choice_idx", default_src_idx),
        label_visibility="collapsed",
        key="src_radio",
    )
    st.session_state["src_choice_idx"] = SRC_OPTIONS.index(src_choice)

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
            value=st.session_state.get("gsheet_url", DEFAULT_GSHEET_URL),
            placeholder="https://docs.google.com/spreadsheets/d/...",
            label_visibility="collapsed",
        )

        if sb.button("🔗 Connect New Sheet", use_container_width=True, type="primary"):
            if gsheet_url.strip():
                st.session_state["gsheet_url"] = gsheet_url.strip()
                st.cache_data.clear()
            else:
                sb.warning("Paste a Google Sheet URL above first")

        if sb.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()

        # Use session state URL (default or user-entered) — no click needed
        active_url = st.session_state.get("gsheet_url", DEFAULT_GSHEET_URL)
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

    # ── SOURCE 2: Metabase ───────────────────────────────────────────────────
    elif src_choice == "📊 Metabase (Live)":
        sb.markdown(
            "<div style='font-size:0.78rem;color:#9CA3AF;margin-bottom:8px;line-height:1.5;'>"
            "Connect to your Metabase instance for <b style='color:#60A5FA;'>real-time analytics</b>"
            "</div>", unsafe_allow_html=True)

        mb_auth_mode = sb.radio(
            "Auth Method",
            ["🔑 API Key", "👤 Username / Password"],
            index=0,
            label_visibility="collapsed",
            key="mb_auth_mode",
            horizontal=True,
        )

        sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>Metabase URL</div>",
                    unsafe_allow_html=True)
        mb_url = sb.text_input(
            "Metabase URL",
            value=st.session_state.get("metabase_url", DEFAULT_METABASE_URL),
            placeholder="https://metabase.yourcompany.com",
            label_visibility="collapsed",
        )

        if mb_auth_mode == "🔑 API Key":
            sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>API Key</div>",
                        unsafe_allow_html=True)
            mb_api_key = sb.text_input(
                "API Key",
                type="password",
                value=st.session_state.get("metabase_api_key", DEFAULT_METABASE_API_KEY),
                placeholder="mb_xxxxxxxx...",
                label_visibility="collapsed",
            )
        else:
            sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>Email</div>",
                        unsafe_allow_html=True)
            mb_user = sb.text_input(
                "Metabase Email",
                value=st.session_state.get("metabase_user", ""),
                placeholder="user@company.com",
                label_visibility="collapsed",
            )
            sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>Password</div>",
                        unsafe_allow_html=True)
            mb_pass = sb.text_input(
                "Password",
                type="password",
                value="",
                placeholder="Password",
                label_visibility="collapsed",
            )

        sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>Question / Card ID</div>",
                    unsafe_allow_html=True)
        mb_qid = sb.text_input(
            "Question / Card ID",
            value=st.session_state.get("metabase_qid", DEFAULT_METABASE_QID),
            placeholder="e.g. 4570 (saved question ID)",
            label_visibility="collapsed",
        )

        if sb.button("📊 Connect Metabase", use_container_width=True, type="primary"):
            if mb_auth_mode == "🔑 API Key":
                if mb_url and mb_api_key and mb_qid:
                    try:
                        with sb.spinner("Verifying API key..."):
                            _metabase_verify_api_key(mb_url.strip(), mb_api_key.strip())
                        st.session_state["metabase_url"]       = mb_url.strip()
                        st.session_state["metabase_api_key"]   = mb_api_key.strip()
                        st.session_state["metabase_auth_type"] = "api_key"
                        st.session_state["metabase_qid"]       = mb_qid.strip()
                        st.session_state.pop("metabase_token", None)
                        st.cache_data.clear()
                        sb.success("✅ API key verified — connected to Metabase")
                    except Exception as e:
                        sb.error(f"❌ API key invalid: {e}")
                else:
                    sb.warning("Fill in Metabase URL, API Key, and Question ID")
            else:
                if mb_url and mb_user and mb_pass and mb_qid:
                    try:
                        with sb.spinner("Authenticating..."):
                            token = _metabase_login(mb_url.strip(), mb_user.strip(), mb_pass)
                        st.session_state["metabase_url"]       = mb_url.strip()
                        st.session_state["metabase_user"]      = mb_user.strip()
                        st.session_state["metabase_token"]     = token
                        st.session_state["metabase_auth_type"] = "session"
                        st.session_state["metabase_qid"]       = mb_qid.strip()
                        st.session_state.pop("metabase_api_key", None)
                        st.cache_data.clear()
                        sb.success("✅ Connected to Metabase")
                    except Exception as e:
                        sb.error(f"❌ Auth failed: {e}")
                else:
                    sb.warning("Fill in all Metabase fields above")

        # Date range for Metabase query (limits data pulled — much faster)
        sb.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:4px;'>Shipping Date Range</div>",
                    unsafe_allow_html=True)
        from datetime import datetime as _dt, timedelta as _td
        _mb_default_start = (_dt.now() - _td(days=30)).date()
        _mb_default_end   = _dt.now().date()
        mb_dates = sb.date_input(
            "Metabase Date Range",
            value=[_mb_default_start, _mb_default_end],
            label_visibility="collapsed",
            key="mb_date_range",
        )

        if sb.button("🔄 Refresh Data", use_container_width=True, key="mb_refresh"):
            st.cache_data.clear()

        # Determine active auth
        mb_active_url  = st.session_state.get("metabase_url")
        mb_active_qid  = st.session_state.get("metabase_qid")
        mb_auth_type   = st.session_state.get("metabase_auth_type", "api_key")
        mb_auth_value  = (st.session_state.get("metabase_api_key")
                          if mb_auth_type == "api_key"
                          else st.session_state.get("metabase_token"))

        mb_start = str(mb_dates[0]) if len(mb_dates) == 2 else str(_mb_default_start)
        mb_end   = str(mb_dates[1]) if len(mb_dates) == 2 else str(_mb_default_end)

        if mb_auth_value and mb_active_url and mb_active_qid:
            try:
                with sb.spinner(f"Fetching Metabase data ({mb_start} → {mb_end})..."):
                    raw = _fetch_metabase(mb_active_url, int(mb_active_qid),
                                          mb_auth_value, mb_auth_type,
                                          mb_start, mb_end)
                df_all  = _parse_uploaded_mis(raw)
                src_label = "Metabase"
                sb.markdown(
                    f"<div style='background:rgba(96,165,250,0.1);border:1px solid rgba(96,165,250,0.3);"
                    f"border-radius:8px;padding:8px 12px;margin-top:6px;'>"
                    f"<span style='color:#60A5FA;font-weight:700;'>✅ {len(df_all):,} rows from Metabase</span>"
                    f"<div style='color:#6B7280;font-size:0.7rem;margin-top:2px;'>"
                    f"Question #{mb_active_qid} · {mb_start} → {mb_end} · Auto-refreshes every 5 min</div>"
                    f"</div>", unsafe_allow_html=True)
            except Exception as e:
                sb.error(f"❌ Query error: {e}")
                sb.caption("Check your Question ID and permissions")

        if df_all is None:
            sb.caption("Using demo data until Metabase is connected")
            df_all    = _get_base_data()
            src_label = "Demo Data"

    # ── SOURCE 3: File Upload ─────────────────────────────────────────────────
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

    # ── Ensure date columns (strip timezone to avoid comparison errors) ────────
    if "shipment_date" not in df_all.columns:
        df_all["shipment_date"] = pd.Timestamp.now()
    df_all["shipment_date"] = pd.to_datetime(df_all["shipment_date"], errors="coerce", utc=True)
    df_all["shipment_date"] = df_all["shipment_date"].dt.tz_localize(None)
    df_all["shipment_date"] = df_all["shipment_date"].fillna(pd.Timestamp.now())

    if "pickup_date" not in df_all.columns:
        df_all["pickup_date"] = df_all["shipment_date"]
    df_all["pickup_date"] = pd.to_datetime(df_all["pickup_date"], errors="coerce", utc=True)
    df_all["pickup_date"] = df_all["pickup_date"].dt.tz_localize(None)
    df_all["pickup_date"] = df_all["pickup_date"].fillna(df_all["shipment_date"])

    # ── Filters ───────────────────────────────────────────────────────────────
    sb.markdown("<hr style='border:0;height:1px;background:#1F2937;margin:16px 0 12px;'>",
                unsafe_allow_html=True)
    sb.markdown("<div style='color:#9CA3AF;font-size:0.75rem;font-weight:600;"
                "text-transform:uppercase;letter-spacing:0.06em;margin-bottom:10px;'>"
                "⚡ Filters</div>", unsafe_allow_html=True)

    sellers     = sorted(df_all["seller_name"].unique().tolist())
    sel_sellers = sb.multiselect("Seller / Client", sellers, default=sellers)

    # Date filter uses PICKUP DATE as cohort anchor
    min_d = df_all["pickup_date"].min().date()
    max_d = df_all["pickup_date"].max().date()
    sb.markdown("<div style='color:#9CA3AF;font-size:0.72rem;margin-bottom:2px;'>"
                "📦 Pickup Date Range (cohort basis)</div>", unsafe_allow_html=True)
    dates = sb.date_input("Pickup Date Range", [min_d, max_d],
                          min_value=min_d, max_value=max_d,
                          label_visibility="collapsed")

    couriers     = sorted(df_all["courier"].unique().tolist())
    sel_couriers = sb.multiselect("Courier (3PL)", couriers, default=couriers)

    df = df_all.copy()
    if sel_sellers:
        df = df[df["seller_name"].isin(sel_sellers)]
    if len(dates) == 2:
        # Filter by PICKUP DATE — this defines the cohort denominator
        df = df[(df["pickup_date"] >= pd.to_datetime(dates[0])) &
                (df["pickup_date"] <= pd.to_datetime(dates[1]))]
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
