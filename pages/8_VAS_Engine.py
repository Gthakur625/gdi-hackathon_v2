"""
VAS Recommendation Engine
Honest numbers only — no assumed revenue.
ROI shown only for NDR recovery (AI Calling + WhatsApp NDR).
"""
import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles      import apply_styles
from utils.sidebar     import render_sidebar_and_get_data
from utils.metrics     import compute_kpis, compute_courier_perf, compute_state_perf
from utils.chat_widget import render_chat_button

apply_styles()

# ── constants (actual vendor rates) ──────────────────────────────────────────
AI_CALL_COST_PER_MIN   = 4.00
AI_CALL_AVG_DURATION   = 2.0
WHATSAPP_COST_PER_MSG  = 0.50
WHATSAPP_MSGS_PER_NDR  = 2
AI_CALLING_RECOVERY    = 0.38
WHATSAPP_RECOVERY      = 0.15
NDR_REFUSE_KEYWORDS    = ["refused","cancel","not responding","unavailable"]

df_full = render_sidebar_and_get_data()

# ── Seller filter ─────────────────────────────────────────────────────────────
all_sellers_vas = sorted(df_full["seller_name"].unique().tolist()) if "seller_name" in df_full.columns else []
if len(all_sellers_vas) > 1:
    sel_vas = st.selectbox(
        "🔍 Select Seller (or view all)",
        ["📊 All Sellers"] + all_sellers_vas,
        key="vas_seller_filter",
        help="Filter VAS recommendations to a specific seller"
    )
    df = df_full[df_full["seller_name"] == sel_vas].copy() if sel_vas != "📊 All Sellers" else df_full.copy()
    if sel_vas != "📊 All Sellers":
        st.markdown(f"<div style='background:rgba(79,70,229,0.1);border:1px solid rgba(79,70,229,0.3);"
                    f"border-radius:8px;padding:8px 14px;margin-bottom:8px;color:#818CF8;font-size:0.85rem;font-weight:600;'>"
                    f"📌 Showing VAS recommendations for: <b>{sel_vas}</b> · {len(df):,} shipments</div>",
                    unsafe_allow_html=True)
else:
    df = df_full.copy()

m  = compute_kpis(df)
cour_df  = compute_courier_perf(df)
state_df = compute_state_perf(df)

# ── pre-compute inputs ────────────────────────────────────────────────────────
total        = len(df)
ndr_df       = df[df["ndr_status"] == "Raised"] if "ndr_status" in df.columns else pd.DataFrame()
ndr_total    = len(ndr_df)
cod_df       = df[df["payment_type"] == "COD"]
cod_ndr_df   = ndr_df[ndr_df["payment_type"] == "COD"] if len(ndr_df) > 0 and "payment_type" in ndr_df.columns else pd.DataFrame()
rto_df       = df[df["delivery_status"] == "RTO"]
delivered_df = df[df["delivery_status"] == "Delivered"]
attempted    = m.get("attempted_total", total)

# NDR reason breakdown
ndr_reasons = {}
if "ndr_reason" in ndr_df.columns and len(ndr_df) > 0:
    ndr_reasons = ndr_df["ndr_reason"].value_counts().to_dict()

# Refusal-type NDRs (WhatsApp less effective here)
refusal_count = sum(v for k, v in ndr_reasons.items()
                    if any(kw in k.lower() for kw in NDR_REFUSE_KEYWORDS))
callable_ndrs  = max(0, ndr_total - refusal_count)   # NDRs where calling helps
whatsapp_ndrs  = len(cod_ndr_df)                       # COD NDRs for WA

# Courier variance
cour_variance = cour_df["delivery_rate"].std() if len(cour_df) > 1 else 0
best_cour     = cour_df.sort_values("delivery_rate", ascending=False).iloc[0] if len(cour_df) > 0 else None
worst_cour    = cour_df.sort_values("delivery_rate").iloc[0]                  if len(cour_df) > 0 else None

# Pincode problem analysis
pin_problem_count = 0
if "pincode" in df.columns and "state" in df.columns:
    pin_g = df.groupby("pincode").agg(
        total    =("delivery_status","count"),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
    ).reset_index()
    pin_g["rr"] = pin_g["rto"] / pin_g["total"].clip(lower=1) * 100
    pin_problem_count = int((pin_g[pin_g["total"] >= 3]["rr"] > 40).sum())

# Attempt count distribution
multi_attempt = 0
if "attempt_count" in df.columns:
    multi_attempt = int((df["attempt_count"] >= 2).sum())

# ── priority score function (0–100, data-driven only) ────────────────────────
def _priority(value, thresholds, weights=(40, 30, 20, 10)):
    """Score increases with severity. thresholds = (critical, high, medium)."""
    c, h, md = thresholds
    if value >= c:  return min(100, int(weights[0] + (value - c) * weights[1] / max(c, 1)))
    if value >= h:  return int(weights[1] + (value - h) / max(h - md, 1) * weights[2])
    if value >= md: return int(weights[2] + (value - md) / max(md, 1) * weights[3])
    return max(5, int(value))

# ── UI helpers ────────────────────────────────────────────────────────────────
def _score_badge(score):
    if score >= 80: bg, tc = "#EF4444", "CRITICAL"
    elif score >= 60: bg, tc = "#F59E0B", "HIGH"
    elif score >= 40: bg, tc = "#818CF8", "MEDIUM"
    else:             bg, tc = "#6B7280", "LOW"
    return (f'<span style="background:{bg}20;color:{bg};border:1px solid {bg}50;'
            f'padding:3px 10px;border-radius:99px;font-size:0.72rem;font-weight:700;">'
            f'{tc} · {score}/100</span>')

def _kv(label, value, color="#D1D5DB", large=False):
    size = "1.1rem" if large else "0.88rem"
    return (f'<div style="padding:8px 0;border-bottom:1px solid #1F2937;">'
            f'<span style="color:#9CA3AF;font-size:0.78rem;">{label}</span>'
            f'<span style="float:right;color:{color};font-weight:700;font-size:{size};">{value}</span>'
            f'</div>')

def _roi_bar(label, filled, total_w, color="#34D399"):
    pct = min(100, filled / max(total_w, 1) * 100)
    return (f'<div style="margin:6px 0;">'
            f'<div style="display:flex;justify-content:space-between;font-size:0.78rem;'
            f'color:#9CA3AF;margin-bottom:3px;"><span>{label}</span>'
            f'<span style="color:{color};font-weight:700;">{pct:.0f}%</span></div>'
            f'<div style="background:#1F2937;border-radius:99px;height:8px;">'
            f'<div style="background:{color};border-radius:99px;height:8px;'
            f'width:{pct:.0f}%;"></div></div></div>')

def _card_header(icon, title, subtitle, score):
    return f"""
    <div style="display:flex;justify-content:space-between;align-items:flex-start;
                margin-bottom:14px;gap:12px;">
      <div>
        <div style="font-size:1.6rem;line-height:1;">{icon}</div>
        <div style="color:#FFFFFF;font-weight:800;font-size:1.05rem;margin:4px 0 2px;">{title}</div>
        <div style="color:#6B7280;font-size:0.78rem;">{subtitle}</div>
      </div>
      <div style="text-align:right;">{_score_badge(score)}</div>
    </div>"""

def _section_divider(label):
    st.markdown(
        f'<div style="color:#9CA3AF;font-size:0.7rem;font-weight:700;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin:6px 0 8px;padding-top:8px;border-top:1px solid #1F2937;">'
        f'{label}</div>', unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PAGE HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-card">
  <h1 class="header-title">⚙️ VAS Recommendation Engine</h1>
  <p class="header-subtitle">Data-driven recommendations · Honest costs · No assumed revenue · NDR recovery ROI only</p>
</div>""", unsafe_allow_html=True)

# ── Live data summary bar ─────────────────────────────────────────────────────
rc = "#34D399" if m["delivery_pct"]>=80 else ("#FBBF24" if m["delivery_pct"]>=65 else "#F87171")
st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-radius:12px;
     padding:12px 20px;margin-bottom:20px;display:flex;gap:24px;flex-wrap:wrap;">
  <div><div style="font-size:1.1rem;font-weight:800;color:{rc};">{m['delivery_pct']:.1f}%</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Delivery</div></div>
  <div><div style="font-size:1.1rem;font-weight:800;color:#F87171;">{m['rto_pct']:.1f}%</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">RTO</div></div>
  <div><div style="font-size:1.1rem;font-weight:800;color:#FBBF24;">{ndr_total:,}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Active NDR</div></div>
  <div><div style="font-size:1.1rem;font-weight:800;color:#C084FC;">{m['cod_pct']:.0f}%</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">COD Share</div></div>
  <div><div style="font-size:1.1rem;font-weight:800;color:#60A5FA;">{total:,}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Shipments</div></div>
  <div style="margin-left:auto;background:rgba(239,68,68,0.08);border:1px solid rgba(239,68,68,0.2);
              border-radius:8px;padding:6px 14px;align-self:center;">
    <div style="color:#FCA5A5;font-size:0.7rem;font-weight:600;text-transform:uppercase;">
      Cost Basis</div>
    <div style="color:#9CA3AF;font-size:0.72rem;margin-top:2px;">
      AI Call ₹{AI_CALL_COST_PER_MIN}/min · WA ₹{WHATSAPP_COST_PER_MSG}/msg
    </div>
  </div>
</div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 1. AI CALLING
# ══════════════════════════════════════════════════════════════════════════════
score_calling = _priority(m["ndr_pct"], thresholds=(25, 15, 8))

recovered_calls    = int(callable_ndrs * AI_CALLING_RECOVERY)
cost_per_call      = AI_CALL_COST_PER_MIN * AI_CALL_AVG_DURATION
total_call_cost    = int(callable_ndrs * cost_per_call)
recovery_efficiency = recovered_calls / max(callable_ndrs, 1) * 100
unreachable_ndrs   = ndr_total - callable_ndrs

col1, col2 = st.columns([1, 1])

with col1:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #818CF8;">
      {_card_header("📞", "AI Calling — NDR Recovery",
                    "IVR outbound calls to customers with active NDRs", score_calling)}

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">PROBLEM</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        <b style="color:#FFFFFF;">{ndr_total:,} active NDRs</b> ({m['ndr_pct']:.1f}% of shipments).
        Of these, <b style="color:#FBBF24;">{refusal_count:,}</b> are refusals/cancellations
        (less callable) and <b style="color:#34D399;">{callable_ndrs:,}</b> are
        reachable cases (unavailable, re-delivery requests, address issues).
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">ROOT CAUSE</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
    """, unsafe_allow_html=True)

    # top NDR reasons
    if ndr_reasons:
        reasons_html = ""
        for reason, cnt in list(ndr_reasons.items())[:4]:
            pct = cnt / max(ndr_total, 1) * 100
            reasons_html += (f'<div style="display:flex;justify-content:space-between;'
                             f'padding:4px 0;border-bottom:1px solid #1F2937;font-size:0.8rem;">'
                             f'<span style="color:#9CA3AF;">{reason[:40]}</span>'
                             f'<span style="color:#FBBF24;font-weight:700;">{cnt} ({pct:.0f}%)</span></div>')
        st.markdown(f'<div style="margin-bottom:12px;">{reasons_html}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div style="color:#6B7280;font-size:0.82rem;">NDR reason data not available.</div>',
                    unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with col2:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #818CF8;">
      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:10px;">ROI — NDR RECOVERY ONLY</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:10px;">Cost Structure</div>
        {_kv("Cost per call (₹4/min × 2 min)", f"₹{cost_per_call:.0f}/shipment")}
        {_kv("Total callable NDRs", f"{callable_ndrs:,}")}
        {_kv("Total calling cost", f"₹{total_call_cost:,}", "#F87171")}
        {_kv("Excluded (refusals)", f"{refusal_count:,} NDRs", "#6B7280")}
      </div>
    """, unsafe_allow_html=True)

    _section_divider("Recovery Estimate")
    st.markdown(f"""
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        {_kv("Recovery rate (AI Calling benchmark)", "38%")}
        {_kv("Estimated recovered shipments", f"{recovered_calls:,}", "#34D399", large=True)}
        {_kv("Unrecoverable (refusals excluded)", f"{unreachable_ndrs:,}", "#6B7280")}
      </div>
    """, unsafe_allow_html=True)

    _roi_bar("Recovery Efficiency (recovered / callable)", recovered_calls, callable_ndrs, "#34D399")
    _roi_bar("NDR Clearance Rate (recovered / total NDR)", recovered_calls, ndr_total, "#818CF8")

    st.markdown(f"""
      <div style="background:rgba(129,140,248,0.07);border-left:3px solid #818CF8;
                  border-radius:0 8px 8px 0;padding:10px 12px;margin-top:12px;
                  font-size:0.8rem;color:#D1D5DB;line-height:1.5;">
        🤖 <b style="color:#818CF8;">GDI Insight:</b>
        At ₹{cost_per_call:.0f}/call, you spend ₹{total_call_cost:,} to attempt recovery on
        {callable_ndrs:,} NDRs. Expected outcome: <b style="color:#34D399;">{recovered_calls:,}
        shipments rescued</b> — {recovery_efficiency:.0f}% recovery efficiency.
        Priority: Call <b>multi-attempt NDRs first</b> ({multi_attempt:,} shipments with ≥2 attempts).
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 2. WHATSAPP NDR
# ══════════════════════════════════════════════════════════════════════════════
score_wa = _priority(
    (m["cod_pct"] * 0.5 + m["ndr_pct"] * 0.5),
    thresholds=(50, 35, 20)
)
wa_messages        = whatsapp_ndrs * WHATSAPP_MSGS_PER_NDR
wa_cost_total      = wa_messages * WHATSAPP_COST_PER_MSG
wa_recovered       = int(whatsapp_ndrs * WHATSAPP_RECOVERY)
wa_efficiency      = wa_recovered / max(whatsapp_ndrs, 1) * 100
cod_rto_count      = len(df[(df["payment_type"]=="COD") & (df["delivery_status"]=="RTO")])
cod_ndr_pct        = len(cod_ndr_df) / max(len(cod_df), 1) * 100

col3, col4 = st.columns([1, 1])

with col3:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #25D366;">
      {_card_header("💬", "WhatsApp AI NDR",
                    "Automated WhatsApp messages to COD customers with failed deliveries",
                    score_wa)}

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">PROBLEM</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        <b style="color:#FFFFFF;">{m['cod_pct']:.0f}% COD share</b> ({m['cod_count']:,} orders).
        Of active NDRs, <b style="color:#FBBF24;">{whatsapp_ndrs:,}</b> are COD-based
        ({cod_ndr_pct:.0f}% of COD orders). COD customers are
        reachable via WhatsApp for reschedule / prepaid switch nudges.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">ROOT CAUSE</div>
      <div style="background:#0B0F19;border-radius:8px;padding:12px;
                  font-size:0.82rem;color:#D1D5DB;line-height:1.6;">
        {_kv("COD NDR count", f"{whatsapp_ndrs:,}")}
        {_kv("COD RTO count", f"{cod_rto_count:,}", "#F87171")}
        {_kv("COD share of all NDRs", f"{cod_ndr_pct:.0f}%", "#C084FC")}
      </div>
    </div>""", unsafe_allow_html=True)

with col4:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #25D366;">
      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:10px;">ROI — NDR RECOVERY ONLY</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;
                    letter-spacing:0.06em;margin-bottom:10px;">Cost Structure</div>
        {_kv("Cost per message", f"₹{WHATSAPP_COST_PER_MSG}")}
        {_kv("Messages per NDR", f"{WHATSAPP_MSGS_PER_NDR} (initial + follow-up)")}
        {_kv("Cost per NDR attempt", f"₹{WHATSAPP_COST_PER_MSG * WHATSAPP_MSGS_PER_NDR:.2f}")}
        {_kv("Total messages", f"{wa_messages:,}")}
        {_kv("Total WA cost", f"₹{wa_cost_total:,.0f}", "#F87171")}
      </div>
    """, unsafe_allow_html=True)

    _section_divider("Recovery Estimate")
    st.markdown(f"""
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        {_kv("Recovery rate (WA NDR benchmark)", f"{WHATSAPP_RECOVERY*100:.0f}%")}
        {_kv("Estimated recovered shipments", f"{wa_recovered:,}", "#34D399", large=True)}
        {_kv("Remaining unrecovered", f"{whatsapp_ndrs - wa_recovered:,}", "#6B7280")}
      </div>
    """, unsafe_allow_html=True)

    _roi_bar("Recovery Efficiency (recovered / COD NDR)", wa_recovered, whatsapp_ndrs, "#25D366")
    _roi_bar("COD NDR Coverage", whatsapp_ndrs, ndr_total, "#818CF8")

    st.markdown(f"""
      <div style="background:rgba(37,211,102,0.06);border-left:3px solid #25D366;
                  border-radius:0 8px 8px 0;padding:10px 12px;margin-top:12px;
                  font-size:0.8rem;color:#D1D5DB;line-height:1.5;">
        🤖 <b style="color:#25D366;">GDI Insight:</b>
        ₹{wa_cost_total:,.0f} total WhatsApp cost to reach {whatsapp_ndrs:,} COD NDRs
        ({wa_messages:,} messages). Estimated <b style="color:#34D399;">{wa_recovered:,}
        shipments recovered</b> at {wa_efficiency:.0f}% efficiency.
        Use alongside AI Calling — WA is cheaper per contact (₹{WHATSAPP_COST_PER_MSG*WHATSAPP_MSGS_PER_NDR:.2f}
        vs ₹{cost_per_call:.0f}), best for low-value COD orders.
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 3. ATS ADDRESS VERIFICATION
# ══════════════════════════════════════════════════════════════════════════════
# Identify address-related NDRs/RTOs from reason column
addr_keywords  = ["address","wrong","incomplete","not found","locality","pin","zip","location"]
addr_ndr_count = 0
if "ndr_reason" in df.columns:
    addr_ndr_count = int(df["ndr_reason"].astype(str).str.lower()
                         .apply(lambda x: any(kw in x for kw in addr_keywords)).sum())
addr_rto_pct   = addr_ndr_count / max(ndr_total, 1) * 100
score_ats      = _priority(m["rto_pct"] + addr_rto_pct * 0.5, thresholds=(30, 20, 10))

col5, col6 = st.columns([1, 1])
with col5:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #60A5FA;">
      {_card_header("📍", "ATS Address Verification",
                    "AI address correction at checkout to prevent address-driven RTOs",
                    score_ats)}

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">PROBLEM</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        Overall RTO at <b style="color:#F87171;">{m['rto_pct']:.1f}%</b>.
        Address-related NDR/RTO reasons detected:
        <b style="color:#FBBF24;">{addr_ndr_count:,} shipments</b>
        ({addr_rto_pct:.0f}% of NDR queue) with wrong/incomplete address as trigger.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">ROOT CAUSE</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:14px;">
        Customers enter incorrect pincodes or incomplete addresses at checkout.
        Courier cannot locate delivery address → first-attempt failure →
        escalates to NDR → RTO if unresolved.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">EXPECTED IMPACT</div>
      <div style="background:#0B0F19;border-radius:8px;padding:12px;">
        {_kv("Address-related NDRs identified", f"{addr_ndr_count:,}")}
        {_kv("ATS verification reduces address RTO by", "4–6% (ATS benchmark)")}
        {_kv("Estimated shipments benefiting", f"{int(m['total']*0.05):,}")}
        {_kv("No revenue assumed", "Prevention metric only", "#6B7280")}
      </div>
    </div>""", unsafe_allow_html=True)

with col6:
    worst_pin_states = []
    if "state" in df.columns and "pincode" in df.columns:
        sp = df.groupby("state").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        sp["rr"] = sp["rto"]/sp["total"].clip(lower=1)*100
        worst_pin_states = sp.nlargest(5,"rr")[["state","total","rr"]].values.tolist()

    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #60A5FA;">
      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:10px;">WHERE ATS HELPS MOST</div>
    """, unsafe_allow_html=True)

    if worst_pin_states:
        rows_html = ""
        for state, tot, rr in worst_pin_states:
            rc2 = "#F87171" if rr>30 else ("#FBBF24" if rr>20 else "#34D399")
            rows_html += (f'<div style="display:flex;justify-content:space-between;padding:7px 0;'
                          f'border-bottom:1px solid #1F2937;font-size:0.82rem;">'
                          f'<span style="color:#FFFFFF;font-weight:600;">{state}</span>'
                          f'<span style="color:#9CA3AF;">{int(tot):,} shpts</span>'
                          f'<span style="color:{rc2};font-weight:700;">{rr:.0f}% RTO</span></div>')
        st.markdown(f'<div style="margin-bottom:14px;">{rows_html}</div>', unsafe_allow_html=True)

    _roi_bar("Address NDR as % of total NDR", addr_ndr_count, ndr_total, "#60A5FA")
    _roi_bar("RTO rate (severity indicator)", int(m["rto_pct"]), 50, "#F87171")

    st.markdown(f"""
      <div style="background:rgba(96,165,250,0.06);border-left:3px solid #60A5FA;
                  border-radius:0 8px 8px 0;padding:10px 12px;margin-top:12px;
                  font-size:0.8rem;color:#D1D5DB;line-height:1.5;">
        🤖 <b style="color:#60A5FA;">GDI Insight:</b>
        ATS Address Verification is an <b>ATS (Amazon Transport Services)</b>
        checkout feature — no per-shipment cost shown as this is a platform
        integration. Priority states for rollout:
        <b>{', '.join(s[0] for s in worst_pin_states[:3]) if worst_pin_states else 'UP, Bihar, Rajasthan'}</b>.
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 4. COURIER OPTIMISATION
# ══════════════════════════════════════════════════════════════════════════════
score_courier = _priority(cour_variance, thresholds=(20, 12, 6))

col7, col8 = st.columns([1, 1])
with col7:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #34D399;">
      {_card_header("🚚", "Courier Optimisation",
                    "Route shipments to best-performing couriers based on delivery data",
                    score_courier)}

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">PROBLEM</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        Delivery rate variance across couriers:
        <b style="color:#34D399;">{best_cour['courier'] if best_cour is not None else 'N/A'}
        {best_cour['delivery_rate']:.0f}%</b> (best) vs
        <b style="color:#F87171;">{worst_cour['courier'] if worst_cour is not None else 'N/A'}
        {worst_cour['delivery_rate']:.0f}%</b> (worst).
        Gap: <b style="color:#FBBF24;">{cour_variance:.1f}% std deviation</b> across partners.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">ROOT CAUSE</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        Volume not allocated by pincode serviceability or courier performance data.
        Weak couriers receiving shipments in areas where they have low delivery rates.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">COURIER PERFORMANCE</div>
    """, unsafe_allow_html=True)

    if len(cour_df) > 0:
        for _, row in cour_df.sort_values("delivery_rate", ascending=False).iterrows():
            dc = "#34D399" if row["delivery_rate"]>=80 else ("#FBBF24" if row["delivery_rate"]>=70 else "#F87171")
            vol_pct = row["total"] / max(total, 1) * 100
            st.markdown(
                f'<div style="margin-bottom:6px;">'
                f'<div style="display:flex;justify-content:space-between;font-size:0.82rem;margin-bottom:3px;">'
                f'<span style="color:#FFFFFF;font-weight:600;">{row["courier"]}</span>'
                f'<span style="color:{dc};font-weight:700;">{row["delivery_rate"]:.0f}% del</span>'
                f'<span style="color:#9CA3AF;">{row["total"]:,} shpts ({vol_pct:.0f}%)</span></div>'
                f'<div style="background:#1F2937;border-radius:99px;height:6px;">'
                f'<div style="background:{dc};border-radius:99px;height:6px;'
                f'width:{min(100,row["delivery_rate"]):.0f}%;"></div></div></div>',
                unsafe_allow_html=True)

    st.markdown("</div>", unsafe_allow_html=True)

with col8:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #34D399;">
      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:10px;">EXPECTED IMPACT</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        {_kv("Current delivery rate", f"{m['delivery_pct']:.1f}%")}
        {_kv("Best courier delivery rate", f"{best_cour['delivery_rate']:.0f}%" if best_cour else "N/A", "#34D399")}
        {_kv("Worst courier delivery rate", f"{worst_cour['delivery_rate']:.0f}%" if worst_cour else "N/A", "#F87171")}
        {_kv("Delivery rate spread", f"{cour_variance:.1f}% std deviation", "#FBBF24")}
        {_kv("Shifting volume to best courier", "Expected +3–5% delivery", "#34D399")}
      </div>
    """, unsafe_allow_html=True)

    _roi_bar(f"Best: {best_cour['courier'] if best_cour else 'N/A'}",
             int(best_cour["delivery_rate"]) if best_cour else 0, 100, "#34D399")
    if worst_cour is not None:
        _roi_bar(f"Worst: {worst_cour['courier']}",
                 int(worst_cour["delivery_rate"]), 100, "#F87171")

    if best_cour is not None and worst_cour is not None:
        shift_shpts = int(worst_cour["total"] * 0.5)
        potential_gain = (best_cour["delivery_rate"] - worst_cour["delivery_rate"]) / 100
        extra_delivered = int(shift_shpts * potential_gain)
        st.markdown(f"""
          <div style="background:rgba(52,211,153,0.06);border-left:3px solid #34D399;
                      border-radius:0 8px 8px 0;padding:10px 12px;margin-top:12px;
                      font-size:0.8rem;color:#D1D5DB;line-height:1.5;">
            🤖 <b style="color:#34D399;">GDI Insight:</b>
            Shifting 50% of <b>{worst_cour['courier']}</b> volume
            ({shift_shpts:,} shipments) to <b>{best_cour['courier']}</b>
            could yield <b style="color:#34D399;">~{extra_delivered:,} additional
            delivered shipments</b> based on the {potential_gain*100:.0f}%
            delivery rate gap. No revenue assumed — delivery count only.
          </div>
        </div>""", unsafe_allow_html=True)
    else:
        st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# 5. PINCODE OPTIMISATION
# ══════════════════════════════════════════════════════════════════════════════
score_pin = _priority(pin_problem_count * 5, thresholds=(60, 40, 20))

col9, col10 = st.columns([1, 1])
with col9:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #C084FC;">
      {_card_header("📍", "Pincode Optimisation",
                    "Restrict COD and reallocate couriers at pincode level based on RTO data",
                    score_pin)}

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">PROBLEM</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        <b style="color:#FBBF24;">{pin_problem_count:,} pincodes</b> have RTO rate > 40%
        (with ≥3 shipments). These are high-risk zones where COD orders
        should be restricted or courier changed.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">ROOT CAUSE</div>
      <div style="font-size:0.85rem;color:#D1D5DB;line-height:1.6;margin-bottom:12px;">
        COD orders accepted uniformly across all pincodes without considering
        historical delivery failure rates. High-RTO pincodes continue to
        receive COD shipments, amplifying return losses.
      </div>

      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:8px;">WORST PINCODES</div>
    """, unsafe_allow_html=True)

    if "pincode" in df.columns:
        pin_g = df.groupby("pincode").agg(
            total =("delivery_status","count"),
            rto   =("delivery_status", lambda x:(x=="RTO").sum()),
            state =("state","first") if "state" in df.columns else ("delivery_status","count"),
            cod   =("payment_type",   lambda x:(x=="COD").sum()) if "payment_type" in df.columns else ("delivery_status","count"),
        ).reset_index()
        pin_g["rr"] = pin_g["rto"]/pin_g["total"].clip(lower=1)*100
        bad_pins = pin_g[pin_g["total"] >= 3].nlargest(8, "rr")

        for _, row in bad_pins.iterrows():
            rc2 = "#F87171" if row["rr"] > 40 else "#FBBF24"
            state_lbl = str(row["state"])[:12] if "state" in df.columns else ""
            st.markdown(
                f'<div style="display:flex;justify-content:space-between;padding:6px 0;'
                f'border-bottom:1px solid #1F2937;font-size:0.8rem;">'
                f'<span style="color:#FFFFFF;font-weight:600;font-family:monospace;">{row["pincode"]}</span>'
                f'<span style="color:#9CA3AF;">{state_lbl}</span>'
                f'<span style="color:#9CA3AF;">{int(row["total"])} shpts</span>'
                f'<span style="color:{rc2};font-weight:700;">{row["rr"]:.0f}% RTO</span></div>',
                unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col10:
    st.markdown(f"""
    <div class="saas-card" style="border-top:3px solid #C084FC;">
      <div style="color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:10px;">EXPECTED IMPACT</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;margin-bottom:14px;">
        {_kv("High-risk pincodes (RTO > 40%)", f"{pin_problem_count:,}", "#F87171")}
        {_kv("Action: Restrict COD at checkout", "Prevent new COD RTOs")}
        {_kv("Action: Switch courier by pincode", "Match best courier to area")}
        {_kv("Action: Prepaid-only for >40% RTO pins", "Eliminate COD exposure")}
        {_kv("No revenue assumed", "RTO prevention metric only", "#6B7280")}
      </div>
    """, unsafe_allow_html=True)

    if "pincode" in df.columns:
        cod_in_bad_pins = 0
        if "payment_type" in df.columns:
            bad_pin_list = pin_g[pin_g["total"] >= 3][pin_g["rr"] > 40]["pincode"].tolist() if len(pin_g)>0 else []
            cod_in_bad_pins = int(df[df["pincode"].isin(bad_pin_list) &
                                     (df["payment_type"] == "COD")].shape[0])

        _roi_bar("Problem pincodes (RTO>40%) as % of total pincodes",
                 pin_problem_count, max(df["pincode"].nunique(), 1), "#C084FC")
        if cod_in_bad_pins > 0:
            _roi_bar("COD orders in high-RTO pincodes (restrict these)",
                     cod_in_bad_pins, max(m["cod_count"], 1), "#F87171")

    st.markdown(f"""
      <div style="background:rgba(192,132,252,0.06);border-left:3px solid #C084FC;
                  border-radius:0 8px 8px 0;padding:10px 12px;margin-top:12px;
                  font-size:0.8rem;color:#D1D5DB;line-height:1.5;">
        🤖 <b style="color:#C084FC;">GDI Insight:</b>
        Pincode blacklisting is the most cost-effective intervention —
        zero per-shipment cost, implemented at your seller dashboard level.
        Restrict COD for <b>{pin_problem_count:,} high-RTO pincodes</b> first.
        Pair with ATS Address Verification to catch bad addresses at entry.
      </div>
    </div>""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════════════════
# PRIORITY SUMMARY TABLE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title' style='margin-top:20px;'>📋 Priority Summary</div>",
            unsafe_allow_html=True)

summary = [
    ("📞 AI Calling",             score_calling, f"{recovered_calls:,} NDRs recovered",
     f"₹{total_call_cost:,} total", "Start immediately — highest NDR count"),
    ("💬 WhatsApp NDR",           score_wa,      f"{wa_recovered:,} NDRs recovered",
     f"₹{wa_cost_total:,.0f} total", "Run parallel to AI Calling for COD NDRs"),
    ("📍 ATS Address Verif.",     score_ats,     f"{int(m['total']*0.05):,} shpts benefit",
     "Platform fee — contact ATS", "Rollout in top-3 RTO states first"),
    ("🚚 Courier Optimisation",   score_courier, f"~{int((best_cour['delivery_rate']-worst_cour['delivery_rate'])/100 * worst_cour['total'] * 0.5):,} extra deliveries" if (best_cour and worst_cour) else "Rebalance volume",
     "No direct cost", "Shift 50% volume from worst courier"),
    ("📍 Pincode Optimisation",   score_pin,     f"{pin_problem_count:,} high-risk pins",
     "No direct cost", "Restrict COD for >40% RTO pincodes"),
]
summary_sorted = sorted(summary, key=lambda x: x[1], reverse=True)

rows_html = ""
for icon_name, score, impact, cost, action in summary_sorted:
    sc2 = "#EF4444" if score>=80 else ("#F59E0B" if score>=60 else ("#818CF8" if score>=40 else "#6B7280"))
    rows_html += (
        f'<tr style="font-size:0.83rem;">'
        f'<td style="padding:10px 12px;border-bottom:1px solid #1F2937;color:#FFFFFF;font-weight:600;">{icon_name}</td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #1F2937;text-align:center;">'
        f'<span style="background:{sc2}20;color:{sc2};border:1px solid {sc2}40;'
        f'padding:2px 10px;border-radius:99px;font-weight:700;">{score}/100</span></td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #1F2937;color:#34D399;">{impact}</td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #1F2937;color:#F87171;">{cost}</td>'
        f'<td style="padding:10px 12px;border-bottom:1px solid #1F2937;color:#9CA3AF;">{action}</td>'
        f'</tr>'
    )

st.markdown(
    f'<div class="saas-card" style="padding:0;overflow:hidden;">'
    f'<table style="width:100%;border-collapse:collapse;">'
    f'<thead><tr style="background:#1F2937;font-size:0.72rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.05em;">'
    f'<th style="padding:10px 12px;text-align:left;">VAS</th>'
    f'<th style="padding:10px 12px;text-align:center;">Priority</th>'
    f'<th style="padding:10px 12px;text-align:left;">Expected Impact</th>'
    f'<th style="padding:10px 12px;text-align:left;">Est. Cost</th>'
    f'<th style="padding:10px 12px;text-align:left;">Recommended Action</th>'
    f'</tr></thead><tbody>{rows_html}</tbody></table></div>',
    unsafe_allow_html=True)

# ── Floating JaGau AI button ─────────────────────────────────────────────────
render_chat_button(df)
