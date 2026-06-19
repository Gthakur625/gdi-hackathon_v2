import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis

st.set_page_config(page_title="Impact Simulator · GDI", page_icon="📊", layout="wide", initial_sidebar_state="expanded")
apply_styles()
df = render_sidebar_and_get_data()
m  = compute_kpis(df)

st.markdown("""
<div class="header-card">
  <h1 class="header-title">📊 Delivery Impact Simulator</h1>
  <p class="header-subtitle">Model the revenue impact of activating each Velocity VAS product — before you commit.</p>
</div>""", unsafe_allow_html=True)

avg_ov  = df["order_value"].mean() if len(df)>0 else 1500
total   = m["total"]
current_del = m["delivered"]

c_inputs, c_outputs = st.columns([1,1])

with c_inputs:
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top:0;color:#FFFFFF;'>⚙️ Simulate VAS Activation</h4>", unsafe_allow_html=True)

    sim_ats = st.slider("Shift to ATS (Velocity) — % of non-ATS volume", 0, 100, 30, 5,
                        help="Reallocate non-ATS shipments to ATS. ATS delivers at ~88%.")
    sim_addr = st.checkbox("Enable ATS Address Verification", value=m["rto_pct"]>20,
                           help="Reduces Bihar/UP RTO by ~5% across the board.")
    sim_cod  = st.slider("Convert COD to Prepaid — %", 0, 100, 20, 5,
                         help="Prepaid has ~92% delivery vs COD's lower rate.")
    sim_calling = st.slider("AI Calling NDR Recovery — %", 0, 50, 35, 5,
                            help="Percentage of NDR shipments recovered via AI calling.")
    sim_wa   = st.checkbox("Enable WhatsApp NDR", value=m["cod_pct"]>60,
                           help="Reduces COD RTO by ~8% via WhatsApp engagement.")
    sim_routing = st.checkbox("Enable ATS Smart Routing", value=False,
                              help="Pincode-level routing improves delivery by 3–5%.")

    if st.button("⚡ Apply All Recommended VAS", use_container_width=True):
        sim_ats = 50; sim_addr = True; sim_cod = 25
        sim_calling = 38; sim_wa = True; sim_routing = True
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ---- Simulation logic ----
np.random.seed(42)
sim_df = df.copy()

# 1. ATS allocation
if sim_ats > 0:
    non_ats = sim_df[sim_df["courier"]!="ATS (Velocity)"].index
    n_move  = int(len(non_ats) * sim_ats / 100)
    if n_move > 0:
        idxs = np.random.choice(non_ats, size=n_move, replace=False)
        sim_df.loc[idxs,"courier"] = "ATS (Velocity)"
        for idx in idxs:
            r = np.random.rand()
            if r < 0.88:   sim_df.loc[idx,"delivery_status"]="Delivered"
            elif r < 0.93: sim_df.loc[idx,"delivery_status"]="RTO"
            else:           sim_df.loc[idx,"delivery_status"]="NDR"

# 2. Address Verification (reduce Bihar/UP RTO by 5%)
if sim_addr:
    risk_states = sim_df[
        (sim_df["state"].isin(["Bihar","Uttar Pradesh"])) &
        (sim_df["delivery_status"]=="RTO")
    ].index
    n_fix = int(len(risk_states)*0.05)
    if n_fix>0:
        idxs = np.random.choice(risk_states, size=n_fix, replace=False)
        sim_df.loc[idxs,"delivery_status"]="Delivered"

# 3. COD to Prepaid
if sim_cod > 0:
    cod_idx = sim_df[sim_df["payment_type"]=="COD"].index
    n_conv  = int(len(cod_idx)*sim_cod/100)
    if n_conv>0:
        idxs = np.random.choice(cod_idx, size=n_conv, replace=False)
        sim_df.loc[idxs,"payment_type"]="Prepaid"
        for idx in idxs:
            r = np.random.rand()
            if r < 0.92:   sim_df.loc[idx,"delivery_status"]="Delivered"
            elif r < 0.98: sim_df.loc[idx,"delivery_status"]="RTO"
            else:           sim_df.loc[idx,"delivery_status"]="NDR"

# 4. AI Calling NDR recovery
if sim_calling > 0 and "ndr_status" in sim_df.columns:
    ndr_idx = sim_df[sim_df["ndr_status"]=="Raised"].index
    n_rec   = int(len(ndr_idx)*sim_calling/100)
    if n_rec>0:
        idxs = np.random.choice(ndr_idx, size=n_rec, replace=False)
        sim_df.loc[idxs,"delivery_status"]="Delivered"

# 5. WhatsApp NDR — reduce COD RTO by 8%
if sim_wa:
    cod_rto_idx = sim_df[(sim_df["payment_type"]=="COD")&(sim_df["delivery_status"]=="RTO")].index
    n_rec = int(len(cod_rto_idx)*0.08)
    if n_rec>0:
        idxs = np.random.choice(cod_rto_idx, size=n_rec, replace=False)
        sim_df.loc[idxs,"delivery_status"]="Delivered"

# 6. Smart Routing — improve delivery 3%
if sim_routing:
    not_del = sim_df[sim_df["delivery_status"]!="Delivered"].index
    n_fix   = int(len(not_del)*0.03)
    if n_fix>0:
        idxs = np.random.choice(not_del, size=n_fix, replace=False)
        sim_df.loc[idxs,"delivery_status"]="Delivered"

# Results
sim_delivered = (sim_df["delivery_status"]=="Delivered").sum()
sim_del_pct   = sim_delivered/total*100 if total>0 else 0
delta_del     = sim_delivered - current_del
delta_pct     = sim_del_pct - m["delivery_pct"]
rev_unlock    = delta_del * avg_ov
logistics_saved = max(0,(m["rto_count"] - (sim_df["delivery_status"]=="RTO").sum())) * avg_ov * 0.12
net_impact    = rev_unlock + logistics_saved

with c_outputs:
    st.markdown('<div class="saas-card" style="height:100%;">', unsafe_allow_html=True)
    st.markdown("<h4 style='margin-top:0;color:#FFFFFF;'>📈 Simulated Projections</h4>", unsafe_allow_html=True)

    r1,r2 = st.columns(2)
    r1.metric("Projected Delivery %",  f"{sim_del_pct:.1f}%",  f"+{delta_pct:.1f}% vs now")
    r2.metric("Additional Deliveries", f"+{int(delta_del)}",   f"from {current_del:,} → {sim_delivered:,}")
    r3,r4 = st.columns(2)
    r3.metric("Revenue Unlock",        f"₹{rev_unlock:,.0f}",  "from extra deliveries")
    r4.metric("Logistics Cost Saved",  f"₹{logistics_saved:,.0f}", "from reduced RTOs")

    st.markdown(f"""
    <div style="background:rgba(16,185,129,0.08);border:1px solid rgba(16,185,129,0.3);
                border-radius:10px;padding:14px;margin-top:12px;text-align:center;">
      <div class="metric-label" style="color:#34D399;">Total Net Impact</div>
      <div style="font-size:2rem;font-weight:800;color:#34D399;">₹{net_impact:,.0f}</div>
    </div>""", unsafe_allow_html=True)

    # Bar chart
    fig = go.Figure()
    fig.add_bar(name="Current", x=["Deliveries"], y=[current_del],  marker_color="#4F46E5")
    fig.add_bar(name="Projected",x=["Deliveries"], y=[sim_delivered],marker_color="#10B981")
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F3F4F6", barmode="group", height=200,
        margin=dict(l=0,r=0,t=10,b=0),
        legend=dict(bgcolor="rgba(0,0,0,0)"),
        xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#1F2937"),
    )
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

# VAS Revenue Breakdown
st.markdown("<div class='section-title'>💡 Revenue Breakdown by VAS Action</div>", unsafe_allow_html=True)
vas_rows = []
if sim_ats > 0:
    n = int(len(df[df["courier"]!="ATS (Velocity)"])*sim_ats/100)
    vas_rows.append({"VAS Action":"ATS Allocation Shift","Shipments Impacted":n,"Est. Revenue":int(n*avg_ov*0.08)})
if sim_addr:
    n2 = int(len(df[df["state"].isin(["Bihar","Uttar Pradesh"])&(df["delivery_status"]=="RTO")])*0.05)
    vas_rows.append({"VAS Action":"Address Verification","Shipments Impacted":n2,"Est. Revenue":int(n2*avg_ov)})
if sim_cod>0:
    n3 = int(len(df[df["payment_type"]=="COD"])*sim_cod/100)
    vas_rows.append({"VAS Action":"COD→Prepaid Conversion","Shipments Impacted":n3,"Est. Revenue":int(n3*avg_ov*0.08)})
if sim_calling>0:
    n4 = int(m["ndr_count"]*sim_calling/100)
    vas_rows.append({"VAS Action":"AI Calling Recovery","Shipments Impacted":n4,"Est. Revenue":int(n4*avg_ov)})
if sim_wa:
    n5 = int(m["rto_count"]*0.08)
    vas_rows.append({"VAS Action":"WhatsApp NDR Recovery","Shipments Impacted":n5,"Est. Revenue":int(n5*avg_ov)})
if sim_routing:
    n6 = int(total*0.03)
    vas_rows.append({"VAS Action":"Smart Routing Uplift","Shipments Impacted":n6,"Est. Revenue":int(n6*avg_ov)})

if vas_rows:
    bdf = pd.DataFrame(vas_rows)
    bdf["Est. Revenue"] = bdf["Est. Revenue"].apply(lambda x: f"₹{x:,}")
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.dataframe(bdf, use_container_width=True, hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)
