import streamlit as st
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis, compute_state_perf, compute_courier_perf, get_anomalies

st.set_page_config(page_title="Root Cause Analysis · GDI", page_icon="🔍", layout="wide", initial_sidebar_state="expanded")
apply_styles()
df = render_sidebar_and_get_data()

m          = compute_kpis(df)
state_perf = compute_state_perf(df)
cour_perf  = compute_courier_perf(df)
anomalies  = get_anomalies(df, m, state_perf, cour_perf)

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🔍 AI Root Cause Analysis</h1>
  <p class="header-subtitle">GDI scanned your shipments and surfaced exactly what's wrong — no manual digging required.</p>
</div>""", unsafe_allow_html=True)

# Summary chips
n_crit = sum(1 for a in anomalies if a["level"]=="critical")
n_warn = sum(1 for a in anomalies if a["level"]=="warning")
n_info = sum(1 for a in anomalies if a["level"]=="info")

st.markdown(f"""
<div style="display:flex;gap:12px;margin-bottom:20px;flex-wrap:wrap;">
  <div style="background:rgba(239,68,68,0.12);border:1px solid rgba(239,68,68,0.3);
              color:#FCA5A5;padding:6px 16px;border-radius:99px;font-size:0.85rem;font-weight:700;">
    🔴 {n_crit} Critical
  </div>
  <div style="background:rgba(245,158,11,0.12);border:1px solid rgba(245,158,11,0.3);
              color:#FBBF24;padding:6px 16px;border-radius:99px;font-size:0.85rem;font-weight:700;">
    🟡 {n_warn} Warning
  </div>
  <div style="background:rgba(59,130,246,0.12);border:1px solid rgba(59,130,246,0.3);
              color:#93C5FD;padding:6px 16px;border-radius:99px;font-size:0.85rem;font-weight:700;">
    🔵 {n_info} Info
  </div>
  <div style="background:rgba(16,185,129,0.12);border:1px solid rgba(16,185,129,0.3);
              color:#34D399;padding:6px 16px;border-radius:99px;font-size:0.85rem;font-weight:700;">
    📦 {m['total']:,} Shipments Scanned
  </div>
</div>""", unsafe_allow_html=True)

if not anomalies:
    st.success("🎉 No anomalies detected. All systems are within healthy thresholds.")
else:
    level_css = {"critical":"anomaly-critical","warning":"anomaly-warning","info":"anomaly-info"}
    level_colors = {"critical":"#EF4444","warning":"#F59E0B","info":"#3B82F6"}
    for a in anomalies:
        css   = level_css.get(a["level"], "anomaly-info")
        color = level_colors.get(a["level"], "#3B82F6")
        with st.expander(f"{a['icon']}  {a['title']}", expanded=(a["level"]=="critical")):
            st.markdown(f"""
            <div class="{css}" style="margin-bottom:0;">
              <p style="color:#D1D5DB;font-size:0.95rem;line-height:1.6;margin:0 0 10px 0;">{a['detail']}</p>
              <div style="background:rgba(0,0,0,0.2);border-radius:6px;padding:10px 14px;">
                <span style="color:{color};font-weight:700;font-size:0.82rem;text-transform:uppercase;
                             letter-spacing:0.05em;">Recommended Fix</span>
                <p style="color:#FFFFFF;margin:4px 0 0 0;font-size:0.93rem;">{a['fix']}</p>
              </div>
            </div>""", unsafe_allow_html=True)

st.markdown("<div class='section-title' style='margin-top:24px;'>📍 State RTO Heatmap</div>", unsafe_allow_html=True)
c1, c2 = st.columns(2)
with c1:
    if len(state_perf) > 0:
        fig = px.bar(
            state_perf.sort_values("rto_rate", ascending=True).tail(8),
            x="rto_rate", y="state", orientation="h", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#1F2937","#EF4444"],
            labels={"rto_rate":"RTO %","state":"State"},
        )
        fig.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#F3F4F6",height=300,margin=dict(l=0,r=0,t=10,b=0),
                          showlegend=False,coloraxis_showscale=False)
        fig.update_xaxes(showgrid=True,gridcolor="#1F2937")
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;color:#FFFFFF;'>RTO % by State</h4>", unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with c2:
    if len(cour_perf) > 0:
        fig2 = px.bar(
            cour_perf.sort_values("delivery_rate", ascending=True),
            x="delivery_rate", y="courier", orientation="h", text_auto=".1f",
            color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
            labels={"delivery_rate":"Delivery %","courier":"Courier"},
        )
        fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
                           font_color="#F3F4F6",height=300,margin=dict(l=0,r=0,t=10,b=0),
                           showlegend=False,coloraxis_showscale=False)
        fig2.update_xaxes(showgrid=True,gridcolor="#1F2937")
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin-top:0;color:#FFFFFF;'>Delivery % by Courier</h4>", unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# Payment type breakdown
st.markdown("<div class='section-title'>💳 COD vs Prepaid Risk</div>", unsafe_allow_html=True)
p1, p2, p3 = st.columns(3)
cod_df      = df[df["payment_type"]=="COD"]
prepaid_df  = df[df["payment_type"]=="Prepaid"]
cod_rto_pct     = len(cod_df[cod_df["delivery_status"]=="RTO"])     / max(len(cod_df),1)    * 100
prepaid_rto_pct = len(prepaid_df[prepaid_df["delivery_status"]=="RTO"]) / max(len(prepaid_df),1) * 100
with p1:
    st.markdown(f"""<div class="saas-card" style="text-align:center;">
      <div class="metric-label">COD RTO Rate</div>
      <div class="metric-value" style="color:#F87171;">{cod_rto_pct:.1f}%</div>
      <div style="font-size:0.75rem;color:#9CA3AF;">{len(cod_df):,} COD shipments</div>
    </div>""", unsafe_allow_html=True)
with p2:
    st.markdown(f"""<div class="saas-card" style="text-align:center;">
      <div class="metric-label">Prepaid RTO Rate</div>
      <div class="metric-value" style="color:#34D399;">{prepaid_rto_pct:.1f}%</div>
      <div style="font-size:0.75rem;color:#9CA3AF;">{len(prepaid_df):,} Prepaid shipments</div>
    </div>""", unsafe_allow_html=True)
with p3:
    diff = cod_rto_pct - prepaid_rto_pct
    st.markdown(f"""<div class="saas-card" style="text-align:center;border:1px solid rgba(239,68,68,0.3);">
      <div class="metric-label" style="color:#FCA5A5;">COD Premium Risk</div>
      <div class="metric-value" style="color:#FCA5A5;">+{diff:.1f}%</div>
      <div style="font-size:0.75rem;color:#9CA3AF;">extra RTO for COD vs Prepaid</div>
    </div>""", unsafe_allow_html=True)
