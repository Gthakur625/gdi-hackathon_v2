import streamlit as st
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis

st.set_page_config(page_title="AI Calling Engine · GDI", page_icon="📞", layout="wide", initial_sidebar_state="expanded")
apply_styles()
df = render_sidebar_and_get_data()
m  = compute_kpis(df)

# NDR recovery probability
STATE_RECOVERY = {
    "Maharashtra":0.88,"Karnataka":0.85,"Delhi":0.87,"Tamil Nadu":0.83,
    "Gujarat":0.82,"Haryana":0.80,"West Bengal":0.75,"Rajasthan":0.70,
    "Uttar Pradesh":0.55,"Bihar":0.42,
}
REASON_RECOVERY = {
    "Customer Not Available":0.90,"Delivery Requested for Later":0.85,
    "Door Locked / Building Issue":0.72,"Customer Refused Delivery":0.45,
    "Wrong / Incomplete Address":0.35,"":0.60,
}
def age_factor(hours):
    if hours <= 24:  return 1.0
    if hours <= 48:  return 0.85
    if hours <= 72:  return 0.65
    return 0.40

ndr_queue = df[df["ndr_status"]=="Raised"].copy()

if "ndr_age_hours" not in ndr_queue.columns: ndr_queue["ndr_age_hours"]=24
if "ndr_reason"    not in ndr_queue.columns: ndr_queue["ndr_reason"]=""
if "attempt_count" not in ndr_queue.columns: ndr_queue["attempt_count"]=1
if "calling_attempted" not in ndr_queue.columns: ndr_queue["calling_attempted"]=False

ndr_queue["state_rec"]  = ndr_queue["state"].map(STATE_RECOVERY).fillna(0.65)
ndr_queue["reason_rec"] = ndr_queue["ndr_reason"].map(REASON_RECOVERY).fillna(0.60)
ndr_queue["age_factor"] = ndr_queue["ndr_age_hours"].apply(age_factor)
ndr_queue["recovery_prob"] = (
    ndr_queue["state_rec"]*0.40 +
    ndr_queue["reason_rec"]*0.35 +
    ndr_queue["age_factor"]*0.25
).clip(0.10, 0.95)

ndr_queue = ndr_queue.sort_values("recovery_prob", ascending=False).reset_index(drop=True)
ndr_queue["priority"] = pd.cut(ndr_queue["recovery_prob"],
    bins=[0,0.50,0.75,1.01], labels=["🟡 Medium","🟢 High","🔥 Urgent"])

high_pri  = ndr_queue[ndr_queue["recovery_prob"] >= 0.75]
rev_at_risk = ndr_queue["order_value"].sum()
exp_recovered = int((ndr_queue["recovery_prob"] * ndr_queue["order_value"]).sum())

st.markdown("""
<div class="header-card">
  <h1 class="header-title">📞 AI Calling Engine</h1>
  <p class="header-subtitle">Not just "use AI calling" — GDI tells you exactly which shipments to call, in priority order.</p>
</div>""", unsafe_allow_html=True)

c1,c2,c3,c4 = st.columns(4)
for col, lbl, val, color in [
    (c1,"NDR Queue",    f"{len(ndr_queue):,}",   "#60A5FA"),
    (c2,"High Priority",f"{len(high_pri):,}",    "#FBBF24"),
    (c3,"Revenue at Risk",f"₹{rev_at_risk:,.0f}","#F87171"),
    (c4,"Expected Recovery",f"₹{exp_recovered:,.0f}","#34D399"),
]:
    col.markdown(f"""<div class="saas-card" style="text-align:center;">
      <div class="metric-label">{lbl}</div>
      <div class="metric-value" style="color:{color};font-size:1.5rem;">{val}</div>
    </div>""", unsafe_allow_html=True)

if len(ndr_queue) == 0:
    st.success("🎉 No NDR shipments in queue. All deliveries are on track."); st.stop()

# Top priority queue
st.markdown("<div class='section-title'>🔥 Priority Calling Queue</div>", unsafe_allow_html=True)

show_cols = ["awb","state","order_value","ndr_reason","attempt_count","ndr_age_hours","recovery_prob","priority"]
avail = [c for c in show_cols if c in ndr_queue.columns]
disp  = ndr_queue[avail].head(50).rename(columns={
    "awb":"AWB","state":"State","order_value":"Order Value (₹)",
    "ndr_reason":"NDR Reason","attempt_count":"Attempts",
    "ndr_age_hours":"Age (hrs)","recovery_prob":"Recovery Prob","priority":"Priority"
})
if "Recovery Prob" in disp.columns:
    disp["Recovery Prob"] = disp["Recovery Prob"].apply(lambda x: f"{x*100:.0f}%")
if "Order Value (₹)" in disp.columns:
    disp["Order Value (₹)"] = disp["Order Value (₹)"].apply(lambda x: f"₹{x:,.0f}")
st.markdown('<div class="saas-card">', unsafe_allow_html=True)
st.dataframe(disp, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)

# Contextual calling script
st.markdown("<div class='section-title'>💬 AI Calling Script Generator</div>", unsafe_allow_html=True)
if len(ndr_queue) > 0:
    top  = ndr_queue.iloc[0]
    reason_script = {
        "Customer Not Available": "We attempted delivery but you were unavailable.",
        "Delivery Requested for Later": "We understand you requested delivery at a later time.",
        "Customer Refused Delivery": "We noticed there was a concern with your delivery.",
        "Wrong / Incomplete Address": "We had trouble locating your delivery address.",
        "Door Locked / Building Issue": "We were unable to access your building for delivery.",
    }.get(str(top.get("ndr_reason","")), "We attempted delivery but were unable to complete it.")

    awb_disp = str(top.get("awb","AWB-XXX"))[:12]
    val_disp = f"₹{int(top.get('order_value',999)):,}"
    state_disp = str(top.get("state","your location"))

    st.markdown(f"""
    <div class="saas-card" style="border:1px solid rgba(79,70,229,0.4);">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">
        <span style="color:#818CF8;font-weight:700;font-size:0.9rem;">📞 SUGGESTED SCRIPT — {awb_disp}</span>
        <span style="color:#9CA3AF;font-size:0.8rem;">Recovery Probability: {top['recovery_prob']*100:.0f}%</span>
      </div>
      <div style="background:#0B0F19;border-radius:8px;padding:16px;font-size:0.93rem;line-height:1.7;color:#D1D5DB;">
        <em style="color:#9CA3AF;">[IVR Opening]</em><br>
        "Hello! This is a message from Velocity Express regarding your order worth <strong>{val_disp}</strong> 
        shipped to <strong>{state_disp}</strong>.<br><br>
        {reason_script}<br><br>
        To reschedule delivery for tomorrow, press <strong>1</strong>.<br>
        To update your delivery address, press <strong>2</strong>.<br>
        To speak with our delivery partner, press <strong>3</strong>.<br>
        To cancel your order, press <strong>4</strong>."<br><br>
        <em style="color:#9CA3AF;">[If no response after 30 sec → attempt WhatsApp follow-up]</em>
      </div>
    </div>""", unsafe_allow_html=True)

# Export
csv_data = ndr_queue[avail].to_csv(index=False).encode("utf-8")
st.download_button("📥 Export Priority Calling List (CSV)", csv_data,
                   "ndr_calling_queue.csv", "text/csv")
