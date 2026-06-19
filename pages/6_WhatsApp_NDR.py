import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis

st.set_page_config(page_title="WhatsApp NDR · GDI", page_icon="💬", layout="wide")
apply_styles()
df = render_sidebar_and_get_data()
m  = compute_kpis(df)

# WhatsApp eligible: COD + NDR Raised + opt-in + not wrong address
wa_eligible = df[
    (df["ndr_status"] == "Raised") &
    (df["payment_type"] == "COD") &
    (df.get("whatsapp_opt_in", pd.Series([True]*len(df), index=df.index)).astype(bool))
].copy()

# Exclude wrong address — send those to calling
if "ndr_reason" in wa_eligible.columns:
    wa_eligible = wa_eligible[~wa_eligible["ndr_reason"].str.contains("Wrong|Incomplete", na=False, case=False)]

np.random.seed(7)
n_total = len(wa_eligible)
n_sent     = min(n_total, max(0, int(n_total * 0.85)))
n_deliv    = int(n_sent * 0.84)
n_read     = int(n_deliv * 0.78)
n_replied  = int(n_read  * 0.58)
n_saved    = int(n_replied* 0.72)
rev_saved  = int(n_saved * df["order_value"].mean()) if len(df) > 0 else 0

st.markdown("""
<div class="header-card">
  <h1 class="header-title">💬 WhatsApp NDR Engine</h1>
  <p class="header-subtitle">Convert COD non-deliveries into successful deliveries via automated WhatsApp engagement.</p>
</div>""", unsafe_allow_html=True)

# Funnel
st.markdown("<div class='section-title'>📊 WhatsApp Engagement Funnel</div>", unsafe_allow_html=True)
fc1, fc2 = st.columns([1,1])

with fc1:
    stages = ["Eligible","Sent","Delivered","Read","Replied","Deliveries Saved"]
    values = [n_total, n_sent, n_deliv, n_read, n_replied, n_saved]
    colors = ["#4F46E5","#6366F1","#818CF8","#A5B4FC","#C4B5FD","#34D399"]
    fig = go.Figure(go.Funnel(
        y=stages, x=values, textposition="inside",
        textinfo="value+percent initial",
        marker=dict(color=colors),
        connector=dict(line=dict(color="#374151",width=1)),
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F3F4F6", font_family="Outfit",
        height=340, margin=dict(l=0,r=0,t=10,b=0),
    )
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with fc2:
    st.markdown(f"""
    <div class="saas-card" style="height:100%;">
      <div class="section-title" style="border:none;padding:0;margin-bottom:16px;">Funnel Summary</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;">
        <div style="background:#0B0F19;border-radius:8px;padding:14px;text-align:center;">
          <div class="metric-label">Eligible for WhatsApp</div>
          <div class="metric-value" style="color:#818CF8;font-size:1.5rem;">{n_total}</div>
        </div>
        <div style="background:#0B0F19;border-radius:8px;padding:14px;text-align:center;">
          <div class="metric-label">Messages Sent</div>
          <div class="metric-value" style="color:#60A5FA;font-size:1.5rem;">{n_sent}</div>
        </div>
        <div style="background:#0B0F19;border-radius:8px;padding:14px;text-align:center;">
          <div class="metric-label">Replied</div>
          <div class="metric-value" style="color:#FBBF24;font-size:1.5rem;">{n_replied}</div>
        </div>
        <div style="background:#0B0F19;border-radius:8px;padding:14px;text-align:center;
                    border:1px solid rgba(16,185,129,0.3);">
          <div class="metric-label" style="color:#34D399;">Deliveries Saved</div>
          <div class="metric-value" style="color:#34D399;font-size:1.5rem;">{n_saved}</div>
        </div>
      </div>
      <div style="margin-top:16px;background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);
                  border-radius:8px;padding:14px;text-align:center;">
        <div class="metric-label" style="color:#34D399;">Revenue Recovered (Est.)</div>
        <div style="font-size:1.8rem;font-weight:800;color:#34D399;">₹{rev_saved:,}</div>
      </div>
    </div>""", unsafe_allow_html=True)

# Template preview
st.markdown("<div class='section-title'>📱 WhatsApp Message Templates</div>", unsafe_allow_html=True)
t1, t2 = st.columns(2)
with t1:
    st.markdown("""
    <div class="saas-card" style="border:1px solid rgba(37,211,102,0.3);">
      <div style="color:#25D366;font-weight:700;margin-bottom:10px;">📲 Template 1 — Reschedule</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;font-size:0.88rem;
                  line-height:1.6;color:#D1D5DB;border:1px solid #1F2937;">
        <strong style="color:#25D366;">📦 Velocity Express</strong><br><br>
        Hi! Your order (<em>₹1,499</em>) couldn't be delivered today.<br><br>
        Please choose an option:<br>
        <strong>1️⃣</strong> Reschedule for tomorrow<br>
        <strong>2️⃣</strong> Update delivery address<br>
        <strong>3️⃣</strong> Cancel order<br><br>
        <em style="color:#6B7280;">Reply within 12 hours to avoid return.</em>
      </div>
    </div>""", unsafe_allow_html=True)
with t2:
    st.markdown("""
    <div class="saas-card" style="border:1px solid rgba(37,211,102,0.3);">
      <div style="color:#25D366;font-weight:700;margin-bottom:10px;">📲 Template 2 — Confirm Delivery</div>
      <div style="background:#0B0F19;border-radius:10px;padding:14px;font-size:0.88rem;
                  line-height:1.6;color:#D1D5DB;border:1px solid #1F2937;">
        <strong style="color:#25D366;">📦 Velocity Express</strong><br><br>
        Hello! Our delivery partner will attempt delivery of your order (<em>₹2,999</em>) again tomorrow.<br><br>
        Please confirm availability:<br>
        <strong>✅</strong> I'll be available<br>
        <strong>🕐</strong> Choose a time slot<br>
        <strong>📍</strong> Change address<br><br>
        <em style="color:#6B7280;">Confirm to ensure successful delivery.</em>
      </div>
    </div>""", unsafe_allow_html=True)

# Queue table
st.markdown("<div class='section-title'>📋 WhatsApp Engagement Queue</div>", unsafe_allow_html=True)
if len(wa_eligible) > 0:
    show = wa_eligible[["state","payment_type","order_value","ndr_reason","attempt_count"] +
                        (["ndr_age_hours"] if "ndr_age_hours" in wa_eligible.columns else [])
                       ].head(30).copy()
    np.random.seed(42)
    statuses = ["Pending","Sent","Delivered","Read","Replied"]
    probs    = [0.20, 0.20, 0.20, 0.20, 0.20]
    show["WA Status"] = np.random.choice(statuses, size=len(show), p=probs)
    show = show.rename(columns={
        "state":"State","payment_type":"Type","order_value":"Order Value",
        "ndr_reason":"NDR Reason","attempt_count":"Attempts","ndr_age_hours":"Age (hrs)"
    })
    show["Order Value"] = show["Order Value"].apply(lambda x: f"₹{x:,}")
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.dataframe(show, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
else:
    st.info("No COD NDR shipments with WhatsApp opt-in found in the current filter.")
