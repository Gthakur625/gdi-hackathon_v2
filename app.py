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
    page_icon="⚡", layout="wide",
    initial_sidebar_state="expanded",
)
apply_styles()
df = render_sidebar_and_get_data()

m            = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs           = compute_health_score(m)
recs         = get_recommendations(m)
state_perf   = compute_state_perf(df)
cour_perf    = compute_courier_perf(df)
anomalies    = get_anomalies(df, m, state_perf, cour_perf)

cod_df    = df[df["payment_type"] == "COD"]
prepaid_df= df[df["payment_type"] == "Prepaid"]
cod_rto   = len(cod_df[cod_df["delivery_status"]=="RTO"])       / max(len(cod_df),1)    * 100
prep_rto  = len(prepaid_df[prepaid_df["delivery_status"]=="RTO"]) / max(len(prepaid_df),1) * 100
ndr_cod   = df[(df["payment_type"]=="COD") & (df["ndr_status"]=="Raised")] \
            if "ndr_status" in df.columns else pd.DataFrame()

if hs >= 80:   risk_level="Low Risk";    sc="#34D399"; rb='<span class="badge-risk-low">🟢 Low Risk</span>'
elif hs >= 65: risk_level="Medium Risk"; sc="#FBBF24"; rb='<span class="badge-risk-medium">🟡 Medium Risk</span>'
else:          risk_level="High Risk";   sc="#FCA5A5"; rb='<span class="badge-risk-high">🔴 High Risk</span>'
total_potential = sum(r["revenue"] for r in recs)

# ── shared chart style ────────────────────────────────────────────────────────
def _fig(height=280):
    return dict(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                font_color="#F3F4F6", height=height,
                margin=dict(l=0,r=0,t=40,b=0),
                showlegend=False, coloraxis_showscale=False)

def _card(label, value, color, sub=""):
    return (f'<div class="saas-card" style="text-align:center;padding:16px 10px;">'
            f'<div class="metric-label">{label}</div>'
            f'<div class="metric-value" style="color:{color};font-size:1.5rem;">{value}</div>'
            f'{"<div style=color:#9CA3AF;font-size:0.75rem;margin-top:2px;>" + sub + "</div>" if sub else ""}'
            f'</div>')

# ══════════════════════════════════════════════════════════════════════════════
# HEADER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("""
<div class="header-card">
  <h1 class="header-title">⚡ Velocity GDI — Growth & Delivery Intelligence</h1>
  <p class="header-subtitle">AI-Powered Operations Consultant · Diagnose · Recommend · Act</p>
</div>""", unsafe_allow_html=True)

# ── Executive Summary ─────────────────────────────────────────────────────────
sellers_count = df["seller_name"].nunique() if "seller_name" in df.columns else 1
n_issues = len(anomalies)
st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(180deg,#161F30 0%,#111827 100%);
     border-left:4px solid #4F46E5;">
  <div style="display:flex;justify-content:space-between;align-items:center;
              flex-wrap:wrap;gap:16px;">
    <div style="flex:1;">
      <div style="color:#9CA3AF;font-size:0.78rem;text-transform:uppercase;
                  letter-spacing:0.05em;">Executive Overview</div>
      <h2 style="color:#FFFFFF;font-size:1.45rem;font-weight:700;margin:6px 0;">
        Status: <span style="color:{sc};">{risk_level}</span>
        &nbsp;·&nbsp; Health Score: <span style="color:#818CF8;">{hs:.0f}/100</span>
      </h2>
      <p style="color:#D1D5DB;font-size:0.9rem;line-height:1.6;margin:0;max-width:820px;">
        Scanned <strong>{m['total']:,} shipments</strong> across
        <strong>{sellers_count} sellers</strong> &amp; <strong>{len(cour_perf)} couriers</strong>.
        Detected <strong>{n_issues} issue{"s" if n_issues!=1 else ""}</strong>.
        Delivery <strong>{m['delivery_pct']:.1f}%</strong> · RTO <strong>{m['rto_pct']:.1f}%</strong>
        · NDR <strong>{m['ndr_count']:,}</strong>.
        Activating recommended VAS unlocks <strong>₹{total_potential:,}</strong>.
      </p>
    </div>
    <div style="text-align:center;min-width:150px;">
      <div class="metric-label">Health Score</div>
      <div style="font-size:2.6rem;font-weight:800;color:#818CF8;line-height:1;">
        {hs:.0f}<span style="font-size:1rem;color:#6B7280;">/100</span></div>
      <div style="margin-top:8px;">{rb}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# ── KPI Row ───────────────────────────────────────────────────────────────────
k1,k2,k3,k4,k5,k6,k7 = st.columns(7)
for col, lbl, val, clr, sub in [
    (k1,"Delivery Rate",   f"{m['delivery_pct']:.1f}%", "#34D399", f"{m['delivered']:,} delivered"),
    (k2,"RTO Rate",        f"{m['rto_pct']:.1f}%",      "#F87171", f"{m['rto_count']:,} returned"),
    (k3,"NDR Active",      f"{m['ndr_count']:,}",        "#FBBF24", "needs resolution"),
    (k4,"Total Shipments", f"{m['total']:,}",            "#60A5FA", "in current view"),
    (k5,"Sellers",         f"{sellers_count}",           "#C084FC", "active accounts"),
    (k6,"Couriers (3PL)",  f"{len(cour_perf)}",          "#818CF8", "partners active"),
    (k7,"Revenue Unlock",  f"₹{total_potential:,}",      "#34D399", "via VAS activation"),
]:
    col.markdown(_card(lbl, val, clr, sub), unsafe_allow_html=True)

# ── Anomalies ─────────────────────────────────────────────────────────────────
if anomalies:
    st.markdown("<div class='section-title'>🔍 GDI Detected Issues</div>",
                unsafe_allow_html=True)
    lvl = {"critical":"anomaly-critical","warning":"anomaly-warning","info":"anomaly-info"}
    for a in anomalies[:3]:
        st.markdown(f"""
        <div class="{lvl.get(a['level'],'anomaly-info')}">
          <strong style="color:#FFFFFF;">{a['icon']} {a['title']}</strong>
          <p style="color:#9CA3AF;margin:6px 0;font-size:0.88rem;">{a['detail']}</p>
          <span style="color:#818CF8;font-size:0.82rem;font-weight:600;">→ {a['fix']}</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# COD vs PREPAID
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>💳 COD vs Prepaid Analysis</div>",
            unsafe_allow_html=True)
st.markdown("""
<p style="color:#9CA3AF;font-size:0.85rem;margin:-8px 0 14px 0;">
  COD orders carry higher RTO risk. Use this to decide where to activate
  <strong>WhatsApp AI NDR</strong> and <strong>Order Confirmation Via AI</strong>.
</p>""", unsafe_allow_html=True)

# Row 1 – 4 stat cards
c1,c2,c3,c4 = st.columns(4)
diff = cod_rto - prep_rto
c1.markdown(_card("COD Shipments",    f"{m['cod_count']:,}",          "#F87171", f"{m['cod_pct']:.1f}% of total"), unsafe_allow_html=True)
c2.markdown(_card("Prepaid Shipments",f"{m['total']-m['cod_count']:,}","#34D399", f"{100-m['cod_pct']:.1f}% of total"), unsafe_allow_html=True)
c3.markdown(_card("COD RTO Rate",     f"{cod_rto:.1f}%",             "#F87171", f"+{diff:.1f}% vs Prepaid"), unsafe_allow_html=True)
c4.markdown(_card("Prepaid RTO Rate", f"{prep_rto:.1f}%",            "#34D399", "lower risk payment"), unsafe_allow_html=True)

# Row 2 – donut + bar + insight
cp1, cp2, cp3 = st.columns([1.2, 1.5, 1.3])

with cp1:
    fig_donut = go.Figure(go.Pie(
        labels=["COD","Prepaid"],
        values=[m["cod_count"], m["total"]-m["cod_count"]],
        hole=0.60,
        marker_colors=["#F87171","#34D399"],
        textinfo="label+percent",
        textfont=dict(color="#F3F4F6", size=11),
        hovertemplate="%{label}: %{value:,} shipments<extra></extra>",
    ))
    fig_donut.update_layout(**{**_fig(240), "showlegend": False,
        "annotations":[dict(text=f"<b>{m['cod_pct']:.0f}%</b><br><span style='font-size:11px'>COD</span>",
                            x=0.5,y=0.5,font_size=16,font_color="#F87171",showarrow=False)]})
    st.markdown("<p style='color:#9CA3AF;font-size:0.78rem;font-weight:600;margin:0 0 4px;'>"
                "PAYMENT MIX</p>", unsafe_allow_html=True)
    st.plotly_chart(fig_donut, use_container_width=True)

with cp2:
    fig_cmp = go.Figure()
    fig_cmp.add_trace(go.Bar(
        name="Delivery %",
        x=["COD","Prepaid"],
        y=[100-cod_rto, 100-prep_rto],
        marker_color=["#F87171","#34D399"],
        text=[f"{100-cod_rto:.1f}%", f"{100-prep_rto:.1f}%"],
        textposition="auto", width=0.4,
    ))
    fig_cmp.add_trace(go.Bar(
        name="RTO %",
        x=["COD","Prepaid"],
        y=[cod_rto, prep_rto],
        marker_color=["rgba(248,113,113,0.4)","rgba(52,211,153,0.4)"],
        text=[f"{cod_rto:.1f}%",f"{prep_rto:.1f}%"],
        textposition="auto", width=0.4,
    ))
    fig_cmp.update_layout(**{**_fig(240), "showlegend": True, "barmode":"group",
        "legend": dict(font_color="#9CA3AF",bgcolor="rgba(0,0,0,0)",
                       orientation="h",y=1.15,x=0),
        "yaxis": dict(gridcolor="#1F2937",ticksuffix="%"),
        "xaxis": dict(showgrid=False)})
    st.markdown("<p style='color:#9CA3AF;font-size:0.78rem;font-weight:600;margin:0 0 4px;'>"
                "DELIVERY & RTO RATE BY PAYMENT TYPE</p>", unsafe_allow_html=True)
    st.plotly_chart(fig_cmp, use_container_width=True)

with cp3:
    color_diff = "#F87171" if diff > 8 else ("#FBBF24" if diff > 4 else "#34D399")
    insight = ("🚨 COD RTO is significantly higher. Activate **WhatsApp AI NDR** + **Order Confirmation Via AI** immediately."
               if diff > 8 else
               ("⚠️ Moderate COD risk. WhatsApp AI NDR will protect your COD deliveries."
                if diff > 4 else "✅ COD risk is manageable. Continue monitoring."))
    st.markdown(f"""
    <div class="saas-card" style="padding:20px;">
      <div style="color:#9CA3AF;font-size:0.78rem;font-weight:600;text-transform:uppercase;
                  letter-spacing:0.05em;margin-bottom:12px;">COD RISK INSIGHT</div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  border-bottom:1px solid #1F2937;padding-bottom:12px;margin-bottom:12px;">
        <span style="color:#9CA3AF;font-size:0.82rem;">COD Premium (extra RTO vs Prepaid)</span>
        <span style="color:{color_diff};font-weight:800;font-size:1.3rem;">+{diff:.1f}%</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  border-bottom:1px solid #1F2937;padding-bottom:12px;margin-bottom:12px;">
        <span style="color:#9CA3AF;font-size:0.82rem;">COD NDR Active</span>
        <span style="color:#FBBF24;font-weight:700;font-size:1.1rem;">{len(ndr_cod):,}</span>
      </div>
      <div style="display:flex;justify-content:space-between;align-items:center;
                  margin-bottom:14px;">
        <span style="color:#9CA3AF;font-size:0.82rem;">Revenue at Risk (COD RTOs)</span>
        <span style="color:#F87171;font-weight:700;font-size:1.1rem;">
          ₹{int(m['rto_count']*m['avg_order_value']):,}</span>
      </div>
      <div style="background:#0B0F19;border-radius:8px;padding:12px;
                  font-size:0.82rem;color:#D1D5DB;line-height:1.5;">{insight}</div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# 3PL COURIER PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🚚 3PL Courier Performance</div>",
            unsafe_allow_html=True)
st.markdown("""
<p style="color:#9CA3AF;font-size:0.85rem;margin:-8px 0 14px 0;">
  Compare all courier partners on delivery rate and RTO.
  Route more volume to top performers — each 1% delivery improvement saves
  significant revenue.
</p>""", unsafe_allow_html=True)

pl1, pl2 = st.columns(2)
with pl1:
    fig_del = px.bar(
        cour_perf.sort_values("delivery_rate"),
        x="delivery_rate", y="courier", orientation="h",
        text_auto=".1f",
        color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
        labels={"delivery_rate":"Delivery %","courier":""},
    )
    fig_del.update_layout(**_fig(max(260, len(cour_perf)*46)),
        title=dict(text="Delivery Rate % by Courier", font=dict(color="#FFFFFF",size=13)),
        xaxis=dict(gridcolor="#1F2937", ticksuffix="%"),
        yaxis=dict(showgrid=False))
    st.plotly_chart(fig_del, use_container_width=True)

with pl2:
    fig_rto = px.bar(
        cour_perf.sort_values("rto_rate", ascending=False),
        x="rto_rate", y="courier", orientation="h",
        text_auto=".1f",
        color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
        labels={"rto_rate":"RTO %","courier":""},
    )
    fig_rto.update_layout(**_fig(max(260, len(cour_perf)*46)),
        title=dict(text="RTO Rate % by Courier", font=dict(color="#FFFFFF",size=13)),
        xaxis=dict(gridcolor="#1F2937", ticksuffix="%"),
        yaxis=dict(showgrid=False))
    st.plotly_chart(fig_rto, use_container_width=True)

# Courier summary metrics
if len(cour_perf) > 0:
    best = cour_perf.sort_values("delivery_rate", ascending=False).iloc[0]
    worst= cour_perf.sort_values("delivery_rate").iloc[0]
    gap  = best["delivery_rate"] - worst["delivery_rate"]
    m1,m2,m3,m4 = st.columns(4)
    m1.markdown(_card("Best Courier",    best["courier"],             "#34D399", f"{best['delivery_rate']:.1f}% delivery"), unsafe_allow_html=True)
    m2.markdown(_card("Needs Attention", worst["courier"],            "#F87171", f"{worst['delivery_rate']:.1f}% delivery"), unsafe_allow_html=True)
    m3.markdown(_card("Performance Gap", f"{gap:.1f}%",              "#FBBF24", "between best & worst"), unsafe_allow_html=True)
    m4.markdown(_card("Total Couriers",  str(len(cour_perf)),        "#818CF8", "active 3PL partners"), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TOP SELLERS
# ══════════════════════════════════════════════════════════════════════════════
if "seller_name" in df.columns and sellers_count > 1:
    st.markdown("<div class='section-title'>🏆 Seller Performance</div>",
                unsafe_allow_html=True)
    st.markdown("""
    <p style="color:#9CA3AF;font-size:0.85rem;margin:-8px 0 14px 0;">
      Identify which sellers need VAS activation and which are performing well.
    </p>""", unsafe_allow_html=True)

    sg = df.groupby("seller_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        revenue  =("order_value","sum"),
        cod      =("payment_type",    lambda x:(x=="COD").sum()),
    ).reset_index()
    sg["delivery_rate"] = sg["delivered"]/sg["total"]*100
    sg["rto_rate"]      = sg["rto"]/sg["total"]*100
    sg["cod_pct"]       = sg["cod"]/sg["total"]*100
    sg = sg.sort_values("delivery_rate", ascending=False).reset_index(drop=True)

    sl1, sl2 = st.columns([3, 2])
    with sl1:
        fig_sl = px.bar(
            sg.sort_values("delivery_rate"),
            x="delivery_rate", y="seller_name", orientation="h",
            text_auto=".1f", color="delivery_rate",
            color_continuous_scale=["#EF4444","#10B981"],
            labels={"delivery_rate":"Delivery %","seller_name":""},
        )
        fig_sl.update_layout(**_fig(max(260, len(sg)*52)),
            title=dict(text="Seller Delivery Rate %", font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937", ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_sl, use_container_width=True)

    with sl2:
        rows_html = ""
        for i, row in sg.iterrows():
            medal = ["🥇","🥈","🥉"][i] if i < 3 else f"{i+1}."
            c_dr = "#34D399" if row["delivery_rate"]>=80 else ("#FBBF24" if row["delivery_rate"]>=65 else "#F87171")
            rows_html += f"""
            <div style="display:flex;justify-content:space-between;align-items:center;
                        padding:10px 4px;border-bottom:1px solid #1F2937;">
              <div style="color:#FFFFFF;font-size:0.85rem;">{medal} {row['seller_name']}</div>
              <div style="display:flex;gap:14px;align-items:center;">
                <span style="color:{c_dr};font-weight:700;font-size:0.9rem;">{row['delivery_rate']:.1f}%</span>
                <span style="color:#F87171;font-size:0.78rem;">RTO {row['rto_rate']:.1f}%</span>
              </div>
            </div>"""
        st.markdown(f'<div class="saas-card" style="padding:16px;">'
                    f'<div style="color:#9CA3AF;font-size:0.78rem;font-weight:600;'
                    f'text-transform:uppercase;margin-bottom:8px;">SELLER SCOREBOARD</div>'
                    f'{rows_html}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TOP PRODUCTS + PRICING BAND
# ══════════════════════════════════════════════════════════════════════════════
if "product_name" in df.columns:
    st.markdown("<div class='section-title'>📦 Top Products & Pricing Band Analysis</div>",
                unsafe_allow_html=True)
    st.markdown("""
    <p style="color:#9CA3AF;font-size:0.85rem;margin:-8px 0 14px 0;">
      Top products by volume and RTO by price range — helps decide where to restrict COD
      and which price bands need Order Confirmation Via AI.
    </p>""", unsafe_allow_html=True)

    prod_g = df.groupby("product_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        revenue  =("order_value","sum"),
    ).reset_index()
    prod_g["rto_rate"]      = prod_g["rto"]/prod_g["total"].clip(lower=1)*100
    prod_g["delivery_rate"] = prod_g["delivered"]/prod_g["total"].clip(lower=1)*100
    top10 = prod_g.sort_values("delivered", ascending=False).head(10)

    tp1, tp2 = st.columns(2)
    with tp1:
        fig_prod = px.bar(
            top10, x="product_name", y="delivered",
            color="delivery_rate",
            color_continuous_scale=["#4F46E5","#34D399"],
            text_auto=True,
            labels={"product_name":"","delivered":"Delivered Units","delivery_rate":"Delivery %"},
        )
        fig_prod.update_layout(**_fig(300),
            title=dict(text="Top 10 Products — Delivered Units", font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(tickangle=-30, showgrid=False),
            yaxis=dict(gridcolor="#1F2937"))
        st.plotly_chart(fig_prod, use_container_width=True)

    with tp2:
        # Pricing Band
        bins   = [0, 499, 999, 1999, 4999, float("inf")]
        blbls  = ["₹0–499","₹500–999","₹1K–2K","₹2K–5K","₹5K+"]
        df_pb  = df.copy()
        df_pb["price_band"] = pd.cut(df_pb["order_value"], bins=bins, labels=blbls, right=True)
        pb_g = df_pb.groupby("price_band", observed=True).agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        pb_g["del_rate"] = pb_g["delivered"]/pb_g["total"].clip(lower=1)*100
        pb_g["rto_rate"] = pb_g["rto"]/pb_g["total"].clip(lower=1)*100
        pb_g["band_str"] = pb_g["price_band"].astype(str)

        fig_pb = go.Figure()
        fig_pb.add_trace(go.Bar(
            x=pb_g["band_str"], y=pb_g["del_rate"], name="Delivery %",
            marker_color="#34D399", text=[f"{v:.0f}%" for v in pb_g["del_rate"]],
            textposition="auto",
        ))
        fig_pb.add_trace(go.Bar(
            x=pb_g["band_str"], y=pb_g["rto_rate"], name="RTO %",
            marker_color="#F87171", text=[f"{v:.0f}%" for v in pb_g["rto_rate"]],
            textposition="auto",
        ))
        fig_pb.update_layout(**_fig(300), barmode="group", showlegend=True,
            title=dict(text="Delivery & RTO % by Price Band", font=dict(color="#FFFFFF",size=13)),
            legend=dict(font_color="#9CA3AF", bgcolor="rgba(0,0,0,0)",
                        orientation="h", y=1.18, x=0),
            xaxis=dict(showgrid=False, title="Order Value Band"),
            yaxis=dict(gridcolor="#1F2937", ticksuffix="%"))
        st.plotly_chart(fig_pb, use_container_width=True)

    # Top 5 products by RTO — quick insight
    top_rto = prod_g.nlargest(3, "rto_rate")
    if len(top_rto) > 0:
        rto_html = ""
        for _, row in top_rto.iterrows():
            rto_html += (f'<span style="background:rgba(248,113,113,0.12);color:#F87171;'
                         f'border:1px solid rgba(248,113,113,0.3);padding:4px 12px;'
                         f'border-radius:99px;font-size:0.8rem;margin:3px;display:inline-block;">'
                         f'{row["product_name"]} — {row["rto_rate"]:.1f}% RTO</span>')
        st.markdown(f'<div style="margin-top:4px;"><span style="color:#9CA3AF;'
                    f'font-size:0.8rem;font-weight:600;">⚠️ Highest RTO Products: </span>'
                    f'{rto_html}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHIC RTO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🗺️ Geographic RTO Analysis</div>",
            unsafe_allow_html=True)

geo1, geo2 = st.columns(2)
with geo1:
    if len(state_perf) > 0:
        fig_st = px.bar(
            state_perf.sort_values("rto_rate", ascending=False).head(8).sort_values("rto_rate"),
            x="rto_rate", y="state", orientation="h", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#F59E0B","#EF4444"],
            labels={"rto_rate":"RTO %","state":""},
        )
        fig_st.update_layout(**_fig(300),
            title=dict(text="Worst States by RTO %", font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_st, use_container_width=True)

with geo2:
    if "payment_type" in df.columns and "state" in df.columns:
        st_cod2 = df[df["payment_type"]=="COD"].groupby("state").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        st_cod2["cod_rto"] = st_cod2["rto"]/st_cod2["total"].clip(lower=1)*100
        fig_cod_st = px.bar(
            st_cod2.nlargest(8,"cod_rto").sort_values("cod_rto"),
            x="cod_rto", y="state", orientation="h", text_auto=".1f",
            color="cod_rto", color_continuous_scale=["#FBBF24","#EF4444"],
            labels={"cod_rto":"COD RTO %","state":""},
        )
        fig_cod_st.update_layout(**_fig(300),
            title=dict(text="Worst States — COD RTO %", font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_cod_st, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# VAS RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════
if recs:
    st.markdown("<div class='section-title'>💡 GDI Recommended VAS Actions</div>",
                unsafe_allow_html=True)
    rc = st.columns(min(len(recs), 4))
    for i, rec in enumerate(recs[:4]):
        rc[i].markdown(f"""
        <div class="saas-card" style="border:1px solid {rec['color']}35;">
          <span class="badge-recommend">{rec['badge']}</span>
          <h4 style="color:#FFFFFF;margin:10px 0 6px;font-size:1rem;">{rec['name']}</h4>
          <p style="color:#9CA3AF;font-size:0.82rem;margin:0 0 12px;">{rec['impact']}</p>
          <div style="border-top:1px solid #1F2937;padding-top:10px;">
            <span style="font-size:0.72rem;color:#34D399;text-transform:uppercase;
                         font-weight:600;">Revenue Unlock</span>
            <div style="font-size:1.2rem;font-weight:700;color:#34D399;">₹{rec['revenue']:,}</div>
          </div>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# ASK GDI AGENT BANNER
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🤖 Ask GDI Agent</div>", unsafe_allow_html=True)
st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(135deg,rgba(79,70,229,0.18) 0%,
     rgba(124,58,237,0.12) 100%);border:1px solid rgba(79,70,229,0.3);text-align:center;
     padding:30px 24px;">
  <div style="font-size:2.4rem;margin-bottom:8px;">🤖</div>
  <h3 style="color:#FFFFFF;font-size:1.25rem;font-weight:700;margin:0 0 8px;">
    Ask GDI Agent Anything About Your Data</h3>
  <p style="color:#9CA3AF;font-size:0.88rem;max-width:600px;margin:0 auto 18px;line-height:1.6;">
    Grounded in your <strong>{m['total']:,} shipments</strong>.
    Ask about specific sellers, products, couriers, COD strategy, or which VAS will help.
  </p>
  <div style="display:flex;justify-content:center;gap:8px;flex-wrap:wrap;margin-bottom:20px;">
    {"".join(
      f'<span style="background:rgba(129,140,248,0.12);color:#818CF8;border:1px solid rgba(129,140,248,0.3);padding:5px 13px;border-radius:99px;font-size:0.8rem;font-weight:600;">{q}</span>'
      for q in ["Compare all sellers","Top selling products","Will AI Calling help?",
                "Which courier is best?","Why is RTO high?","COD vs Prepaid breakdown"]
    )}
  </div>
  <a href="/7_AI_Chat_Assistant" target="_self"
     style="background:linear-gradient(135deg,#4F46E5,#7C3AED);color:#fff;
            padding:12px 32px;border-radius:10px;font-weight:700;font-size:0.95rem;
            text-decoration:none;display:inline-block;
            box-shadow:0 4px 18px rgba(79,70,229,0.4);">
    🤖 Open Ask GDI Agent →
  </a>
</div>""", unsafe_allow_html=True)

# ── Module Guide ──────────────────────────────────────────────────────────────
st.markdown("<div class='section-title'>🧭 GDI Modules</div>", unsafe_allow_html=True)
nav = [
    ("❤️","Seller Health","Delivery health score with benchmark comparison"),
    ("🔍","Root Cause","Auto-detected anomalies — why delivery is failing"),
    ("📦","SKU Intelligence","Which product underperforms and why"),
    ("🚀","VAS Recommendations","Ranked VAS mapped to your exact problem"),
    ("📞","AI Calling Engine","NDR priority queue + Order Confirmation"),
    ("💬","WhatsApp AI NDR","COD NDR resolution via WhatsApp AI"),
    ("🤖","Ask GDI Agent","Chat about any seller, product, courier or VAS"),
    ("📊","Impact Simulator","Model revenue impact of each VAS activation"),
]
nc = st.columns(4)
for i, (icon, title, desc) in enumerate(nav):
    nc[i%4].markdown(f"""
    <div class="saas-card" style="text-align:center;padding:14px;">
      <div style="font-size:1.7rem;">{icon}</div>
      <div style="color:#FFFFFF;font-weight:700;margin:6px 0 3px;font-size:0.88rem;">{title}</div>
      <div style="color:#9CA3AF;font-size:0.74rem;">{desc}</div>
    </div>""", unsafe_allow_html=True)
