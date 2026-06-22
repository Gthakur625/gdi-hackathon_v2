"""
JaGau AI — GDI Dashboard
From Insight to Action.
"""
import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os, random, string
from datetime import datetime, timedelta
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles          import apply_styles
from utils.sidebar         import render_sidebar_and_get_data
from utils.chat_widget     import render_chat_button
from utils.recommendations import (detect_courier_concentration,
                                   build_velocity_recommendations, NDD_COURIERS)
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                           compute_courier_perf, compute_state_perf, get_recommendations,
                           get_anomalies)

apply_styles()

st.markdown("""
<style>
/* ── JaGau Briefing card ── */
.jaggu-brief { background:linear-gradient(135deg,#0F0A1E 0%,#111827 100%);
    border:1px solid rgba(79,70,229,0.4);border-radius:16px;padding:24px 28px;margin-bottom:20px; }
.jaggu-section-lbl { font-size:0.68rem;font-weight:700;text-transform:uppercase;
    letter-spacing:0.1em;margin-bottom:8px; }
.risk-item  { padding:8px 12px;border-radius:8px;margin-bottom:6px;
    background:rgba(248,113,113,0.08);border-left:3px solid #F87171;
    font-size:0.85rem;color:#D1D5DB;line-height:1.4; }
.opp-item   { padding:8px 12px;border-radius:8px;margin-bottom:6px;
    background:rgba(52,211,153,0.08);border-left:3px solid #34D399;
    font-size:0.85rem;color:#D1D5DB;line-height:1.4; }
.action-item{ padding:10px 14px;border-radius:8px;margin-bottom:8px;
    background:#111827;border:1px solid #1F2937;
    font-size:0.85rem;color:#D1D5DB;line-height:1.5; }
.impact-pill{ display:inline-block;padding:4px 12px;border-radius:99px;
    font-size:0.78rem;font-weight:700;margin:3px; }
.exec-done  { background:rgba(52,211,153,0.1);border:1px solid rgba(52,211,153,0.3);
    border-radius:8px;padding:10px 14px;color:#34D399;font-size:0.82rem;font-weight:600; }
</style>""", unsafe_allow_html=True)

# ── Load data ─────────────────────────────────────────────────────────────────
df_full = render_sidebar_and_get_data()
all_sellers = sorted(df_full["seller_name"].unique().tolist()) if "seller_name" in df_full.columns else []
is_admin    = len(all_sellers) > 1


# ══════════════════════════════════════════════════════════════════════════════
# SELLER + DATE SELECTION  (the only two inputs JaGau needs)
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div style="margin-bottom:16px;">
  <div style="color:#818CF8;font-size:0.72rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.08em;margin-bottom:6px;">🤖 JaGau AI</div>
  <div style="color:#FFFFFF;font-size:1.6rem;font-weight:800;line-height:1.2;">
    From Insight to Action.</div>
  <div style="color:#6B7280;font-size:0.88rem;margin-top:4px;">
    Select a seller — JaGau instantly generates their health briefing, risks, opportunities and recommended actions.
  </div>
</div>""", unsafe_allow_html=True)

col_sel, col_info = st.columns([3, 2])
with col_sel:
    if is_admin:
        selected_seller = st.selectbox(
            "Select Seller / Client",
            ["📊 All Sellers"] + all_sellers,
            key="dash_seller",
            label_visibility="collapsed",
        )
    else:
        selected_seller = all_sellers[0] if all_sellers else "All"
        st.markdown(f"<div style='color:#818CF8;font-size:0.9rem;font-weight:600;padding:8px 0;'>"
                    f"📌 {selected_seller}</div>", unsafe_allow_html=True)

with col_info:
    # Show pickup date range
    _dc = "pickup_date" if "pickup_date" in df_full.columns else "shipment_date"
    _mn = pd.to_datetime(df_full[_dc]).min()
    _mx = pd.to_datetime(df_full[_dc]).max()
    _rng = f"{_mn.strftime('%d %b')} – {_mx.strftime('%d %b %Y')}" if pd.notna(_mn) else "All dates"
    st.markdown(
        f'<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;'
        f'padding:10px 14px;font-size:0.82rem;color:#9CA3AF;">'
        f'📦 Pickup cohort: <b style="color:#D1D5DB;">{_rng}</b><br>'
        f'<span style="font-size:0.75rem;">Delivery% = Delivered ÷ Attempted in this window</span>'
        f'</div>', unsafe_allow_html=True)

# Apply seller filter
if is_admin and selected_seller != "📊 All Sellers":
    df = df_full[df_full["seller_name"] == selected_seller].copy()
else:
    df = df_full.copy()

# ── Compute metrics ───────────────────────────────────────────────────────────
m       = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs      = compute_health_score(m)
cour_df = compute_courier_perf(df)
state_df= compute_state_perf(df)
recs    = get_recommendations(m)
conc    = detect_courier_concentration(df)
m["courier_concentration"] = conc.get("is_concentrated", False)
vel     = build_velocity_recommendations(df, m, cour_df, conc)

_has_cour  = len(cour_df) > 0
_has_state = len(state_df) > 0
best_c  = cour_df.sort_values("delivery_rate", ascending=False).iloc[0] if _has_cour  else None
worst_c = cour_df.sort_values("delivery_rate").iloc[0]                  if _has_cour  else None
worst_st= state_df.sort_values("rto_rate", ascending=False).iloc[0]     if _has_state else None
def _cv(row, key, default="N/A"): return row[key] if row is not None else default
best_c_name = _cv(best_c, "courier"); best_c_dr  = _cv(best_c,  "delivery_rate", 0)
worst_c_name= _cv(worst_c,"courier"); worst_c_dr = _cv(worst_c, "delivery_rate", 0)
worst_st_name=_cv(worst_st,"state");  worst_st_rr= _cv(worst_st,"rto_rate", 0)

cod_df   = df[df["payment_type"]=="COD"]
prep_df  = df[df["payment_type"]=="Prepaid"]
cod_rto  = len(cod_df[cod_df["delivery_status"]=="RTO"]) / max(len(cod_df), 1) * 100
prep_rto = len(prep_df[prep_df["delivery_status"]=="RTO"])/ max(len(prep_df),1) * 100
att      = m.get("attempted_total", m["total"])
pending  = m.get("pending_count", 0)

# ── Date range string ─────────────────────────────────────────────────────────
_date_col = "pickup_date" if "pickup_date" in df.columns else "shipment_date"
_min_d = pd.to_datetime(df[_date_col]).min()
_max_d = pd.to_datetime(df[_date_col]).max()
_period = (f"{_min_d.strftime('%d %b')} – {_max_d.strftime('%d %b %Y')}"
           if pd.notna(_min_d) else "All dates")

# ══════════════════════════════════════════════════════════════════════════════
# BUILD JaGau BRIEFING  — Risks / Opportunities / Actions
# ══════════════════════════════════════════════════════════════════════════════

# ── Pre-compute pincode intelligence (used in risks + courier section) ────────
_pin_df = pd.DataFrame()
if "pincode" in df.columns:
    _pagg = df.groupby("pincode").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        ndr_ct   =("ndr_status",      lambda x:(x=="Raised").sum()) if "ndr_status" in df.columns
                   else ("delivery_status","count"),
        cod      =("payment_type",    lambda x:(x=="COD").sum()) if "payment_type" in df.columns
                   else ("delivery_status","count"),
        state    =("state","first")   if "state" in df.columns else ("delivery_status","count"),
    ).reset_index()
    _pagg["dr"]    = _pagg["delivered"] / _pagg["total"].clip(lower=1) * 100
    _pagg["rr"]    = _pagg["rto"]       / _pagg["total"].clip(lower=1) * 100
    _pagg["ndr_r"] = _pagg["ndr_ct"]    / _pagg["total"].clip(lower=1) * 100
    _pagg["cod_r"] = _pagg["cod"]       / _pagg["total"].clip(lower=1) * 100
    _pagg["pincode_str"] = _pagg["pincode"].astype(str)
    _pin_df = _pagg

# High NDR pincodes (actual pincode list)
_high_ndr_pins = _pin_df[(_pin_df["total"] >= 2) & (_pin_df["ndr_r"] > 25)].nlargest(5, "ndr_r") \
                 if len(_pin_df) > 0 else pd.DataFrame()
_high_rto_pins = _pin_df[(_pin_df["total"] >= 2) & (_pin_df["rr"] > 40)].nlargest(5, "rr") \
                 if len(_pin_df) > 0 else pd.DataFrame()
_high_ndr_pin_count = int((_pin_df["ndr_r"] > 25).sum()) if len(_pin_df) > 0 else 0
_high_ndr_pin_list  = ", ".join(_high_ndr_pins["pincode_str"].tolist()[:4]) if len(_high_ndr_pins) > 0 else ""

# ── Risks (max 4, ranked by severity) ────────────────────────────────────────
risks = []
if m["ndr_pct"] > 20:
    ndr_detail = f"{m['ndr_count']:,} active NDRs ({m['ndr_pct']:.0f}% of shipments)"
    if _high_ndr_pin_count > 0:
        ndr_detail += f" · {_high_ndr_pin_count} pincodes with NDR > 25%"
        if _high_ndr_pin_list:
            ndr_detail += f" (top: {_high_ndr_pin_list})"
    risks.append({"icon":"🚨","label":"High NDR", "detail": ndr_detail})
if m["rto_pct"] > 20:
    risks.append({
        "icon":"⚠️","label":"High RTO",
        "detail": f"{m['rto_count']:,} RTOs ({m['rto_pct']:.0f}%) · "
                  + (f"{worst_st_name} worst state at {worst_st_rr:.0f}%" if _has_state else "multiple states"),
    })
if m["cod_pct"] > 70:
    risks.append({
        "icon":"⚠️","label":"COD Concentration Risk",
        "detail": f"{m['cod_pct']:.0f}% COD share · COD-RTO at {cod_rto:.0f}% vs Prepaid {prep_rto:.0f}%",
    })
if conc.get("is_concentrated"):
    risks.append({
        "icon":"⚠️","label":"Courier Concentration Risk",
        "detail": f"{conc['dominant_pct']:.0f}% volume on {conc['dominant_courier']} alone · single point of failure",
    })
if _has_cour and worst_c_dr < (m["delivery_pct"] - 10):
    risks.append({
        "icon":"⚠️","label":f"Courier Underperformance — {worst_c_name}",
        "detail": f"Delivering only {worst_c_dr:.0f}% vs fleet avg {m['delivery_pct']:.0f}% · {int(_cv(worst_c,'total',0)):,} shipments affected",
    })
if not risks:
    risks.append({"icon":"✅","label":"No Critical Risks","detail":"Operations within healthy thresholds."})

# ── Opportunities (max 4) ─────────────────────────────────────────────────────
opps = []
if m["ndr_count"] > 10:
    rec = int(m["ndr_count"]*0.38)
    opps.append({"icon":"📞","label":"AI Calling — NDR Recovery",
                 "detail":f"~{rec:,} shipments recoverable at 38% rate · cost ₹{int(m['ndr_count']*8):,}"})
if m["cod_pct"] > 50 and m["ndr_pct"] > 10:
    sv = int(m["rto_count"]*0.08)
    opps.append({"icon":"💬","label":"WhatsApp AI NDR",
                 "detail":f"~{sv:,} COD RTOs preventable · cost ₹{int(m['ndr_count']*1):,}"})
if _has_cour and (best_c_dr - worst_c_dr) > 8:
    extra = int(_cv(worst_c,"total",0) * 0.4 * (best_c_dr - worst_c_dr) / 100)
    opps.append({"icon":"🚚","label":"Courier Optimization",
                 "detail":f"Shift 40% of {worst_c_name} volume to {best_c_name} → ~{extra:,} extra deliveries"})
if m["rto_pct"] > 15:
    sv = int(m["rto_count"]*0.12)
    opps.append({"icon":"✅","label":"Order Confirmation Via AI",
                 "detail":f"~{sv:,} fake/impulsive COD orders blocked pre-dispatch"})
if not opps:
    opps.append({"icon":"🚀","label":"NDD Activation",
                 "detail":"Activate ElasticRun / PiknDel / Blitz for Zone A/B next-day delivery"})

# ── Actions (data-backed, specific) ──────────────────────────────────────────
actions = []
for i, v in enumerate(vel[:5], 1):
    actions.append({"rank": i, "name": v["name"], "detail": v["impact"], "metric": v["metric"],
                    "key": f"exec_{i}_{selected_seller[:8].replace(' ','_')}"})

# ── Expected impact totals ────────────────────────────────────────────────────
total_recoverable = (int(m["ndr_count"]*0.38) + int(m["rto_count"]*0.08)
                     + int(m["rto_count"]*0.12))
delivery_gain  = round(min(12, m["ndr_pct"]*0.38*0.3 + (best_c_dr-m["delivery_pct"])*0.2), 1) if _has_cour else 3.5
rto_reduction  = round(min(10, m["rto_pct"]*0.15), 1)

# ══════════════════════════════════════════════════════════════════════════════
# RENDER JaGau BRIEFING CARD
# ══════════════════════════════════════════════════════════════════════════════
scope_label = f"— {selected_seller}" if (is_admin and selected_seller != "📊 All Sellers") else ""

# Health score colour + label
if hs >= 80:   hs_col="#34D399"; hs_lbl="Healthy";         hs_icon="🟢"
elif hs >= 65: hs_col="#FBBF24"; hs_lbl="Needs Attention";  hs_icon="🟡"
else:          hs_col="#F87171"; hs_lbl="At Risk";           hs_icon="🔴"

# ── Pre-build all HTML strings OUTSIDE the f-string to avoid rendering bugs ──
_period_str   = _period
_shpt_str     = f"{m['total']:,} shipments · {m['delivered']:,} delivered of {att:,} attempted"
_pending_str  = f" · {pending:,} Pending Pickup excluded" if pending > 0 else ""
_scope_str    = scope_label

_risks_html = "".join(
    f'<div class="risk-item"><b style="color:#F87171;">{r["icon"]} {r["label"]}</b>'
    f'<br><span style="font-size:0.82rem;">{r["detail"]}</span></div>'
    for r in risks[:3]
)
_opps_html = "".join(
    f'<div class="opp-item"><b style="color:#34D399;">{o["icon"]} {o["label"]}</b>'
    f'<br><span style="font-size:0.82rem;">{o["detail"]}</span></div>'
    for o in opps[:3]
)
_actions_html = "".join(
    f'<div class="action-item">'
    f'<b style="color:#FFFFFF;">#{a["rank"]}. {a["name"]}</b>'
    f'<br>{a["detail"]}'
    f'<br><span style="color:#818CF8;font-size:0.78rem;">→ {a["metric"]}</span></div>'
    for a in actions[:4]
)
_impact_html = (
    f'<span class="impact-pill" style="background:rgba(52,211,153,0.12);color:#34D399;">'
    f'📈 +{delivery_gain:.1f}% Delivery Rate</span>'
    f'<span class="impact-pill" style="background:rgba(248,113,113,0.12);color:#F87171;">'
    f'📉 -{rto_reduction:.1f}% RTO Rate</span>'
    f'<span class="impact-pill" style="background:rgba(129,140,248,0.12);color:#818CF8;">'
    f'📞 ~{total_recoverable:,} shipments recoverable</span>'
)

st.markdown(
    f'<div class="jaggu-brief">'
    f'<div style="display:flex;justify-content:space-between;align-items:flex-start;'
    f'flex-wrap:wrap;gap:12px;margin-bottom:20px;">'
    f'<div>'
    f'<div style="color:#818CF8;font-size:0.7rem;font-weight:700;text-transform:uppercase;'
    f'letter-spacing:0.08em;margin-bottom:4px;">🤖 JaGau AI Briefing {_scope_str}</div>'
    f'<div style="color:#6B7280;font-size:0.72rem;">'
    f'Period: <b style="color:#9CA3AF;">{_period_str}</b> · {_shpt_str}{_pending_str}'
    f'</div></div>'
    f'<div style="background:#0B0F19;border-radius:12px;padding:10px 20px;text-align:center;min-width:140px;">'
    f'<div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;font-weight:600;">Seller Health</div>'
    f'<div style="font-size:2.4rem;font-weight:800;color:{hs_col};line-height:1.1;">{hs:.0f}</div>'
    f'<div style="font-size:0.72rem;color:{hs_col};font-weight:700;">{hs_icon} {hs_lbl}</div>'
    f'</div></div>'
    f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">'
    f'<div><div class="jaggu-section-lbl" style="color:#F87171;">⚡ TOP RISKS</div>{_risks_html}</div>'
    f'<div><div class="jaggu-section-lbl" style="color:#34D399;">💰 TOP OPPORTUNITIES</div>{_opps_html}</div>'
    f'</div>'
    f'<div style="border-top:1px solid #1F2937;padding-top:16px;margin-bottom:16px;">'
    f'<div class="jaggu-section-lbl" style="color:#818CF8;">✅ RECOMMENDED ACTIONS</div>'
    f'{_actions_html}</div>'
    f'<div style="background:#0B0F19;border-radius:10px;padding:14px 18px;margin-bottom:4px;">'
    f'<div style="color:#6B7280;font-size:0.7rem;text-transform:uppercase;font-weight:600;margin-bottom:8px;">'
    f'Expected Impact (if all actions activated)</div>'
    f'<div style="display:flex;gap:10px;flex-wrap:wrap;">{_impact_html}</div>'
    f'</div></div>',
    unsafe_allow_html=True
)

# ── Approve & Execute buttons ─────────────────────────────────────────────────
st.markdown("<div style='color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;"
            "letter-spacing:0.08em;margin-bottom:10px;'>⚡ AGENTIC EXECUTION — APPROVE ACTIONS</div>",
            unsafe_allow_html=True)

exec_cols = st.columns(min(len(actions), 4))
for i, action in enumerate(actions[:4]):
    with exec_cols[i]:
        sk = f"approved_{action['key']}"
        if st.session_state.get(sk):
            st.markdown(f"""<div class="exec-done">
              ✅ <b>{action['name']}</b><br>
              <span style="font-size:0.75rem;color:#6B7280;">Approved · Ticket #{st.session_state[sk]}</span>
            </div>""", unsafe_allow_html=True)
        else:
            if st.button(f"▶ Approve #{action['rank']}: {action['name'][:20]}",
                         key=f"btn_approve_{i}_{selected_seller[:8]}",
                         use_container_width=True, type="primary"):
                ticket = "GDI-" + "".join(random.choices(string.digits, k=5))
                st.session_state[sk] = ticket
                st.rerun()

# Create all tasks button
st.markdown("<div style='height:8px;'></div>", unsafe_allow_html=True)
if st.button("📋 Create All Action Tasks", key="create_all_tasks", use_container_width=False):
    task_id = "TASK-" + "".join(random.choices(string.digits, k=5))
    st.markdown(f"""<div style="background:rgba(129,140,248,0.08);border:1px solid rgba(129,140,248,0.3);
                    border-radius:8px;padding:10px 14px;margin-top:8px;font-size:0.82rem;color:#818CF8;">
      ✅ <b>{len(actions[:4])} tasks created</b> · Ref: {task_id}
      · Due: {(datetime.now()+timedelta(hours=4)).strftime("%d %b, %I:%M %p")}</div>""",
                unsafe_allow_html=True)

st.markdown("---")

# ══════════════════════════════════════════════════════════════════════════════
# CRITICAL ISSUES (from Agentic Ops — kept compact)
# ══════════════════════════════════════════════════════════════════════════════
from utils.agent_ops import detect_critical_issues
issues = detect_critical_issues(df, m, cour_df, state_df)
if issues:
    with st.expander(f"🚨 {len(issues)} Critical Issues Detected — Click to Escalate", expanded=False):
        from utils.agent_ops import render_agent_ops
        render_agent_ops(df, m, cour_df, state_df)

# ══════════════════════════════════════════════════════════════════════════════
# SELLER INTELLIGENCE (tabs — shown only when seller selected)
# ══════════════════════════════════════════════════════════════════════════════
if is_admin and selected_seller != "📊 All Sellers":
    with st.expander(f"🔬 Deep Seller Intelligence — {selected_seller}", expanded=False):
        from utils.seller_intelligence import render_seller_intelligence
        render_seller_intelligence(df, selected_seller,
                                   compute_kpis(df_full)["delivery_pct"],
                                   compute_kpis(df_full)["rto_pct"])
elif not is_admin:
    with st.expander("🔬 Seller Intelligence", expanded=False):
        from utils.seller_intelligence import render_seller_intelligence
        render_seller_intelligence(df, all_sellers[0] if all_sellers else "Your Account",
                                   m["delivery_pct"], m["rto_pct"])

# ══════════════════════════════════════════════════════════════════════════════
# ALL SELLERS TABLE (admin only — compact)
# ══════════════════════════════════════════════════════════════════════════════
if is_admin and selected_seller == "📊 All Sellers":
    with st.expander("🏆 All Sellers — Performance Overview", expanded=True):
        sg = df_full.groupby("seller_name").agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            ndr      =("ndr_status",      lambda x:(x=="Raised").sum()) if "ndr_status" in df_full.columns
                       else ("delivery_status","count"),
        ).reset_index()
        sg["dr"]  = sg["delivered"]/sg["total"].clip(lower=1)*100
        sg["rr"]  = sg["rto"]/sg["total"].clip(lower=1)*100
        sg["ndrr"]= sg["ndr"]/sg["total"].clip(lower=1)*100
        sg = sg.sort_values("dr", ascending=False).reset_index(drop=True)

        rows_html = ""
        for i, row in sg.iterrows():
            hs_s  = compute_health_score({"delivery_pct":row["dr"],"rto_pct":row["rr"],
                                           "ndr_pct":row["ndrr"],"cod_pct":60,
                                           "vas_adoption_score":30,"courier_score_variance":10})
            hc = "#34D399" if hs_s>=80 else ("#FBBF24" if hs_s>=65 else "#F87171")
            dc = "#34D399" if row["dr"]>=80 else ("#FBBF24" if row["dr"]>=65 else "#F87171")
            rc = "#F87171" if row["rr"]>25 else ("#FBBF24" if row["rr"]>15 else "#34D399")
            medal = ["🥇","🥈","🥉"][i] if i < 3 else f"#{i+1}"
            rows_html += (
                f'<div style="display:flex;align-items:center;padding:9px 12px;'
                f'border-bottom:1px solid #1F2937;gap:12px;">'
                f'<div style="width:28px;text-align:center;font-size:0.9rem;">{medal}</div>'
                f'<div style="flex:3;color:#FFFFFF;font-weight:600;font-size:0.85rem;">{row["seller_name"]}</div>'
                f'<div style="flex:1;text-align:right;color:#9CA3AF;font-size:0.82rem;">{int(row["total"]):,}</div>'
                f'<div style="flex:1;text-align:right;color:{dc};font-weight:700;font-size:0.88rem;">{row["dr"]:.0f}%</div>'
                f'<div style="flex:1;text-align:right;color:{rc};font-size:0.82rem;">{row["rr"]:.0f}%</div>'
                f'<div style="flex:1;text-align:right;color:{hc};font-weight:700;font-size:0.82rem;">{hs_s:.0f}/100</div>'
                f'</div>'
            )
        st.markdown(
            f'<div style="background:#111827;border:1px solid #1F2937;border-radius:10px;overflow:hidden;">'
            f'<div style="display:flex;padding:8px 12px;background:#1F2937;gap:12px;">'
            f'<div style="width:28px;"></div>'
            f'<div style="flex:3;color:#6B7280;font-size:0.72rem;font-weight:700;text-transform:uppercase;">Seller</div>'
            f'<div style="flex:1;text-align:right;color:#6B7280;font-size:0.72rem;font-weight:700;text-transform:uppercase;">Shipments</div>'
            f'<div style="flex:1;text-align:right;color:#6B7280;font-size:0.72rem;font-weight:700;text-transform:uppercase;">Delivery%</div>'
            f'<div style="flex:1;text-align:right;color:#6B7280;font-size:0.72rem;font-weight:700;text-transform:uppercase;">RTO%</div>'
            f'<div style="flex:1;text-align:right;color:#6B7280;font-size:0.72rem;font-weight:700;text-transform:uppercase;">Health</div>'
            f'</div>{rows_html}</div>',
            unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# 3PL COURIER INTELLIGENCE + PINCODE INSIGHTS
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("🚚 3PL Courier Intelligence & Pincode Analysis", expanded=False):
    if _has_cour:
        _lyt = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#F3F4F6", height=250, showlegend=False, coloraxis_showscale=False,
                    margin=dict(l=0,r=0,t=36,b=0))

        # ── Row 1: courier bars ──────────────────────────────────────────────
        cc1, cc2 = st.columns(2)
        with cc1:
            fig = px.bar(cour_df.sort_values("delivery_rate"), x="delivery_rate", y="courier",
                         orientation="h", text_auto=".0f",
                         color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
                         labels={"delivery_rate":"Delivery %","courier":""})
            fig.update_layout(**_lyt, title=dict(text="Delivery % by Courier",font=dict(color="#FFFFFF",size=12)),
                              xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
            st.plotly_chart(fig, use_container_width=True)
        with cc2:
            fig2 = px.bar(cour_df.sort_values("rto_rate", ascending=False), x="rto_rate", y="courier",
                          orientation="h", text_auto=".0f",
                          color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
                          labels={"rto_rate":"RTO %","courier":""})
            fig2.update_layout(**_lyt, title=dict(text="RTO % by Courier",font=dict(color="#FFFFFF",size=12)),
                               xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
            st.plotly_chart(fig2, use_container_width=True)

        # ── Row 2: 3PL × Pincode reallocation insights ───────────────────────
        if len(_pin_df) > 0 and "courier" in df.columns and _has_cour:
            st.markdown(
                "<div style='color:#9CA3AF;font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                "letter-spacing:0.06em;margin:14px 0 10px;border-top:1px solid #1F2937;padding-top:12px;'>"
                "📍 3PL × PINCODE REALLOCATION INSIGHTS</div>",
                unsafe_allow_html=True)

            # Per-courier pincode performance
            _cpin = df.groupby(["courier","pincode"]).agg(
                total    =("delivery_status","count"),
                delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
                rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            ).reset_index()
            _cpin["dr"] = _cpin["delivered"] / _cpin["total"].clip(lower=1) * 100
            _cpin["rr"] = _cpin["rto"]       / _cpin["total"].clip(lower=1) * 100

            # Fleet average delivery rate per pincode
            _pin_avg = _cpin.groupby("pincode")["dr"].mean().reset_index().rename(columns={"dr":"fleet_avg_dr"})
            _cpin = _cpin.merge(_pin_avg, on="pincode", how="left")
            _cpin["vs_avg"] = _cpin["dr"] - _cpin["fleet_avg_dr"]

            fleet_del = m["delivery_pct"]

            # Pincodes where a courier is ABOVE average (good allocation signal)
            above_avg = (_cpin[(_cpin["vs_avg"] > 5) & (_cpin["total"] >= 3)]
                         .sort_values("vs_avg", ascending=False).head(6))
            # Pincodes where a courier is BELOW average (reallocation opportunity)
            below_avg = (_cpin[(_cpin["vs_avg"] < -5) & (_cpin["total"] >= 3)]
                         .sort_values("vs_avg").head(6))

            pi1, pi2 = st.columns(2)

            with pi1:
                st.markdown(
                    "<div style='color:#34D399;font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                    "letter-spacing:0.05em;margin-bottom:8px;'>✅ Strong Pincodes — Keep Allocation</div>",
                    unsafe_allow_html=True)
                if len(above_avg) > 0:
                    rows = ""
                    for _, r in above_avg.iterrows():
                        rows += (
                            f'<div style="display:flex;justify-content:space-between;padding:7px 10px;'
                            f'border-bottom:1px solid #1F2937;font-size:0.8rem;">'
                            f'<span style="color:#FFFFFF;font-family:monospace;">{str(r["pincode"])}</span>'
                            f'<span style="color:#9CA3AF;">{r["courier"][:12]}</span>'
                            f'<span style="color:#34D399;font-weight:700;">{r["dr"]:.0f}%</span>'
                            f'<span style="color:#6B7280;font-size:0.75rem;">+{r["vs_avg"]:.0f}% vs avg</span>'
                            f'</div>'
                        )
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;">'
                        f'<div style="display:flex;justify-content:space-between;padding:6px 10px;'
                        f'background:#1F2937;font-size:0.68rem;color:#6B7280;font-weight:700;text-transform:uppercase;">'
                        f'<span>Pincode</span><span>Courier</span><span>Del%</span><span>vs Avg</span></div>'
                        f'{rows}</div>',
                        unsafe_allow_html=True)
                    st.markdown(
                        "<div style='color:#34D399;font-size:0.78rem;margin-top:6px;padding:6px 10px;"
                        "background:rgba(52,211,153,0.06);border-radius:6px;'>"
                        "💡 These couriers outperform fleet average at these pincodes — maintain or increase volume.</div>",
                        unsafe_allow_html=True)
                else:
                    st.caption("Insufficient pincode × courier data for comparison.")

            with pi2:
                st.markdown(
                    "<div style='color:#F87171;font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                    "letter-spacing:0.05em;margin-bottom:8px;'>⚠️ Underperforming Pincodes — Reallocate</div>",
                    unsafe_allow_html=True)
                if len(below_avg) > 0:
                    best_cour_overall = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["courier"] \
                                        if _has_cour else "top courier"
                    rows = ""
                    for _, r in below_avg.iterrows():
                        rows += (
                            f'<div style="display:flex;justify-content:space-between;padding:7px 10px;'
                            f'border-bottom:1px solid #1F2937;font-size:0.8rem;">'
                            f'<span style="color:#FFFFFF;font-family:monospace;">{str(r["pincode"])}</span>'
                            f'<span style="color:#F87171;">{r["courier"][:12]}</span>'
                            f'<span style="color:#F87171;font-weight:700;">{r["dr"]:.0f}%</span>'
                            f'<span style="color:#6B7280;font-size:0.75rem;">{r["vs_avg"]:.0f}% vs avg</span>'
                            f'</div>'
                        )
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;">'
                        f'<div style="display:flex;justify-content:space-between;padding:6px 10px;'
                        f'background:#1F2937;font-size:0.68rem;color:#6B7280;font-weight:700;text-transform:uppercase;">'
                        f'<span>Pincode</span><span>Current Courier</span><span>Del%</span><span>vs Avg</span></div>'
                        f'{rows}</div>',
                        unsafe_allow_html=True)
                    reallocate_count = len(below_avg)
                    st.markdown(
                        f"<div style='color:#F87171;font-size:0.78rem;margin-top:6px;padding:6px 10px;"
                        f"background:rgba(248,113,113,0.06);border-radius:6px;'>"
                        f"💡 Shift {reallocate_count} pincode(s) from underperforming couriers to "
                        f"<b style='color:#34D399;'>{best_cour_overall}</b> — "
                        f"estimated delivery improvement based on fleet average.</div>",
                        unsafe_allow_html=True)
                else:
                    st.caption("All couriers performing at or above average in sampled pincodes.")

        # ── Pincode risk table ───────────────────────────────────────────────
        if len(_high_rto_pins) > 0:
            st.markdown(
                "<div style='color:#F87171;font-size:0.72rem;font-weight:700;text-transform:uppercase;"
                "letter-spacing:0.05em;margin:14px 0 8px;border-top:1px solid #1F2937;padding-top:12px;'>"
                "🚨 HIGH-RISK PINCODES — COD RESTRICTION RECOMMENDED</div>",
                unsafe_allow_html=True)
            rows = ""
            for _, r in _high_rto_pins.iterrows():
                state_lbl = str(r["state"])[:12] if "state" in _high_rto_pins.columns and r.get("state") not in [None,"count"] else ""
                rc2 = "#F87171" if r["rr"] > 50 else "#FBBF24"
                action = "Blacklist COD" if r["rr"] > 50 else "Restrict COD"
                rows += (
                    f'<div style="display:flex;justify-content:space-between;align-items:center;'
                    f'padding:8px 12px;border-bottom:1px solid #1F2937;font-size:0.8rem;">'
                    f'<span style="color:#FFFFFF;font-family:monospace;flex:1;">{str(r["pincode_str"])}</span>'
                    f'<span style="color:#9CA3AF;flex:1;">{state_lbl}</span>'
                    f'<span style="color:{rc2};font-weight:700;flex:0.8;">{r["rr"]:.0f}% RTO</span>'
                    f'<span style="color:#9CA3AF;flex:0.8;">{int(r["total"]):,} shpts</span>'
                    f'<span style="background:{rc2}20;color:{rc2};border:1px solid {rc2}40;'
                    f'padding:2px 8px;border-radius:99px;font-size:0.72rem;font-weight:600;">{action}</span>'
                    f'</div>'
                )
            st.markdown(
                f'<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;">'
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:6px 12px;background:#1F2937;font-size:0.68rem;color:#6B7280;'
                f'font-weight:700;text-transform:uppercase;">'
                f'<span style="flex:1;">Pincode</span><span style="flex:1;">State</span>'
                f'<span style="flex:0.8;">RTO%</span><span style="flex:0.8;">Shipments</span>'
                f'<span>Action</span></div>{rows}</div>',
                unsafe_allow_html=True)

        # ── Concentration alert ──────────────────────────────────────────────
        if conc.get("is_concentrated"):
            st.markdown(
                f'<div style="background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.3);'
                f'border-radius:8px;padding:10px 14px;font-size:0.82rem;color:#F87171;margin-top:10px;">'
                f'⚠️ <b>Courier Concentration Risk:</b> {conc["dominant_pct"]:.0f}% on '
                f'{conc["dominant_courier"]}. Activate Multi-Courier Allocation. '
                f'Add ElasticRun / PiknDel / Blitz for NDD coverage.</div>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FLOATING JAGAU AI BUTTON
# ══════════════════════════════════════════════════════════════════════════════
render_chat_button(df)
