import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis, compute_health_score, compute_vas_adoption_score

st.set_page_config(page_title="Seller Health Score · GDI", page_icon="❤️", layout="wide")
apply_styles()
df = render_sidebar_and_get_data()

m = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs = compute_health_score(m)

if hs >= 80:   risk_label="Low Risk";    risk_color="#34D399"; risk_badge='<span class="badge-risk-low">🟢 Low Risk</span>'
elif hs >= 65: risk_label="Medium Risk"; risk_color="#FBBF24"; risk_badge='<span class="badge-risk-medium">🟡 Medium Risk</span>'
else:          risk_label="High Risk";   risk_color="#FCA5A5"; risk_badge='<span class="badge-risk-high">🔴 High Risk</span>'

bench = {"Delivery Rate":85,"RTO Rate":12,"NDR Rate":8,"COD Ratio":50,"VAS Adoption":75}
dims  = {
    "Delivery Rate":   (m["delivery_pct"],  40),
    "RTO Rate":        (100-m["rto_pct"],   25),
    "NDR Rate":        (100-m["ndr_pct"],   20),
    "COD Ratio":       (100-m["cod_pct"],   10),
    "VAS Adoption":    (m["vas_adoption_score"],5),
}

st.markdown("""
<div class="header-card">
  <h1 class="header-title">❤️ Seller Health Score</h1>
  <p class="header-subtitle">Your delivery operations scored — with a plain-language verdict on what to fix first.</p>
</div>""", unsafe_allow_html=True)

col_gauge, col_verdict = st.columns([1,2])

with col_gauge:
    fig = go.Figure(go.Indicator(
        mode="gauge+number",
        value=hs,
        domain={"x":[0,1],"y":[0,1]},
        number={"font":{"size":52,"color":"#FFFFFF","family":"Outfit"},"suffix":"/100"},
        gauge={
            "axis":{"range":[0,100],"tickcolor":"#6B7280","tickfont":{"color":"#9CA3AF"}},
            "bar":{"color":risk_color,"thickness":0.25},
            "bgcolor":"#1F2937",
            "bordercolor":"#374151",
            "steps":[
                {"range":[0,65], "color":"rgba(239,68,68,0.15)"},
                {"range":[65,80],"color":"rgba(245,158,11,0.15)"},
                {"range":[80,100],"color":"rgba(16,185,129,0.15)"},
            ],
            "threshold":{"line":{"color":risk_color,"width":3},"thickness":0.75,"value":hs},
        },
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font={"color":"#FFFFFF","family":"Outfit"},
        height=260, margin=dict(l=20,r=20,t=20,b=0),
    )
    st.markdown('<div class="saas-card" style="text-align:center;">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown(f'<div style="text-align:center;margin-top:-10px;">{risk_badge}</div>', unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with col_verdict:
    if hs >= 80:
        verdict = f"Your operations are healthy. Maintain this level by ensuring ATS allocation stays above 60% and NDR responses are resolved within 24 hours."
    elif hs >= 65:
        verdict_fixes = []
        if m["rto_pct"] > 20:  verdict_fixes.append(f"RTO is {m['rto_pct']:.0f}% — activate Address Verification")
        if m["ndr_pct"] > 15:  verdict_fixes.append(f"NDR is {m['ndr_pct']:.0f}% — launch AI Calling now")
        if m["cod_pct"] > 70:  verdict_fixes.append(f"COD is {m['cod_pct']:.0f}% — add prepaid nudge at checkout")
        verdict = f"Your health is declining. 3 specific fixes can recover 8+ points: {'; '.join(verdict_fixes[:3])}."
    else:
        verdict = f"Critical. Delivery at {m['delivery_pct']:.0f}%, RTO at {m['rto_pct']:.0f}%. Immediate action required on courier allocation and NDR resolution."

    st.markdown(f"""
    <div class="saas-card" style="border-left:4px solid {risk_color};height:100%;">
      <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.06em;">GDI Verdict</div>
      <h2 style="color:#FFFFFF;font-size:1.5rem;font-weight:700;margin:8px 0;">{risk_label} — {hs:.0f}/100</h2>
      <p style="color:#D1D5DB;font-size:0.97rem;line-height:1.6;margin:0;">{verdict}</p>
      <hr/>
      <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;margin-top:12px;">
        <div style="text-align:center;">
          <div class="metric-label">Delivery</div>
          <div class="metric-value" style="color:#34D399;font-size:1.5rem;">{m['delivery_pct']:.1f}%</div>
        </div>
        <div style="text-align:center;">
          <div class="metric-label">RTO</div>
          <div class="metric-value" style="color:#F87171;font-size:1.5rem;">{m['rto_pct']:.1f}%</div>
        </div>
        <div style="text-align:center;">
          <div class="metric-label">NDR</div>
          <div class="metric-value" style="color:#FBBF24;font-size:1.5rem;">{m['ndr_pct']:.1f}%</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

st.markdown("<div class='section-title'>📊 Score Breakdown — 5 Dimensions</div>", unsafe_allow_html=True)

rows = []
for dim, (your_raw, weight) in dims.items():
    your_pts  = round(your_raw * weight / 100, 1)
    bench_raw = bench[dim]
    bench_pts = round(bench_raw * weight / 100, 1)
    delta     = round(your_pts - bench_pts, 1)
    delta_str = f"{'▲' if delta>=0 else '▼'} {abs(delta)}"
    delta_col = "#34D399" if delta >= 0 else "#F87171"
    rows.append({
        "Dimension": dim,
        "Your Score": f"{your_raw:.1f}%  →  {your_pts:.1f}/{weight}",
        "Benchmark":  f"{bench_raw}%  →  {bench_pts:.1f}/{weight}",
        "vs Benchmark": delta_str,
        "_delta_color": delta_col,
        "_delta": delta,
    })

st.markdown('<div class="saas-card">', unsafe_allow_html=True)
for r in rows:
    col1, col2, col3, col4 = st.columns([3,3,3,2])
    with col1: st.markdown(f"<span style='color:#FFFFFF;font-weight:600;'>{r['Dimension']}</span>", unsafe_allow_html=True)
    with col2: st.markdown(f"<span style='color:#D1D5DB;'>{r['Your Score']}</span>", unsafe_allow_html=True)
    with col3: st.markdown(f"<span style='color:#9CA3AF;'>{r['Benchmark']}</span>", unsafe_allow_html=True)
    with col4: st.markdown(f"<span style='color:{r['_delta_color']};font-weight:700;'>{r['vs Benchmark']}</span>", unsafe_allow_html=True)
    st.markdown("<hr style='margin:8px 0;'>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

st.markdown("<div class='section-title'>📅 Weekly Trend (Date-Based Simulation)</div>", unsafe_allow_html=True)
if "shipment_date" in df.columns and len(df) > 0:
    df["week"] = pd.to_datetime(df["shipment_date"]).dt.to_period("W").astype(str)
    weekly = []
    for w, wdf in df.groupby("week"):
        wm = compute_kpis(wdf)
        wm["vas_adoption_score"] = compute_vas_adoption_score(wdf)
        weekly.append({"Week": w, "Health Score": round(compute_health_score(wm),1)})
    if len(weekly) > 1:
        wdf2 = pd.DataFrame(weekly).tail(6)
        import plotly.express as px
        fig2 = px.line(wdf2, x="Week", y="Health Score", markers=True,
                       color_discrete_sequence=["#818CF8"])
        fig2.add_hline(y=80, line_dash="dash", line_color="#34D399",
                       annotation_text="Target 80", annotation_font_color="#34D399")
        fig2.update_layout(
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#F3F4F6", height=220,
            margin=dict(l=0,r=0,t=10,b=0),
            xaxis=dict(showgrid=False), yaxis=dict(range=[0,100], gridcolor="#1F2937"),
        )
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig2, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
