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

# ── chart layout helper ───────────────────────────────────────────────────────
_LAYOUT = dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
               font_color="#F3F4F6", margin=dict(l=0,r=0,t=36,b=0),
               showlegend=False, coloraxis_showscale=False)

# ── HEADER ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="header-card">
  <h1 class="header-title">⚡ Velocity GDI — Growth & Delivery Intelligence</h1>
  <p class="header-subtitle">AI-Powered Seller Operations Consultant · Diagnose. Recommend. Act.</p>
</div>""", unsafe_allow_html=True)

# ── EXECUTIVE SUMMARY ────────────────────────────────────────────────────────
n_issues   = len(anomalies)
issue_word = "anomaly" if n_issues == 1 else "anomalies"
cod_df     = df[df["payment_type"] == "COD"]
prepaid_df = df[df["payment_type"] == "Prepaid"]
cod_rto    = len(cod_df[cod_df["delivery_status"] == "RTO"])    / max(len(cod_df), 1)    * 100
prep_rto   = len(prepaid_df[prepaid_df["delivery_status"] == "RTO"]) / max(len(prepaid_df), 1) * 100

st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(180deg,#161F30 0%,#111827 100%);border-left:4px solid #4F46E5;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
    <div style="flex:1;">
      <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">Executive Overview</div>
      <h2 style="color:#FFFFFF;font-size:1.55rem;font-weight:700;margin:6px 0;">
        Operations: <span style="color:{summary_color};">{risk_level}</span>
        &nbsp;·&nbsp; Health Score: <span style="color:#818CF8;">{hs:.0f}/100</span>
      </h2>
      <p style="color:#D1D5DB;font-size:0.93rem;line-height:1.55;margin:0;max-width:860px;">
        GDI scanned <strong>{m['total']:,} shipments</strong> · detected <strong>{n_issues} {issue_word}</strong>
        · Delivery <strong>{m['delivery_pct']:.1f}%</strong> · RTO <strong>{m['rto_pct']:.1f}%</strong>
        · Activating {len(recs)} recommended VAS can unlock <strong>₹{total_potential:,}</strong>
      </p>
    </div>
    <div style="text-align:right;min-width:170px;">
      <div class="metric-label">Health Score</div>
      <div style="font-size:2.4rem;font-weight:800;color:#818CF8;">{hs:.0f}<span style="font-size:1.1rem;color:#6B7280;">/100</span></div>
      <div style="margin-top:6px;">{risk_badge}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── KPI ROW ───────────────────────────────────────────────────────────────────
sellers_count = df["seller_name"].nunique() if "seller_name" in df.columns else 1
k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
kpis = [
    (k1, "Delivery Rate",   f"{m['delivery_pct']:.1f}%",  "#34D399"),
    (k2, "RTO Rate",        f"{m['rto_pct']:.1f}%",       "#F87171"),
    (k3, "NDR Active",      f"{m['ndr_count']:,}",         "#FBBF24"),
    (k4, "Total Shipments", f"{m['total']:,}",             "#60A5FA"),
    (k5, "Sellers",         f"{sellers_count}",            "#C084FC"),
    (k6, "Couriers",        f"{len(cour_perf)}",           "#818CF8"),
    (k7, "Revenue Unlock",  f"₹{total_potential:,}",       "#34D399"),
]
for col, label, val, color in kpis:
    col.markdown(f"""<div class="saas-card" style="text-align:center;padding:14px;">
      <div class="metric-label">{label}</div>
      <div class="metric-value" style="color:{color};font-size:1.4rem;">{val}</div>
    </div>""", unsafe_allow_html=True)

# ── ANOMALIES ────────────────────────────────────────────────────────────────
if anomalies:
    st.markdown("<div class='section-title'>🔍 GDI Detected Issues</div>", unsafe_allow_html=True)
    level_css = {"critical":"anomaly-critical","warning":"anomaly-warning","info":"anomaly-info"}
    for a in anomalies[:3]:
        css = level_css.get(a["level"], "anomaly-info")
        st.markdown(f"""
        <div class="{css}">
          <strong style="color:#FFFFFF;">{a['icon']} {a['title']}</strong>
          <p style="color:#9CA3AF;margin:6px 0;font-size:0.88rem;">{a['detail']}</p>
          <span style="color:#818CF8;font-size:0.82rem;font-weight:600;">→ {a['fix']}</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── COD vs PREPAID ───────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>💳 COD vs Prepaid Analysis</div>", unsafe_allow_html=True)

cp1, cp2, cp3 = st.columns([1, 1, 1])
with cp1:
    # Donut: share
    fig_donut = go.Figure(go.Pie(
        labels=["COD", "Prepaid"],
        values=[m["cod_count"], m["total"] - m["cod_count"]],
        hole=0.62,
        marker_colors=["#F87171", "#34D399"],
        textinfo="label+percent",
        textfont=dict(color="#F3F4F6", size=12),
    ))
    fig_donut.update_layout(**{**_LAYOUT, "height": 230,
        "annotations": [dict(text=f"<b>{m['cod_pct']:.0f}%</b><br>COD",
                             x=0.5, y=0.5, font_size=15, font_color="#F87171",
                             showarrow=False)]})
    st.markdown('<div class="saas-card"><h4 style="margin:0 0 8px;color:#FFFFFF;">Payment Mix</h4>', unsafe_allow_html=True)
    st.plotly_chart(fig_donut, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with cp2:
    # RTO comparison bars
    fig_cpr = go.Figure()
    fig_cpr.add_trace(go.Bar(name="COD RTO",     x=["COD"],     y=[cod_rto],  marker_color="#F87171", text=[f"{cod_rto:.1f}%"],    textposition="auto"))
    fig_cpr.add_trace(go.Bar(name="Prepaid RTO", x=["Prepaid"], y=[prep_rto], marker_color="#34D399", text=[f"{prep_rto:.1f}%"], textposition="auto"))
    fig_cpr.update_layout(**{**_LAYOUT, "height": 230, "showlegend": True,
        "legend": dict(font_color="#9CA3AF", bgcolor="rgba(0,0,0,0)"),
        "title": dict(text="RTO Rate by Payment Type", font=dict(color="#FFFFFF", size=13)),
        "yaxis": dict(gridcolor="#1F2937")})
    st.markdown('<div class="saas-card">', unsafe_allow_html=True)
    st.plotly_chart(fig_cpr, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)

with cp3:
    diff = cod_rto - prep_rto
    col_diff = "#F87171" if diff > 5 else "#FBBF24"
    ndr_cod = df[(df["payment_type"]=="COD") & (df["ndr_status"]=="Raised")] if "ndr_status" in df.columns else pd.DataFrame()
    st.markdown(f"""
    <div class="saas-card" style="height:260px;">
      <h4 style="margin:0 0 14px;color:#FFFFFF;">COD Risk Summary</h4>
      <div style="margin-bottom:14px;">
        <div class="metric-label">COD Shipments</div>
        <div style="font-size:1.5rem;font-weight:700;color:#F87171;">{m['cod_count']:,}</div>
      </div>
      <div style="margin-bottom:14px;">
        <div class="metric-label">COD vs Prepaid RTO Premium</div>
        <div style="font-size:1.5rem;font-weight:700;color:{col_diff};">+{diff:.1f}%</div>
      </div>
      <div>
        <div class="metric-label">COD NDR Active</div>
        <div style="font-size:1.5rem;font-weight:700;color:#FBBF24;">{len(ndr_cod):,}</div>
      </div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── 3PL PERFORMANCE SCORECARD ─────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🚚 3PL Courier Performance Scorecard</div>", unsafe_allow_html=True)

sc1, sc2 = st.columns([3, 2])
with sc1:
    st.markdown('<div class="saas-card" style="padding:18px;">', unsafe_allow_html=True)
    st.markdown("<h4 style='margin:0 0 14px;color:#FFFFFF;'>Delivery Rate by Courier</h4>", unsafe_allow_html=True)
    for _, row in cour_perf.sort_values("delivery_rate", ascending=False).iterrows():
        rate   = row["delivery_rate"]
        bar_w  = max(2, int(rate))
        color  = "#34D399" if rate >= 80 else ("#FBBF24" if rate >= 70 else "#EF4444")
        emoji  = "✅" if rate >= 80 else ("⚠️" if rate >= 70 else "🚨")
        st.markdown(f"""
        <div class="score-row">
          <div class="score-name">{emoji} {row['courier']}</div>
          <div class="score-vol">{row['total']:,} shpts</div>
          <div class="score-bar-wrap">
            <div class="score-bar-fill" style="width:{bar_w}%;background:{color};"></div>
          </div>
          <div class="score-pct" style="color:{color};">{rate:.1f}%</div>
          <div style="flex:1;text-align:right;color:#F87171;font-size:0.8rem;">RTO {row['rto_rate']:.1f}%</div>
        </div>""", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

with sc2:
    if len(cour_perf) > 0:
        fig_3pl = px.bar(
            cour_perf.sort_values("rto_rate", ascending=False),
            x="courier", y="rto_rate", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
            labels={"courier":"","rto_rate":"RTO %"},
            title="RTO % by Courier"
        )
        fig_3pl.update_layout(**{**_LAYOUT, "height": 280,
            "title": dict(text="RTO % by Courier", font=dict(color="#FFFFFF", size=13)),
            "yaxis": dict(gridcolor="#1F2937"), "xaxis": dict(tickangle=-20)})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_3pl, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── TOP SELLERS ──────────────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if "seller_name" in df.columns and df["seller_name"].nunique() > 1:
    st.markdown("<div class='section-title'>🏆 Top Sellers Performance</div>", unsafe_allow_html=True)
    seller_g = df.groupby("seller_name").agg(
        total     =("delivery_status","count"),
        delivered =("delivery_status", lambda x: (x=="Delivered").sum()),
        rto       =("delivery_status", lambda x: (x=="RTO").sum()),
        revenue   =("order_value","sum"),
        cod       =("payment_type",    lambda x: (x=="COD").sum()),
    ).reset_index()
    seller_g["delivery_rate"] = seller_g["delivered"] / seller_g["total"] * 100
    seller_g["rto_rate"]      = seller_g["rto"]       / seller_g["total"] * 100
    seller_g["cod_pct"]       = seller_g["cod"]        / seller_g["total"] * 100
    seller_g = seller_g.sort_values("delivery_rate", ascending=False)

    ts1, ts2 = st.columns([2, 1])
    with ts1:
        fig_sellers = px.bar(
            seller_g, x="delivery_rate", y="seller_name", orientation="h",
            text_auto=".1f", color="delivery_rate",
            color_continuous_scale=["#EF4444","#10B981"],
            labels={"delivery_rate":"Delivery %","seller_name":"Seller"},
            title="Seller Delivery Rate (%)"
        )
        fig_sellers.update_layout(**{**_LAYOUT, "height": max(220, len(seller_g)*48),
            "title": dict(text="Seller Delivery Rate (%)", font=dict(color="#FFFFFF", size=13)),
            "yaxis": dict(autorange="reversed"), "xaxis": dict(gridcolor="#1F2937")})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_sellers, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with ts2:
        st.markdown('<div class="saas-card" style="padding:16px;">', unsafe_allow_html=True)
        st.markdown("<h4 style='margin:0 0 12px;color:#FFFFFF;'>Seller Scoreboard</h4>", unsafe_allow_html=True)
        for _, row in seller_g.iterrows():
            e = "🥇" if _ == 0 else ("🥈" if _ == 1 else ("🥉" if _ == 2 else "  "))
            c = "#34D399" if row["delivery_rate"]>=80 else ("#FBBF24" if row["delivery_rate"]>=65 else "#F87171")
            st.markdown(f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:8px 0;border-bottom:1px solid #1F2937;">
              <div style="color:#FFFFFF;font-size:0.85rem;">{e} {row['seller_name']}</div>
              <div style="color:{c};font-weight:700;font-size:0.88rem;">{row['delivery_rate']:.1f}%</div>
            </div>""", unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── TOP PRODUCTS + PRICING BAND ──────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if "product_name" in df.columns:
    st.markdown("<div class='section-title'>📦 Top Products & Pricing Band Analysis</div>", unsafe_allow_html=True)
    tp1, tp2 = st.columns(2)

    with tp1:
        prod_g = df.groupby("product_name").agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto      =("delivery_status", lambda x: (x=="RTO").sum()),
            revenue  =("order_value","sum"),
        ).reset_index()
        prod_g["delivery_rate"] = prod_g["delivered"] / prod_g["total"] * 100
        prod_g["rto_rate"]      = prod_g["rto"]       / prod_g["total"] * 100
        top10 = prod_g.sort_values("delivered", ascending=False).head(10)

        fig_top = px.bar(
            top10, x="product_name", y="delivered",
            color="delivery_rate", color_continuous_scale=["#4F46E5","#34D399"],
            text_auto=True, labels={"product_name":"","delivered":"Delivered Units"},
            title="Top 10 Products — Delivered Units"
        )
        fig_top.update_layout(**{**_LAYOUT, "height": 300,
            "title": dict(text="Top 10 Products — Delivered Units", font=dict(color="#FFFFFF",size=13)),
            "xaxis": dict(tickangle=-30), "yaxis": dict(gridcolor="#1F2937"),
            "coloraxis_showscale": False})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_top, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

    with tp2:
        # Pricing Band Analysis
        bins   = [0, 499, 999, 1999, 4999, float("inf")]
        labels = ["₹0–499","₹500–999","₹1K–2K","₹2K–5K","₹5K+"]
        df_pb  = df.copy()
        df_pb["price_band"] = pd.cut(df_pb["order_value"], bins=bins, labels=labels, right=True)
        pb_g = df_pb.groupby("price_band", observed=True).agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto      =("delivery_status", lambda x: (x=="RTO").sum()),
        ).reset_index()
        pb_g["delivery_rate"] = pb_g["delivered"] / pb_g["total"].clip(lower=1) * 100
        pb_g["rto_rate"]      = pb_g["rto"]       / pb_g["total"].clip(lower=1) * 100

        fig_pb = go.Figure()
        fig_pb.add_trace(go.Bar(
            x=pb_g["price_band"].astype(str), y=pb_g["delivery_rate"],
            name="Delivery %", marker_color="#34D399",
            text=[f"{v:.0f}%" for v in pb_g["delivery_rate"]], textposition="auto",
        ))
        fig_pb.add_trace(go.Bar(
            x=pb_g["price_band"].astype(str), y=pb_g["rto_rate"],
            name="RTO %", marker_color="#F87171",
            text=[f"{v:.0f}%" for v in pb_g["rto_rate"]], textposition="auto",
        ))
        fig_pb.update_layout(**{**_LAYOUT, "height": 300, "showlegend": True,
            "legend": dict(font_color="#9CA3AF", bgcolor="rgba(0,0,0,0)",
                           orientation="h", yanchor="bottom", y=1.02),
            "title": dict(text="Delivery & RTO % by Price Band", font=dict(color="#FFFFFF",size=13)),
            "xaxis": dict(title="Price Band"), "yaxis": dict(gridcolor="#1F2937"),
            "barmode": "group"})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_pb, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── COURIER × STATE HEATMAP ───────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🗺️ Geographic RTO Intelligence</div>", unsafe_allow_html=True)
geo1, geo2 = st.columns(2)

with geo1:
    if len(state_perf) > 0:
        worst5 = state_perf.sort_values("rto_rate", ascending=False).head(8)
        fig_s = px.bar(
            worst5.sort_values("rto_rate"),
            x="rto_rate", y="state", orientation="h", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#F59E0B","#EF4444"],
            labels={"rto_rate":"RTO %","state":"State"}, title="Worst States by RTO %"
        )
        fig_s.update_layout(**{**_LAYOUT, "height": 280,
            "title": dict(text="Worst States by RTO %", font=dict(color="#FFFFFF",size=13)),
            "yaxis": dict(autorange="reversed"), "xaxis": dict(gridcolor="#1F2937")})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_s, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

with geo2:
    # State × COD RTO breakdown
    if "payment_type" in df.columns and "state" in df.columns:
        st_cod = df[df["payment_type"]=="COD"].groupby("state").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x: (x=="RTO").sum()),
        ).reset_index()
        st_cod["cod_rto_rate"] = st_cod["rto"] / st_cod["total"].clip(lower=1) * 100
        top_cod = st_cod.sort_values("cod_rto_rate", ascending=False).head(8)
        fig_c = px.bar(
            top_cod.sort_values("cod_rto_rate"),
            x="cod_rto_rate", y="state", orientation="h", text_auto=".1f",
            color="cod_rto_rate", color_continuous_scale=["#FBBF24","#EF4444"],
            labels={"cod_rto_rate":"COD RTO %","state":"State"}, title="Worst States — COD RTO %"
        )
        fig_c.update_layout(**{**_LAYOUT, "height": 280,
            "title": dict(text="Worst States — COD RTO %", font=dict(color="#FFFFFF",size=13)),
            "yaxis": dict(autorange="reversed"), "xaxis": dict(gridcolor="#1F2937")})
        st.markdown('<div class="saas-card">', unsafe_allow_html=True)
        st.plotly_chart(fig_c, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ── VAS RECOMMENDATIONS ───────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
if recs:
    st.markdown("<div class='section-title'>💡 GDI Recommended Actions — Ranked by Revenue Impact</div>", unsafe_allow_html=True)
    rec_cols = st.columns(min(len(recs), 4))
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

# ══════════════════════════════════════════════════════════════════════════════
# ── ASK GDI AGENT BANNER ─────────────────────────────────────────────────────
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🤖 Ask GDI Agent</div>", unsafe_allow_html=True)
st.markdown("""
<div class="saas-card" style="background:linear-gradient(135deg,rgba(79,70,229,0.2) 0%,rgba(124,58,237,0.15) 100%);
     border:1px solid rgba(79,70,229,0.35);text-align:center;padding:32px;">
  <div style="font-size:2.5rem;margin-bottom:8px;">🤖</div>
  <h3 style="color:#FFFFFF;font-size:1.3rem;font-weight:700;margin:0 0 8px;">Ask GDI Agent Anything</h3>
  <p style="color:#9CA3AF;font-size:0.9rem;max-width:560px;margin:0 auto 18px;">
    Which seller has highest RTO? · Top selling products? · Will AI Calling help?
    · Which courier is best? · Why is RTO high? · COD vs Prepaid breakdown?
  </p>
  <div style="display:flex;justify-content:center;gap:10px;flex-wrap:wrap;">
    <span style="background:rgba(129,140,248,0.15);color:#818CF8;border:1px solid rgba(129,140,248,0.3);
                 padding:5px 14px;border-radius:99px;font-size:0.8rem;font-weight:600;">Compare all sellers</span>
    <span style="background:rgba(52,211,153,0.15);color:#34D399;border:1px solid rgba(52,211,153,0.3);
                 padding:5px 14px;border-radius:99px;font-size:0.8rem;font-weight:600;">Top selling products</span>
    <span style="background:rgba(248,113,113,0.15);color:#F87171;border:1px solid rgba(248,113,113,0.3);
                 padding:5px 14px;border-radius:99px;font-size:0.8rem;font-weight:600;">Why is RTO high?</span>
    <span style="background:rgba(251,191,36,0.15);color:#FBBF24;border:1px solid rgba(251,191,36,0.3);
                 padding:5px 14px;border-radius:99px;font-size:0.8rem;font-weight:600;">Will AI Calling help?</span>
  </div>
</div>""", unsafe_allow_html=True)

col_btn = st.columns([1, 2, 1])[1]
with col_btn:
    st.page_link("pages/7_AI_Chat_Assistant.py",
                 label="Open Ask GDI Agent →",
                 icon="🤖",
                 use_container_width=True)

# ── MODULE GUIDE ─────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🧭 GDI Module Guide</div>", unsafe_allow_html=True)
nav_items = [
    ("❤️","Seller Health Score","Overall delivery health score with benchmarks"),
    ("🔍","Root Cause Analysis","Auto-detected anomalies — why delivery is failing"),
    ("📦","SKU Intelligence","Which product is underperforming and why"),
    ("🚀","ATS Recommendations","Ranked VAS mapped to your exact problems"),
    ("📞","AI Calling Engine","AI Calling & Order Confirmation priority queue"),
    ("💬","WhatsApp AI NDR","COD NDR funnel via WhatsApp AI engagement"),
    ("🤖","Ask GDI Agent","Chat: ask about any seller, product, courier or VAS"),
    ("📊","Impact Simulator","Model revenue impact of each VAS activation"),
]
nc = st.columns(4)
for i, (icon, title, desc) in enumerate(nav_items):
    nc[i % 4].markdown(f"""
    <div class="saas-card" style="text-align:center;padding:16px;">
      <div style="font-size:1.8rem;">{icon}</div>
      <div style="color:#FFFFFF;font-weight:700;margin:6px 0 4px;font-size:0.9rem;">{title}</div>
      <div style="color:#9CA3AF;font-size:0.75rem;">{desc}</div>
    </div>""", unsafe_allow_html=True)
