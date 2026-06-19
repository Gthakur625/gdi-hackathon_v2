import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(__file__))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                           compute_courier_perf, compute_state_perf, get_recommendations,
                           get_anomalies)

st.set_page_config(
    page_title="GDI · Growth & Delivery Intelligence",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()
df = render_sidebar_and_get_data()

m   = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs  = compute_health_score(m)
recs       = get_recommendations(m)
state_perf = compute_state_perf(df)
cour_perf  = compute_courier_perf(df)
anomalies  = get_anomalies(df, m, state_perf, cour_perf)

if hs >= 80:   risk_level="Low Risk";    summary_color="#34D399"; risk_badge='<span class="badge-risk-low">🟢 Low Risk</span>'
elif hs >= 65: risk_level="Medium Risk"; summary_color="#FBBF24"; risk_badge='<span class="badge-risk-medium">🟡 Medium Risk</span>'
else:          risk_level="High Risk";   summary_color="#FCA5A5"; risk_badge='<span class="badge-risk-high">🔴 High Risk</span>'

total_potential = sum(r["revenue"] for r in recs)

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-card">
  <h1 class="header-title">⚡ Velocity GDI — Growth & Delivery Intelligence Engine</h1>
  <p class="header-subtitle">AI-Powered Seller Operations Consultant · Diagnose. Recommend. Act.</p>
</div>""", unsafe_allow_html=True)

# ── EXECUTIVE SUMMARY ────────────────────────────────────────────────────────
n_issues = len(anomalies)
issue_word = "anomaly" if n_issues==1 else "anomalies"
st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(180deg,#161F30 0%,#111827 100%);border-left:4px solid #4F46E5;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
    <div style="flex:1;">
      <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">Executive Overview</div>
      <h2 style="color:#FFFFFF;font-size:1.55rem;font-weight:700;margin:6px 0;">
        Operations Status: <span style="color:{summary_color};">{risk_level}</span>
        &nbsp;·&nbsp; Health Score: <span style="color:#818CF8;">{hs:.0f}/100</span>
      </h2>
      <p style="color:#D1D5DB;font-size:0.93rem;line-height:1.55;margin:0;max-width:860px;">
        GDI scanned <strong>{m['total']:,} shipments</strong> and detected <strong>{n_issues} {issue_word}</strong>.
        Delivery rate is <strong>{m['delivery_pct']:.1f}%</strong> with RTO at
        <strong>{m['rto_pct']:.1f}%</strong>.
        Activating the {len(recs)} recommended VAS products can unlock an estimated
        <strong>₹{total_potential:,}</strong> in revenue.
      </p>
    </div>
    <div style="text-align:right;min-width:170px;">
      <div class="metric-label">Health Score</div>
      <div style="font-size:2.4rem;font-weight:800;color:#818CF8;">{hs:.0f}<span style="font-size:1.1rem;color:#6B7280;">/100</span></div>
      <div style="margin-top:6px;">{risk_badge}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── KPI CARDS ────────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5,k6 = st.columns(6)
kpis = [
    (k1,"Delivery Rate",     f"{m['delivery_pct']:.1f}%", "#34D399"),
    (k2,"RTO Rate",          f"{m['rto_pct']:.1f}%",      "#F87171"),
    (k3,"NDR Rate",          f"{m['ndr_pct']:.1f}%",      "#FBBF24"),
    (k4,"Total Shipments",   f"{m['total']:,}",            "#60A5FA"),
    (k5,"Delivered",         f"{m['delivered']:,}",        "#10B981"),
    (k6,"Revenue Unlock",    f"₹{total_potential:,}",      "#34D399"),
]
for col, label, val, color in kpis:
    col.markdown(f"""<div class="saas-card" style="text-align:center;">
      <div class="metric-label">{label}</div>
      <div class="metric-value" style="color:{color};font-size:1.6rem;">{val}</div>
    </div>""", unsafe_allow_html=True)

# ── ANOMALIES (compact) ───────────────────────────────────────────────────────
if anomalies:
    st.markdown("<div class='section-title'>🔍 GDI Detected Issues — Click Pages in Sidebar for Deep Dive</div>", unsafe_allow_html=True)
    level_css = {"critical":"anomaly-critical","warning":"anomaly-warning","info":"anomaly-info"}
    for a in anomalies[:3]:
        css = level_css.get(a["level"],"anomaly-info")
        st.markdown(f"""
        <div class="{css}">
          <strong style="color:#FFFFFF;">{a['icon']} {a['title']}</strong>
          <p style="color:#9CA3AF;margin:6px 0 6px 0;font-size:0.88rem;">{a['detail']}</p>
          <span style="color:#818CF8;font-size:0.82rem;font-weight:600;">→ {a['fix']}</span>
        </div>""", unsafe_allow_html=True)

# ── COURIER + STATE CHARTS ────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🚚 Courier & Geographic Intelligence</div>", unsafe_allow_html=True)
gc1, gc2 = st.columns(2)

with gc1:
    if len(cour_perf) > 0:
        fig = px.bar(
            cour_perf.sort_values("delivery_rate"),
            x="delivery_rate", y="courier", orientation="h", text_auto=".1f",
            color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
            labels={"delivery_rate":"Delivery %","courier":"Courier"},
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#F3F4F6",height=260,margin=dict(l=0,r=0,t=0,b=0),
                          showlegend=False,coloraxis_showscale=False)
        fig.update_xaxes(showgrid=True,gridcolor="#1F2937")
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin:0 0 10px;color:#FFFFFF;'>Courier Delivery %</h4>", unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with gc2:
    if len(state_perf) > 0:
        worst5 = state_perf.sort_values("rto_rate",ascending=False).head(5)
        fig2 = px.bar(
            worst5.sort_values("rto_rate"),
            x="rto_rate", y="state", orientation="h", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#F59E0B","#EF4444"],
            labels={"rto_rate":"RTO %","state":"State"},
        )
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#F3F4F6",height=260,margin=dict(l=0,r=0,t=0,b=0),
                           showlegend=False,coloraxis_showscale=False)
        fig2.update_xaxes(showgrid=True,gridcolor="#1F2937")
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin:0 0 10px;color:#FFFFFF;'>Worst 5 States by RTO %</h4>", unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ── VAS RECOMMENDATION CARDS ──────────────────────────────────────────────────
if recs:
    st.markdown("<div class='section-title'>💡 GDI Recommended Actions — Ranked by Revenue Impact</div>", unsafe_allow_html=True)
    rec_cols = st.columns(min(len(recs),4))
    for i, rec in enumerate(recs[:4]):
        with rec_cols[i]:
            st.markdown(f"""
            <div class="saas-card" style="border:1px solid {rec['color']}30;">
              <span class="badge-recommend">{rec['badge']}</span>
              <h4 style="color:#FFFFFF;margin:10px 0 6px;font-size:1rem;">{rec['name']}</h4>
              <p style="color:#9CA3AF;font-size:0.82rem;margin:0 0 12px;">{rec['impact']}</p>
              <div style="border-top:1px solid #1F2937;padding-top:10px;">
                <span style="font-size:0.72rem;color:#34D399;text-transform:uppercase;font-weight:600;">Revenue Unlock</span>
                <div style="font-size:1.2rem;font-weight:700;color:#34D399;">₹{rec['revenue']:,}</div>
              </div>
            </div>""", unsafe_allow_html=True)

# ── QUICK NAV GUIDE ───────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🧭 GDI Module Guide</div>", unsafe_allow_html=True)
nav_items = [
    ("❤️","Seller Health Score","Your overall delivery health in one number"),
    ("🔍","Root Cause Analysis","Why delivery is failing — auto-detected anomalies"),
    ("📦","SKU Intelligence","Which product is underperforming and why"),
    ("🚀","ATS Recommendations","Ranked VAS products mapped to your exact problems"),
    ("📞","AI Calling Engine","Priority calling queue with recovery probabilities"),
    ("💬","WhatsApp NDR","COD NDR engagement funnel and queue"),
    ("🤖","AI Chat Assistant","Ask anything — answers grounded in your data"),
    ("📊","Impact Simulator","Model revenue impact of each VAS activation"),
]
nc = st.columns(4)
for i, (icon, title, desc) in enumerate(nav_items):
    nc[i%4].markdown(f"""
    <div class="saas-card" style="text-align:center;padding:16px;">
      <div style="font-size:1.8rem;">{icon}</div>
      <div style="color:#FFFFFF;font-weight:700;margin:6px 0 4px;font-size:0.9rem;">{title}</div>
      <div style="color:#9CA3AF;font-size:0.75rem;">{desc}</div>
    </div>""", unsafe_allow_html=True)
