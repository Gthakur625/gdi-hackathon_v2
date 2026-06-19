import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles      import apply_styles
from utils.sidebar     import render_sidebar_and_get_data
from utils.chat_widget import render_chat_button
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                           compute_courier_perf, compute_state_perf, get_recommendations,
                           get_anomalies)

apply_styles()
df_full = render_sidebar_and_get_data()

# ── shared chart base (NO showlegend / coloraxis keys — set per chart) ────────
def _fig(h=280):
    return dict(
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F3F4F6", height=h,
        margin=dict(l=0, r=0, t=42, b=0),
    )

def _card(label, value, color, sub=""):
    return (f'<div class="saas-card" style="text-align:center;padding:14px 8px;">'
            f'<div class="metric-label">{label}</div>'
            f'<div class="metric-value" style="color:{color};font-size:1.4rem;">{value}</div>'
            f'{"<div style=color:#9CA3AF;font-size:0.73rem;margin-top:3px;>" + sub + "</div>" if sub else ""}'
            f'</div>')

# ══════════════════════════════════════════════════════════════════════════════
# SELLER AUTOCOMPLETE SEARCH (admin view — when multiple sellers loaded)
# ══════════════════════════════════════════════════════════════════════════════
all_sellers = sorted(df_full["seller_name"].unique().tolist()) if "seller_name" in df_full.columns else []
is_admin    = len(all_sellers) > 1

# Header
st.markdown("""
<div class="header-card">
  <h1 class="header-title">⚡ Velocity GDI — Growth & Delivery Intelligence</h1>
  <p class="header-subtitle">AI-Powered Operations Consultant · Diagnose · Recommend · Act</p>
</div>""", unsafe_allow_html=True)

# Seller search bar (only when multiple sellers)
if is_admin:
    col_search, col_info = st.columns([3, 2])
    with col_search:
        selected_seller = st.selectbox(
            "🔍 Select Seller / Client (type to search)",
            ["📊 All Sellers"] + all_sellers,
            index=0,
            help="Start typing seller name to filter",
        )
    with col_info:
        if selected_seller != "📊 All Sellers":
            seller_count = len(df_full[df_full["seller_name"] == selected_seller])
            st.markdown(f"""
            <div style="background:rgba(79,70,229,0.12);border:1px solid rgba(79,70,229,0.3);
                        border-radius:10px;padding:12px 16px;margin-top:4px;">
              <span style="color:#818CF8;font-weight:700;">📌 {selected_seller}</span>
              <span style="color:#9CA3AF;font-size:0.82rem;margin-left:8px;">
                · {seller_count:,} shipments</span>
            </div>""", unsafe_allow_html=True)

    # Filter df based on selection
    if selected_seller != "📊 All Sellers":
        df = df_full[df_full["seller_name"] == selected_seller].copy()
    else:
        df = df_full.copy()
else:
    df = df_full.copy()
    selected_seller = all_sellers[0] if all_sellers else "All"

# ══════════════════════════════════════════════════════════════════════════════
# METRICS
# ══════════════════════════════════════════════════════════════════════════════
m          = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs         = compute_health_score(m)
recs       = get_recommendations(m)
state_perf = compute_state_perf(df)
cour_perf  = compute_courier_perf(df)
anomalies  = get_anomalies(df, m, state_perf, cour_perf)

cod_df     = df[df["payment_type"]=="COD"]
prepaid_df = df[df["payment_type"]=="Prepaid"]
cod_rto    = len(cod_df[cod_df["delivery_status"]=="RTO"])       / max(len(cod_df),1)    * 100
prep_rto   = len(prepaid_df[prepaid_df["delivery_status"]=="RTO"]) / max(len(prepaid_df),1) * 100
ndr_cod    = df[(df["payment_type"]=="COD") & (df["ndr_status"]=="Raised")] \
             if "ndr_status" in df.columns else pd.DataFrame()

if hs>=80:   sc="#34D399"; rl="Low Risk";    rb='<span class="badge-risk-low">🟢 Low Risk</span>'
elif hs>=65: sc="#FBBF24"; rl="Medium Risk"; rb='<span class="badge-risk-medium">🟡 Medium Risk</span>'
else:        sc="#FCA5A5"; rl="High Risk";   rb='<span class="badge-risk-high">🔴 High Risk</span>'
total_pot = sum(r["revenue"] for r in recs)

# Executive summary
sellers_in_view = df["seller_name"].nunique() if "seller_name" in df.columns else 1
st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(180deg,#161F30 0%,#111827 100%);
     border-left:4px solid #4F46E5;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
    <div style="flex:1;">
      <div style="color:#9CA3AF;font-size:0.78rem;text-transform:uppercase;letter-spacing:0.05em;">
        Executive Overview{"  ·  " + selected_seller if selected_seller != "📊 All Sellers" else ""}</div>
      <h2 style="color:#FFFFFF;font-size:1.4rem;font-weight:700;margin:6px 0;">
        Status: <span style="color:{sc};">{rl}</span>
        &nbsp;·&nbsp; Health: <span style="color:#818CF8;">{hs:.0f}/100</span>
      </h2>
      <p style="color:#D1D5DB;font-size:0.88rem;line-height:1.6;margin:0;">
        <strong>{m['total']:,} shipments</strong> · Delivery <strong>{m['delivery_pct']:.1f}%</strong>
        · RTO <strong>{m['rto_pct']:.1f}%</strong> · NDR <strong>{m['ndr_count']:,}</strong>
        · VAS unlock <strong>₹{total_pot:,}</strong>
      </p>
    </div>
    <div style="text-align:center;min-width:130px;">
      <div class="metric-label">Health Score</div>
      <div style="font-size:2.4rem;font-weight:800;color:#818CF8;line-height:1.1;">
        {hs:.0f}<span style="font-size:1rem;color:#6B7280;">/100</span></div>
      <div style="margin-top:6px;">{rb}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

# KPI row
c1,c2,c3,c4,c5,c6,c7 = st.columns(7)
pending_count = m.get("pending_count", 0)
for col, lbl, val, clr, sub in [
    (c1,"Delivery %",     f"{m['delivery_pct']:.1f}%", "#34D399",
     f"{m['delivered']:,} of {m['attempted_total']:,} attempted"),
    (c2,"RTO Rate",       f"{m['rto_pct']:.1f}%",      "#F87171", f"{m['rto_count']:,} returned"),
    (c3,"NDR Active",     f"{m['ndr_count']:,}",        "#FBBF24", "needs resolution"),
    (c4,"Pending Pickup",  f"{pending_count:,}",         "#6B7280", "not collected · excluded from %"),
    (c5,"COD Share",      f"{m['cod_pct']:.1f}%",       "#C084FC", f"₹{m['avg_order_value']:,.0f} avg order"),
    (c6,"Couriers",       f"{len(cour_perf)}",          "#818CF8", "3PL partners"),
    (c7,"VAS Unlock",     f"₹{total_pot:,}",            "#34D399", "revenue potential"),
]:
    col.markdown(_card(lbl,val,clr,sub), unsafe_allow_html=True)

if pending_count > 0:
    st.markdown(
        f'<div style="background:rgba(107,114,128,0.08);border:1px solid rgba(107,114,128,0.2);'
        f'border-radius:8px;padding:8px 14px;font-size:0.82rem;color:#9CA3AF;margin-bottom:10px;">'
        f'ℹ️ <b style="color:#D1D5DB;">{pending_count:,} shipments</b> are <b>Pending Pickup</b> '
        f'(courier not yet collected) — excluded from Delivery %. '
        f'In Transit shipments are included in the denominator.</div>',
        unsafe_allow_html=True)

# Anomalies
if anomalies:
    st.markdown("<div class='section-title'>🔍 GDI Detected Issues</div>", unsafe_allow_html=True)
    lvl = {"critical":"anomaly-critical","warning":"anomaly-warning","info":"anomaly-info"}
    for a in anomalies[:3]:
        st.markdown(f"""<div class="{lvl.get(a['level'],'anomaly-info')}">
          <strong style="color:#FFFFFF;">{a['icon']} {a['title']}</strong>
          <p style="color:#9CA3AF;margin:6px 0;font-size:0.87rem;">{a['detail']}</p>
          <span style="color:#818CF8;font-size:0.82rem;font-weight:600;">→ {a['fix']}</span>
        </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# COD vs PREPAID
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>💳 COD vs Prepaid Analysis</div>", unsafe_allow_html=True)
st.markdown("<p style='color:#9CA3AF;font-size:0.83rem;margin:-8px 0 12px;'>Use this to decide where to activate WhatsApp AI NDR and Order Confirmation Via AI.</p>", unsafe_allow_html=True)

r1c1,r1c2,r1c3,r1c4 = st.columns(4)
diff = cod_rto - prep_rto
r1c1.markdown(_card("COD Shipments",    f"{m['cod_count']:,}",           "#F87171", f"{m['cod_pct']:.1f}% of total"), unsafe_allow_html=True)
r1c2.markdown(_card("Prepaid Shipments",f"{m['total']-m['cod_count']:,}","#34D399", f"{100-m['cod_pct']:.1f}% of total"), unsafe_allow_html=True)
r1c3.markdown(_card("COD RTO Rate",     f"{cod_rto:.1f}%",              "#F87171", f"+{diff:.1f}% vs Prepaid"), unsafe_allow_html=True)
r1c4.markdown(_card("Prepaid RTO Rate", f"{prep_rto:.1f}%",             "#34D399", "lower risk"), unsafe_allow_html=True)

cp1,cp2,cp3 = st.columns([1.2,1.5,1.3])
with cp1:
    fig_d = go.Figure(go.Pie(
        labels=["COD","Prepaid"],
        values=[m["cod_count"], m["total"]-m["cod_count"]],
        hole=0.60, marker_colors=["#F87171","#34D399"],
        textinfo="label+percent", textfont=dict(color="#F3F4F6",size=11),
        hovertemplate="%{label}: %{value:,}<extra></extra>",
    ))
    fig_d.update_layout(**_fig(240), showlegend=False,
        annotations=[dict(text=f"<b>{m['cod_pct']:.0f}%</b><br>COD",
                          x=0.5,y=0.5,font_size=16,font_color="#F87171",showarrow=False)])
    st.markdown("<p style='color:#9CA3AF;font-size:0.75rem;font-weight:600;margin:0 0 3px;'>PAYMENT MIX</p>", unsafe_allow_html=True)
    st.plotly_chart(fig_d, use_container_width=True)

with cp2:
    fig_cp = go.Figure()
    fig_cp.add_trace(go.Bar(name="Delivery %", x=["COD","Prepaid"], y=[100-cod_rto,100-prep_rto],
        marker_color=["#F87171","#34D399"], text=[f"{100-cod_rto:.1f}%",f"{100-prep_rto:.1f}%"],
        textposition="auto", width=0.4))
    fig_cp.add_trace(go.Bar(name="RTO %", x=["COD","Prepaid"], y=[cod_rto,prep_rto],
        marker_color=["rgba(248,113,113,0.4)","rgba(52,211,153,0.4)"],
        text=[f"{cod_rto:.1f}%",f"{prep_rto:.1f}%"], textposition="auto", width=0.4))
    fig_cp.update_layout(**_fig(240), barmode="group", showlegend=True,
        legend=dict(font_color="#9CA3AF",bgcolor="rgba(0,0,0,0)",orientation="h",y=1.15,x=0),
        yaxis=dict(gridcolor="#1F2937",ticksuffix="%"), xaxis=dict(showgrid=False))
    st.markdown("<p style='color:#9CA3AF;font-size:0.75rem;font-weight:600;margin:0 0 3px;'>DELIVERY vs RTO BY PAYMENT TYPE</p>", unsafe_allow_html=True)
    st.plotly_chart(fig_cp, use_container_width=True)

with cp3:
    cc = "#F87171" if diff>8 else ("#FBBF24" if diff>4 else "#34D399")
    ins = ("🚨 Activate WhatsApp AI NDR + Order Confirmation Via AI immediately."
           if diff>8 else ("⚠️ WhatsApp AI NDR will protect COD deliveries."
           if diff>4 else "✅ COD risk is manageable."))
    st.markdown(f"""
    <div class="saas-card" style="padding:18px;">
      <div style="color:#9CA3AF;font-size:0.75rem;font-weight:600;text-transform:uppercase;margin-bottom:12px;">COD RISK</div>
      <div style="display:flex;justify-content:space-between;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid #1F2937;">
        <span style="color:#9CA3AF;font-size:0.82rem;">COD Premium vs Prepaid</span>
        <span style="color:{cc};font-weight:800;font-size:1.2rem;">+{diff:.1f}%</span>
      </div>
      <div style="display:flex;justify-content:space-between;padding-bottom:10px;margin-bottom:10px;border-bottom:1px solid #1F2937;">
        <span style="color:#9CA3AF;font-size:0.82rem;">COD NDR Active</span>
        <span style="color:#FBBF24;font-weight:700;">{len(ndr_cod):,}</span>
      </div>
      <div style="display:flex;justify-content:space-between;margin-bottom:14px;">
        <span style="color:#9CA3AF;font-size:0.82rem;">Revenue at Risk</span>
        <span style="color:#F87171;font-weight:700;">₹{int(m['rto_count']*m['avg_order_value']):,}</span>
      </div>
      <div style="background:#0B0F19;border-radius:8px;padding:10px;font-size:0.8rem;color:#D1D5DB;line-height:1.5;">{ins}</div>
    </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# 3PL PERFORMANCE
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🚚 3PL Courier Performance</div>", unsafe_allow_html=True)
pl1,pl2 = st.columns(2)
with pl1:
    fig_del = px.bar(cour_perf.sort_values("delivery_rate"),
        x="delivery_rate", y="courier", orientation="h", text_auto=".1f",
        color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
        labels={"delivery_rate":"Delivery %","courier":""})
    fig_del.update_layout(**_fig(max(240,len(cour_perf)*46)), showlegend=False, coloraxis_showscale=False,
        title=dict(text="Delivery Rate % by Courier",font=dict(color="#FFFFFF",size=13)),
        xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
    st.plotly_chart(fig_del, use_container_width=True)

with pl2:
    fig_rto = px.bar(cour_perf.sort_values("rto_rate",ascending=False),
        x="rto_rate", y="courier", orientation="h", text_auto=".1f",
        color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
        labels={"rto_rate":"RTO %","courier":""})
    fig_rto.update_layout(**_fig(max(240,len(cour_perf)*46)), showlegend=False, coloraxis_showscale=False,
        title=dict(text="RTO Rate % by Courier",font=dict(color="#FFFFFF",size=13)),
        xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
    st.plotly_chart(fig_rto, use_container_width=True)

if len(cour_perf)>0:
    best=cour_perf.sort_values("delivery_rate",ascending=False).iloc[0]
    worst=cour_perf.sort_values("delivery_rate").iloc[0]
    m1,m2,m3,m4 = st.columns(4)
    m1.markdown(_card("Best Courier",    best["courier"],                        "#34D399", f"{best['delivery_rate']:.1f}%"), unsafe_allow_html=True)
    m2.markdown(_card("Needs Attention", worst["courier"],                       "#F87171", f"{worst['delivery_rate']:.1f}%"), unsafe_allow_html=True)
    m3.markdown(_card("Performance Gap", f"{best['delivery_rate']-worst['delivery_rate']:.1f}%","#FBBF24","best vs worst"), unsafe_allow_html=True)
    m4.markdown(_card("3PL Partners",    str(len(cour_perf)),                   "#818CF8", "active couriers"), unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# TOP SELLERS (admin multi-seller view)
# ══════════════════════════════════════════════════════════════════════════════
if is_admin and selected_seller == "📊 All Sellers":
    st.markdown("<div class='section-title'>🏆 Seller Performance</div>", unsafe_allow_html=True)
    sg = df_full.groupby("seller_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
    ).reset_index()
    sg["delivery_rate"] = sg["delivered"]/sg["total"]*100
    sg["rto_rate"]      = sg["rto"]/sg["total"]*100
    sg = sg.sort_values("delivery_rate",ascending=False).reset_index(drop=True)

    sl1,sl2 = st.columns([3,2])
    with sl1:
        fig_sl = px.bar(sg.sort_values("delivery_rate"),
            x="delivery_rate", y="seller_name", orientation="h", text_auto=".1f",
            color="delivery_rate", color_continuous_scale=["#EF4444","#10B981"],
            labels={"delivery_rate":"Delivery %","seller_name":""})
        fig_sl.update_layout(**_fig(max(240,len(sg)*52)), showlegend=False, coloraxis_showscale=False,
            title=dict(text="Seller Delivery Rate %",font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_sl, use_container_width=True)

    with sl2:
        rows_html = ""
        for i,row in sg.iterrows():
            m = ["🥇","🥈","🥉"][i] if i<3 else f"{i+1}."
            c = "#34D399" if row["delivery_rate"]>=80 else ("#FBBF24" if row["delivery_rate"]>=65 else "#F87171")
            rows_html += f"""<div style="display:flex;justify-content:space-between;align-items:center;
                padding:9px 4px;border-bottom:1px solid #1F2937;">
              <div style="color:#FFFFFF;font-size:0.82rem;">{m} {row['seller_name']}</div>
              <div style="display:flex;gap:10px;">
                <span style="color:{c};font-weight:700;font-size:0.85rem;">{row['delivery_rate']:.1f}%</span>
                <span style="color:#F87171;font-size:0.77rem;">RTO {row['rto_rate']:.1f}%</span>
              </div></div>"""
        st.markdown(f'<div class="saas-card" style="padding:14px;">'
                    f'<div style="color:#9CA3AF;font-size:0.75rem;font-weight:600;text-transform:uppercase;margin-bottom:8px;">SCOREBOARD</div>'
                    f'{rows_html}</div>', unsafe_allow_html=True)

# Reset m for charts below (in case seller was selected)
m = compute_kpis(df)

# ══════════════════════════════════════════════════════════════════════════════
# TOP PRODUCTS + PRICING BAND
# ══════════════════════════════════════════════════════════════════════════════
if "product_name" in df.columns:
    st.markdown("<div class='section-title'>📦 Top Products & Pricing Band</div>", unsafe_allow_html=True)
    st.markdown("<p style='color:#9CA3AF;font-size:0.83rem;margin:-8px 0 12px;'>Top products by volume and RTO by price range — identifies where to restrict COD and apply Order Confirmation Via AI.</p>", unsafe_allow_html=True)

    pg_df = df.groupby("product_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        revenue  =("order_value","sum"),
    ).reset_index()
    pg_df["rto_rate"] = pg_df["rto"]/pg_df["total"].clip(lower=1)*100
    pg_df["del_rate"] = pg_df["delivered"]/pg_df["total"].clip(lower=1)*100
    top10 = pg_df.sort_values("delivered",ascending=False).head(10)

    tp1,tp2 = st.columns(2)
    with tp1:
        fig_prod = px.bar(top10, x="product_name", y="delivered",
            color="del_rate", color_continuous_scale=["#4F46E5","#34D399"],
            text_auto=True, labels={"product_name":"","delivered":"Delivered","del_rate":"Delivery %"})
        fig_prod.update_layout(**_fig(300), showlegend=False, coloraxis_showscale=False,
            title=dict(text="Top 10 Products — Delivered Units",font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(tickangle=-30,showgrid=False), yaxis=dict(gridcolor="#1F2937"))
        st.plotly_chart(fig_prod, use_container_width=True)

    with tp2:
        bins  = [0,499,999,1999,4999,float("inf")]
        blbls = ["₹0–499","₹500–999","₹1K–2K","₹2K–5K","₹5K+"]
        df_pb = df.copy()
        df_pb["price_band"] = pd.cut(df_pb["order_value"],bins=bins,labels=blbls,right=True)
        pb = df_pb.groupby("price_band",observed=True).agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        pb["del_rate"] = pb["delivered"]/pb["total"].clip(lower=1)*100
        pb["rto_rate"] = pb["rto"]/pb["total"].clip(lower=1)*100

        fig_pb = go.Figure()
        fig_pb.add_trace(go.Bar(x=pb["price_band"].astype(str), y=pb["del_rate"],
            name="Delivery %", marker_color="#34D399",
            text=[f"{v:.0f}%" for v in pb["del_rate"]], textposition="auto"))
        fig_pb.add_trace(go.Bar(x=pb["price_band"].astype(str), y=pb["rto_rate"],
            name="RTO %", marker_color="#F87171",
            text=[f"{v:.0f}%" for v in pb["rto_rate"]], textposition="auto"))
        fig_pb.update_layout(**_fig(300), barmode="group", showlegend=True,
            legend=dict(font_color="#9CA3AF",bgcolor="rgba(0,0,0,0)",orientation="h",y=1.18,x=0),
            title=dict(text="Delivery & RTO % by Price Band",font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#1F2937",ticksuffix="%"))
        st.plotly_chart(fig_pb, use_container_width=True)

    top_rto = pg_df.nlargest(3,"rto_rate")
    if len(top_rto)>0:
        chips = "".join(
            f'<span style="background:rgba(248,113,113,0.1);color:#F87171;border:1px solid rgba(248,113,113,0.3);'
            f'padding:4px 10px;border-radius:99px;font-size:0.78rem;margin:3px;display:inline-block;">'
            f'{row["product_name"]} — {row["rto_rate"]:.1f}% RTO</span>'
            for _,row in top_rto.iterrows())
        st.markdown(f'<div style="margin:4px 0 12px;"><span style="color:#9CA3AF;font-size:0.78rem;font-weight:600;">⚠️ Highest RTO: </span>{chips}</div>', unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# GEOGRAPHIC RTO
# ══════════════════════════════════════════════════════════════════════════════
st.markdown("<div class='section-title'>🗺️ Geographic RTO Analysis</div>", unsafe_allow_html=True)
geo1,geo2 = st.columns(2)
with geo1:
    if len(state_perf)>0:
        fig_st = px.bar(state_perf.sort_values("rto_rate",ascending=False).head(8).sort_values("rto_rate"),
            x="rto_rate", y="state", orientation="h", text_auto=".1f",
            color="rto_rate", color_continuous_scale=["#F59E0B","#EF4444"],
            labels={"rto_rate":"RTO %","state":""})
        fig_st.update_layout(**_fig(300), showlegend=False, coloraxis_showscale=False,
            title=dict(text="Worst States by RTO %",font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_st, use_container_width=True)

with geo2:
    if "payment_type" in df.columns:
        sc2 = df[df["payment_type"]=="COD"].groupby("state").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        sc2["cod_rto"] = sc2["rto"]/sc2["total"].clip(lower=1)*100
        fig_c2 = px.bar(sc2.nlargest(8,"cod_rto").sort_values("cod_rto"),
            x="cod_rto", y="state", orientation="h", text_auto=".1f",
            color="cod_rto", color_continuous_scale=["#FBBF24","#EF4444"],
            labels={"cod_rto":"COD RTO %","state":""})
        fig_c2.update_layout(**_fig(300), showlegend=False, coloraxis_showscale=False,
            title=dict(text="Worst States — COD RTO %",font=dict(color="#FFFFFF",size=13)),
            xaxis=dict(gridcolor="#1F2937",ticksuffix="%"), yaxis=dict(showgrid=False))
        st.plotly_chart(fig_c2, use_container_width=True)

# ══════════════════════════════════════════════════════════════════════════════
# VAS RECOMMENDATIONS
# ══════════════════════════════════════════════════════════════════════════════
if recs:
    st.markdown("<div class='section-title'>💡 GDI Recommended VAS Actions</div>", unsafe_allow_html=True)
    rc = st.columns(min(len(recs),4))
    for i,rec in enumerate(recs[:4]):
        rc[i].markdown(f"""
        <div class="saas-card" style="border:1px solid {rec['color']}35;">
          <span class="badge-recommend">{rec['badge']}</span>
          <h4 style="color:#FFFFFF;margin:10px 0 6px;font-size:0.95rem;">{rec['name']}</h4>
          <p style="color:#9CA3AF;font-size:0.8rem;margin:0 0 12px;">{rec['impact']}</p>
          <div style="border-top:1px solid #1F2937;padding-top:10px;">
            <span style="font-size:0.7rem;color:#34D399;text-transform:uppercase;font-weight:600;">Revenue Unlock</span>
            <div style="font-size:1.15rem;font-weight:700;color:#34D399;">₹{rec['revenue']:,}</div>
          </div>
        </div>""", unsafe_allow_html=True)

# ── Ask GDI Agent inline button (opens dialog popup, no page redirect) ────────
render_chat_button(df)
