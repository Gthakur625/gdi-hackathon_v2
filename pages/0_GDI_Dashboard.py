import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles               import apply_styles
from utils.sidebar              import render_sidebar_and_get_data
from utils.chat_widget          import render_chat_button
from utils.seller_intelligence  import render_seller_intelligence
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
  <p class="header-subtitle">AI Operations Consultant · Diagnose · Recommend · Act</p>
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

# NDD partners
NDD_PARTNERS = ["Elastic Run", "PiknDel", "Blitz"]
zone_col = next((c for c in ["zone","standard_zone","Zone"] if c in df.columns), None)
zone_ab_count = 0
if zone_col:
    zone_ab_count = int(df[df[zone_col].astype(str).str.upper().isin(["A","B"])].shape[0])

# ── AI EXECUTIVE BRIEFING ─────────────────────────────────────────────────────
def _build_briefing(df, m, hs, recs, cour_perf, state_perf, seller_label):
    """Generate proactive AI briefing text blocks for risks, opportunities, actions."""
    risks, opps, actions = [], [], []

    # Risks
    if m["rto_pct"] > 20:
        risks.append(f"🚨 RTO at <b style='color:#F87171;'>{m['rto_pct']:.1f}%</b> — above 20% threshold")
    if m["cod_pct"] > 65:
        risks.append(f"⚠️ COD at <b style='color:#C084FC;'>{m['cod_pct']:.1f}%</b> — high fake-order risk")
    if m["ndr_pct"] > 15:
        risks.append(f"⚠️ NDR backlog <b style='color:#FBBF24;'>{m['ndr_count']:,}</b> shipments unresolved")
    if len(state_perf) > 0:
        ws = state_perf.sort_values("rto_rate", ascending=False).iloc[0]
        if ws["rto_rate"] > 30:
            risks.append(f"🚨 <b>{ws['state']}</b> — {ws['rto_rate']:.0f}% RTO, your biggest hotspot")
    if len(cour_perf) > 0:
        wc = cour_perf.sort_values("delivery_rate").iloc[0]
        if wc["delivery_rate"] < 70:
            risks.append(f"⚠️ <b>{wc['courier']}</b> delivering only {wc['delivery_rate']:.0f}%")
    if not risks:
        risks.append("✅ No critical risks detected in current period")

    # Opportunities
    if m["ndr_count"] > 10:
        rec = int(m["ndr_count"] * 0.38)
        opps.append(f"📞 <b>AI Calling</b> → recover ~{rec:,} NDRs → <b style='color:#34D399;'>₹{int(rec*m['avg_order_value']):,}</b>")
    if m["cod_pct"] > 55 and m["ndr_pct"] > 10:
        saved = int(m["rto_count"] * 0.08)
        opps.append(f"💬 <b>WhatsApp AI NDR</b> → prevent ~{saved:,} COD RTOs → <b style='color:#34D399;'>₹{int(saved*m['avg_order_value']):,}</b>")
    if m["rto_pct"] > 15:
        saved = int(m["rto_count"] * 0.12)
        opps.append(f"🔍 <b>Order Confirmation Via AI</b> → stop ~{saved:,} fake orders → <b style='color:#34D399;'>₹{int(saved*m['avg_order_value']):,}</b>")
    if zone_ab_count > 0:
        pct = zone_ab_count / max(m["total"], 1) * 100
        opps.append(f"🚀 <b>NDD (Elastic Run / PiknDel / Blitz)</b> → {pct:.0f}% orders in Zone A/B eligible for next-day delivery")
    if not opps:
        opps.append("✅ Operations healthy — focus on expanding volume with top couriers")

    # Actions (prioritised)
    priority = sorted(recs, key=lambda r: r["revenue"], reverse=True)
    for i, r in enumerate(priority[:3], 1):
        actions.append(f"<b>#{i}</b> Activate <b>{r['name']}</b> — {r['impact']}")
    if not actions:
        actions.append("<b>#1</b> Maintain current VAS stack and monitor NDR age daily")

    return risks[:4], opps[:4], actions[:3]

risks, opps, actions = _build_briefing(df, m, hs, recs, cour_perf, state_perf,
                                        selected_seller if is_admin else None)

def _bullet(items, color="#D1D5DB"):
    return "".join(f'<div style="padding:4px 0;border-bottom:1px solid #1F2937;font-size:0.82rem;color:{color};">{it}</div>' for it in items)

scope = f" — {selected_seller}" if (is_admin and selected_seller != "📊 All Sellers") else ""
st.markdown(f"""
<div style="background:linear-gradient(135deg,#0F172A 0%,#111827 100%);
     border:1px solid #1F2937;border-radius:16px;padding:20px 24px;margin-bottom:18px;
     border-left:4px solid #818CF8;">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:16px;margin-bottom:16px;">
    <div>
      <div style="color:#818CF8;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.08em;margin-bottom:4px;">🤖 GDI Consultant — AI Executive Briefing{scope}</div>
      <div style="color:#FFFFFF;font-size:1.35rem;font-weight:800;line-height:1.2;">
        Status: <span style="color:{sc};">{rl}</span>
        <span style="color:#6B7280;font-size:0.9rem;font-weight:400;margin-left:12px;">
          {m['delivered']:,} delivered of {m['attempted_total']:,} attempted</span>
      </div>
    </div>
    <div style="text-align:center;background:#0B0F19;border-radius:12px;padding:10px 20px;min-width:110px;">
      <div style="font-size:2rem;font-weight:800;color:#818CF8;line-height:1;">{hs:.0f}</div>
      <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">/100 Health</div>
      <div style="margin-top:4px;">{rb}</div>
    </div>
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:16px;">
    <div>
      <div style="color:#F87171;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:6px;">⚡ Top Risks</div>
      {_bullet(risks)}
    </div>
    <div>
      <div style="color:#34D399;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:6px;">💰 Opportunities</div>
      {_bullet(opps)}
    </div>
    <div>
      <div style="color:#818CF8;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:6px;">✅ Recommended Actions</div>
      {_bullet(actions)}
    </div>
  </div>
  <div style="margin-top:14px;padding-top:12px;border-top:1px solid #1F2937;
              display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:8px;">
    <div style="font-size:0.78rem;color:#6B7280;">
      {m['total']:,} shipments · COD {m['cod_pct']:.0f}% · NDR {m['ndr_count']:,}
      · Avg ₹{m['avg_order_value']:,.0f} · {len(cour_perf)} couriers active
      {f" · 🚀 {zone_ab_count:,} Zone A/B NDD-eligible" if zone_ab_count > 0 else ""}
    </div>
    <div style="font-size:0.78rem;color:#34D399;font-weight:600;">
      💰 Total revenue unlock: ₹{total_pot:,}
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

# Reset m for sections below (in case seller was selected)
m = compute_kpis(df)

# ══════════════════════════════════════════════════════════════════════════════
# TOP PRODUCTS + PRICING BAND — AI INSIGHTS (text, not charts)
# ══════════════════════════════════════════════════════════════════════════════
if "product_name" in df.columns:
    seller_label = selected_seller if (is_admin and selected_seller != "📊 All Sellers") else None
    st.markdown(
        f"<div class='section-title'>📦 Product Intelligence"
        f"{' — ' + seller_label if seller_label else ''}</div>",
        unsafe_allow_html=True)

    # ── compute product table ─────────────────────────────────────────────────
    pg_df = df.groupby("product_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        ndr      =("delivery_status", lambda x:(x=="NDR").sum()),
        cod      =("payment_type",    lambda x:(x=="COD").sum()),
        revenue  =("order_value","sum"),
        avg_val  =("order_value","mean"),
    ).reset_index()
    pg_df["dr"]      = pg_df["delivered"] / pg_df["total"].clip(lower=1) * 100
    pg_df["rr"]      = pg_df["rto"]       / pg_df["total"].clip(lower=1) * 100
    pg_df["cod_pct"] = pg_df["cod"]       / pg_df["total"].clip(lower=1) * 100
    avg_dr = m["delivery_pct"]; avg_rr = m["rto_pct"]

    # check NDD zones
    ndd_partners = ["Elastic Run", "PiknDel", "Blitz"]
    zone_col = "zone" if "zone" in df.columns else ("standard_zone" if "standard_zone" in df.columns else None)
    zone_ab_pct = 0
    if zone_col:
        zone_ab = df[df[zone_col].astype(str).str.upper().isin(["A","B","ZONE A","ZONE B"])]
        zone_ab_pct = len(zone_ab) / max(len(df),1) * 100

    top5 = pg_df.sort_values("total", ascending=False).head(5)
    pi1, pi2 = st.columns([3, 2])

    with pi1:
        st.markdown(
            "<div style='color:#9CA3AF;font-size:0.75rem;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.05em;margin-bottom:10px;'>TOP 5 PRODUCTS — AI INSIGHTS</div>",
            unsafe_allow_html=True)
        for rank, (_, row) in enumerate(top5.iterrows(), 1):
            dr_icon = "✅" if row["dr"] >= avg_dr else ("⚠️" if row["dr"] >= avg_dr-10 else "🚨")
            dr_col  = "#34D399" if row["dr"] >= avg_dr else ("#FBBF24" if row["dr"] >= avg_dr-10 else "#F87171")

            # generate personalized insight
            if row["rr"] > avg_rr * 1.5 and row["cod_pct"] > 65:
                tip  = "💡 High RTO + High COD — activate <b>Order Confirmation Via AI</b> before dispatch"
                tip_c= "#FBBF24"
            elif row["rr"] > avg_rr * 1.5:
                tip  = "💡 High RTO — restrict COD in UP/Bihar; try <b>AI Calling</b> for NDR recovery"
                tip_c= "#F87171"
            elif row["ndr"] > row["total"] * 0.15:
                tip  = "💡 High NDR — activate <b>WhatsApp AI NDR</b> messaging for failed deliveries"
                tip_c= "#FBBF24"
            elif row["dr"] >= avg_dr + 5 and zone_ab_pct > 30:
                tip  = f"💡 Top performer — consider <b>NDD</b> (Elastic Run/PiknDel) for Zone A/B orders"
                tip_c= "#34D399"
            else:
                tip  = f"💡 Near average — <b>WhatsApp NDR</b> can recover ~{int(row['rto']*0.08):,} RTOs/month"
                tip_c= "#818CF8"

            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1F2937;border-radius:10px;
                        padding:12px 16px;margin-bottom:8px;">
              <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                <span style="color:#FFFFFF;font-weight:700;font-size:0.9rem;">
                  {rank}. {row['product_name']}</span>
                <span style="color:{dr_col};font-weight:800;font-size:0.95rem;">{row['dr']:.0f}% {dr_icon}</span>
              </div>
              <div style="display:flex;gap:16px;font-size:0.8rem;color:#9CA3AF;margin-bottom:8px;">
                <span>{row['total']:,} orders</span>
                <span>RTO <b style="color:#F87171;">{row['rr']:.0f}%</b></span>
                <span>NDR <b style="color:#FBBF24;">{row['ndr']:,}</b></span>
                <span>COD <b style="color:#C084FC;">{row['cod_pct']:.0f}%</b></span>
                <span>₹{row['avg_val']:,.0f} avg</span>
              </div>
              <div style="background:rgba(0,0,0,0.2);border-radius:6px;padding:7px 10px;
                          font-size:0.78rem;color:{tip_c};">{tip}</div>
            </div>""", unsafe_allow_html=True)

    with pi2:
        st.markdown(
            "<div style='color:#9CA3AF;font-size:0.75rem;font-weight:600;text-transform:uppercase;"
            "letter-spacing:0.05em;margin-bottom:10px;'>PRICING BAND INSIGHTS</div>",
            unsafe_allow_html=True)
        bins  = [0,499,999,1999,4999,float("inf")]
        blbls = ["₹0–499","₹500–999","₹1K–2K","₹2K–5K","₹5K+"]
        df_pb = df.copy()
        df_pb["pb"] = pd.cut(df_pb["order_value"],bins=bins,labels=blbls,right=True)
        pb = df_pb.groupby("pb",observed=True).agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            cod      =("payment_type",    lambda x:(x=="COD").sum()),
        ).reset_index()
        pb["dr"]      = pb["delivered"] / pb["total"].clip(lower=1) * 100
        pb["rr"]      = pb["rto"]       / pb["total"].clip(lower=1) * 100
        pb["cod_pct"] = pb["cod"]       / pb["total"].clip(lower=1) * 100

        for _, row in pb.iterrows():
            if row["total"] == 0: continue
            e  = "🚨" if row["rr"]>30 else ("⚠️" if row["rr"]>20 else "✅")
            ec = "#F87171" if row["rr"]>30 else ("#FBBF24" if row["rr"]>20 else "#34D399")
            if row["rr"] > 30 and row["cod_pct"] > 60:
                tip = "Restrict COD + Order Confirmation Via AI"
            elif row["rr"] > 20:
                tip = "Restrict COD for high-risk states in this band"
            elif row["dr"] > 85:
                tip = "Strong band — NDD upgrade for Zone A/B"
            else:
                tip = "WhatsApp NDR for failed COD deliveries"
            st.markdown(f"""
            <div style="background:#111827;border:1px solid #1F2937;border-radius:8px;
                        padding:10px 14px;margin-bottom:6px;">
              <div style="display:flex;justify-content:space-between;align-items:center;">
                <b style="color:#FFFFFF;font-size:0.88rem;">{e} {row['pb']}</b>
                <span style="color:{ec};font-weight:700;font-size:0.88rem;">{row['dr']:.0f}% del</span>
              </div>
              <div style="font-size:0.77rem;color:#9CA3AF;margin:4px 0;">
                {row['total']:,} orders · RTO <b style="color:{ec};">{row['rr']:.0f}%</b>
                · COD <b>{row['cod_pct']:.0f}%</b>
              </div>
              <div style="font-size:0.76rem;color:#818CF8;margin-top:4px;">💡 {tip}</div>
            </div>""", unsafe_allow_html=True)

        # NDD opportunity callout
        if zone_ab_pct > 0:
            st.markdown(f"""
            <div style="background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.25);
                        border-radius:8px;padding:10px 14px;margin-top:8px;">
              <div style="color:#34D399;font-weight:700;font-size:0.82rem;margin-bottom:4px;">
                🚀 NDD Opportunity</div>
              <div style="color:#9CA3AF;font-size:0.78rem;line-height:1.5;">
                <b style="color:#FFFFFF;">{zone_ab_pct:.0f}%</b> of shipments in Zone A/B<br>
                Partners: <b>Elastic Run · PiknDel · Blitz</b><br>
                Next day delivery → fewer NDRs, happier customers
              </div>
            </div>""", unsafe_allow_html=True)

# ══════════════════════════════════════════════════════════════════════════════
# SELLER INTELLIGENCE LAYER (shown when a specific seller is selected)
# ══════════════════════════════════════════════════════════════════════════════
if is_admin and selected_seller != "📊 All Sellers":
    st.markdown("<div class='section-title'>🔬 Seller Intelligence</div>",
                unsafe_allow_html=True)
    render_seller_intelligence(
        df=df,
        seller_name=selected_seller,
        overall_delivery_pct=compute_kpis(df_full)["delivery_pct"],
        overall_rto_pct=compute_kpis(df_full)["rto_pct"],
    )
elif not is_admin:
    # Single-seller mode — always show intelligence
    st.markdown("<div class='section-title'>🔬 Seller Intelligence</div>",
                unsafe_allow_html=True)
    render_seller_intelligence(
        df=df,
        seller_name=all_sellers[0] if all_sellers else "Your Account",
        overall_delivery_pct=m["delivery_pct"],
        overall_rto_pct=m["rto_pct"],
    )

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
