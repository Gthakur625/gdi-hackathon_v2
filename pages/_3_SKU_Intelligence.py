import streamlit as st
import plotly.express as px
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis, compute_sku_perf

st.set_page_config(page_title="SKU Intelligence · GDI", page_icon="📦", layout="wide", initial_sidebar_state="expanded")
apply_styles()
df = render_sidebar_and_get_data()

m       = compute_kpis(df)
sku_df  = compute_sku_perf(df)

st.markdown("""
<div class="header-card">
  <h1 class="header-title">📦 SKU Intelligence</h1>
  <p class="header-subtitle">Which product is hurting your delivery rate? GDI answers in one view.</p>
</div>""", unsafe_allow_html=True)

if sku_df.empty:
    st.warning("No SKU data available."); st.stop()

avg_rto = m["rto_pct"]
sku_df["status"] = sku_df["rto_rate"].apply(
    lambda r: "🔴 Critical" if r > avg_rto*1.5 else ("🟡 Warning" if r > avg_rto else "🟢 OK")
)
sku_df["action"] = sku_df.apply(lambda row: (
    f"Restrict COD in high-risk states for this SKU"
    if row["rto_rate"] > avg_rto*1.5
    else ("Review courier allocation for this SKU" if row["rto_rate"] > avg_rto else "No action needed")
), axis=1)

n_crit = (sku_df["status"]=="🔴 Critical").sum()
n_warn = (sku_df["status"]=="🟡 Warning").sum()
n_ok   = (sku_df["status"]=="🟢 OK").sum()
total_risk = sku_df["revenue_at_risk"].sum()

s1,s2,s3,s4 = st.columns(4)
for col, label, val, color in [
    (s1,"SKUs Analyzed",len(sku_df),"#60A5FA"),
    (s2,"Critical SKUs",int(n_crit),"#F87171"),
    (s3,"Warning SKUs",int(n_warn),"#FBBF24"),
    (s4,"Revenue at Risk",f"₹{total_risk:,.0f}","#FCA5A5"),
]:
    col.markdown(f"""<div class="saas-card" style="text-align:center;">
      <div class="metric-label">{label}</div>
      <div class="metric-value" style="color:{color};font-size:1.6rem;">{val}</div>
    </div>""", unsafe_allow_html=True)

# Critical SKUs
crit_df = sku_df[sku_df["status"]=="🔴 Critical"]
if len(crit_df) > 0:
    st.markdown("<div class='section-title'>🔴 Critical SKUs — Immediate Action Required</div>", unsafe_allow_html=True)
    for _, row in crit_df.iterrows():
        cat = row.get("sku_category","")
        st.markdown(f"""
        <div class="anomaly-critical">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;">
            <div>
              <span style="color:#FCA5A5;font-weight:700;font-size:1rem;">{row['sku']}</span>
              <span style="color:#9CA3AF;font-size:0.85rem;margin-left:8px;">{row['product_name']}</span>
              <span style="background:rgba(239,68,68,0.15);color:#FCA5A5;border:1px solid rgba(239,68,68,0.3);
                           padding:2px 8px;border-radius:99px;font-size:0.72rem;font-weight:600;margin-left:8px;">{cat}</span>
            </div>
            <div style="text-align:right;">
              <span style="color:#F87171;font-size:1.3rem;font-weight:700;">{row['rto_rate']:.0f}% RTO</span>
              <span style="color:#9CA3AF;font-size:0.8rem;margin-left:6px;">vs avg {avg_rto:.0f}%</span>
            </div>
          </div>
          <div style="margin-top:10px;display:flex;gap:24px;">
            <div><span style="color:#9CA3AF;font-size:0.78rem;">Shipments</span><br>
                 <span style="color:#FFFFFF;font-weight:600;">{int(row['total']):,}</span></div>
            <div><span style="color:#9CA3AF;font-size:0.78rem;">Delivery %</span><br>
                 <span style="color:#34D399;font-weight:600;">{row['delivery_rate']:.1f}%</span></div>
            <div><span style="color:#9CA3AF;font-size:0.78rem;">Revenue at Risk</span><br>
                 <span style="color:#FCA5A5;font-weight:600;">₹{row['revenue_at_risk']:,.0f}</span></div>
            <div><span style="color:#9CA3AF;font-size:0.78rem;">Avg Order Value</span><br>
                 <span style="color:#FFFFFF;font-weight:600;">₹{row['avg_value']:,.0f}</span></div>
          </div>
          <div style="margin-top:10px;background:rgba(0,0,0,0.2);border-radius:6px;padding:8px 12px;">
            <span style="color:#EF4444;font-size:0.78rem;font-weight:700;text-transform:uppercase;">Action → </span>
            <span style="color:#FFFFFF;font-size:0.88rem;">{row['action']}</span>
          </div>
        </div>""", unsafe_allow_html=True)

# Scatter plot
st.markdown("<div class='section-title'>📊 Delivery vs Order Value — All SKUs</div>", unsafe_allow_html=True)
color_map = {"🔴 Critical":"#EF4444","🟡 Warning":"#F59E0B","🟢 OK":"#10B981"}
fig = px.scatter(
    sku_df, x="avg_value", y="delivery_rate", size="total",
    color="status", color_discrete_map=color_map,
    hover_data={"sku":True,"product_name":True,"rto_rate":":.1f","total":True},
    labels={"avg_value":"Avg Order Value (₹)","delivery_rate":"Delivery %","status":"Status"},
    size_max=40,
)
fig.update_layout(
    paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
    font_color="#F3F4F6",height=380,margin=dict(l=0,r=0,t=10,b=0),
    xaxis=dict(gridcolor="#1F2937"),yaxis=dict(gridcolor="#1F2937"),
    legend=dict(bgcolor="rgba(0,0,0,0)"),
)
st.markdown('<div class="saas-card">', unsafe_allow_html=True)
st.plotly_chart(fig, use_container_width=True)
st.markdown("</div>", unsafe_allow_html=True)

# Full table
st.markdown("<div class='section-title'>📋 Full SKU Performance Table</div>", unsafe_allow_html=True)
display_cols = ["sku","product_name","total","delivery_rate","rto_rate","revenue_at_risk","status","action"]
display_cols = [c for c in display_cols if c in sku_df.columns]
renamed = {
    "sku":"SKU","product_name":"Product","total":"Shipments",
    "delivery_rate":"Delivery %","rto_rate":"RTO %",
    "revenue_at_risk":"Revenue at Risk","status":"Status","action":"Recommended Action"
}
show_df = sku_df[display_cols].rename(columns=renamed).copy()
if "Delivery %" in show_df.columns:
    show_df["Delivery %"] = show_df["Delivery %"].round(1)
if "RTO %" in show_df.columns:
    show_df["RTO %"] = show_df["RTO %"].round(1)
if "Revenue at Risk" in show_df.columns:
    show_df["Revenue at Risk"] = show_df["Revenue at Risk"].apply(lambda x: f"₹{x:,.0f}")
st.markdown('<div class="saas-card">', unsafe_allow_html=True)
st.dataframe(show_df, use_container_width=True, hide_index=True)
st.markdown("</div>", unsafe_allow_html=True)
