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

# ── Risks (max 4, ranked by severity) ────────────────────────────────────────
risks = []
if m["ndr_pct"] > 20:
    pin_ndr_count = 0
    if "pincode" in df.columns and "ndr_status" in df.columns:
        pg = df.groupby("pincode").agg(ndr=("ndr_status", lambda x:(x=="Raised").sum()),
                                       total=("delivery_status","count")).reset_index()
        pg["nr"] = pg["ndr"]/pg["total"].clip(lower=1)*100
        pin_ndr_count = int((pg["nr"]>20).sum())
    risks.append({
        "icon":"🚨","label":"High NDR",
        "detail": f"{m['ndr_count']:,} active NDRs ({m['ndr_pct']:.0f}% of shipments)"
                  + (f" · {pin_ndr_count} high-NDR pincodes" if pin_ndr_count else ""),
    })
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
if hs >= 80:   hs_col="#34D399"; hs_lbl="Healthy";     hs_icon="🟢"
elif hs >= 65: hs_col="#FBBF24"; hs_lbl="Needs Attention"; hs_icon="🟡"
else:          hs_col="#F87171"; hs_lbl="At Risk";      hs_icon="🔴"

st.markdown(f"""
<div class="jaggu-brief">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              flex-wrap:wrap;gap:12px;margin-bottom:20px;">
    <div>
      <div style="color:#818CF8;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.08em;margin-bottom:4px;">
        🤖 JaGau AI Briefing {scope_label}</div>
      <div style="color:#6B7280;font-size:0.72rem;">
        Period: <b style="color:#9CA3AF;">{_period}</b> ·
        {m['total']:,} shipments · {m['delivered']:,} delivered of {att:,} attempted
        {"· " + str(pending) + " Pending Pickup excluded" if pending > 0 else ""}
      </div>
    </div>
    <div style="background:#0B0F19;border-radius:12px;padding:10px 20px;text-align:center;min-width:140px;">
      <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;font-weight:600;">Seller Health</div>
      <div style="font-size:2.4rem;font-weight:800;color:{hs_col};line-height:1.1;">{hs:.0f}</div>
      <div style="font-size:0.72rem;color:{hs_col};font-weight:700;">{hs_icon} {hs_lbl}</div>
    </div>
  </div>

  <div style="display:grid;grid-template-columns:1fr 1fr;gap:20px;margin-bottom:20px;">
    <div>
      <div class="jaggu-section-lbl" style="color:#F87171;">⚡ TOP RISKS</div>
      {"".join(f'<div class="risk-item"><b style="color:#F87171;">{r["icon"]} {r["label"]}</b><br>{r["detail"]}</div>' for r in risks[:3])}
    </div>
    <div>
      <div class="jaggu-section-lbl" style="color:#34D399;">💰 TOP OPPORTUNITIES</div>
      {"".join(f'<div class="opp-item"><b style="color:#34D399;">{o["icon"]} {o["label"]}</b><br>{o["detail"]}</div>' for o in opps[:3])}
    </div>
  </div>

  <div style="border-top:1px solid #1F2937;padding-top:16px;margin-bottom:16px;">
    <div class="jaggu-section-lbl" style="color:#818CF8;">✅ RECOMMENDED ACTIONS</div>
    {"".join(f'<div class="action-item"><b style="color:#FFFFFF;">#{a["rank"]}. {a["name"]}</b><br>{a["detail"]}<br><span style="color:#818CF8;font-size:0.78rem;">→ {a["metric"]}</span></div>' for a in actions[:4])}
  </div>

  <div style="background:#0B0F19;border-radius:10px;padding:14px 18px;margin-bottom:16px;
              display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:12px;">
    <div>
      <div style="color:#6B7280;font-size:0.7rem;text-transform:uppercase;font-weight:600;margin-bottom:4px;">
        Expected Impact (if all actions activated)</div>
      <div style="display:flex;gap:16px;flex-wrap:wrap;">
        <span class="impact-pill" style="background:rgba(52,211,153,0.12);color:#34D399;">
          📈 +{delivery_gain:.1f}% Delivery Rate</span>
        <span class="impact-pill" style="background:rgba(248,113,113,0.12);color:#F87171;">
          📉 -{rto_reduction:.1f}% RTO Rate</span>
        <span class="impact-pill" style="background:rgba(129,140,248,0.12);color:#818CF8;">
          📞 ~{total_recoverable:,} shipments recoverable</span>
      </div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

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
# 3PL COURIER INTELLIGENCE  (compact — 2 bars only)
# ══════════════════════════════════════════════════════════════════════════════
with st.expander("🚚 Courier Intelligence", expanded=False):
    if _has_cour:
        _lyt = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#F3F4F6", height=260, showlegend=False, coloraxis_showscale=False,
                    margin=dict(l=0,r=0,t=36,b=0))
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
            fig2 = px.bar(cour_df.sort_values("rto_rate",ascending=False), x="rto_rate", y="courier",
                          orientation="h", text_auto=".0f",
                          color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
                          labels={"rto_rate":"RTO %","courier":""})
            fig2.update_layout(**_lyt, title=dict(text="RTO % by Courier",font=dict(color="#FFFFFF",size=12)),
                               xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
            st.plotly_chart(fig2, use_container_width=True)
        # Concentration alert
        if conc.get("is_concentrated"):
            st.markdown(
                f'<div style="background:rgba(248,113,113,0.08);border:1px solid rgba(248,113,113,0.3);'
                f'border-radius:8px;padding:10px 14px;font-size:0.82rem;color:#F87171;">'
                f'⚠️ <b>Courier Concentration Risk:</b> {conc["dominant_pct"]:.0f}% on {conc["dominant_courier"]}. '
                f'Activate Multi-Courier Allocation. Add ElasticRun / PiknDel / Blitz.</div>',
                unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# FLOATING JAGAU AI BUTTON
# ══════════════════════════════════════════════════════════════════════════════
render_chat_button(df)
