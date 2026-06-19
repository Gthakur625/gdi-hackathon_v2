import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                           compute_sku_perf, compute_courier_perf, compute_state_perf,
                           get_recommendations)

apply_styles()

# ── extra styles for this page ────────────────────────────────────────────────
st.markdown("""
<style>
.agent-lbl{display:flex;align-items:center;gap:8px;color:#818CF8;font-size:0.75rem;
           font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:3px;}
.user-lbl{text-align:right;color:#6B7280;font-size:0.75rem;font-weight:600;
          margin-bottom:3px;text-transform:uppercase;}
.sim-card{background:#0B0F19;border:1px solid #4F46E5;border-radius:12px;
          padding:18px 22px;margin:10px 0;}
.sim-title{color:#818CF8;font-weight:800;font-size:1rem;margin:0 0 12px;}
.sim-row{display:flex;justify-content:space-between;align-items:center;
         padding:7px 0;border-bottom:1px solid #1F2937;font-size:0.85rem;}
.sim-row:last-child{border-bottom:none;padding-top:10px;}
.sim-lbl{color:#9CA3AF;}
.sim-val{font-weight:700;color:#FFFFFF;}
.sim-highlight{color:#34D399;font-size:1.1rem;font-weight:800;}
.qchip{display:inline-block;background:rgba(79,70,229,0.10);color:#818CF8;
       border:1px solid rgba(79,70,229,0.25);padding:5px 13px;border-radius:99px;
       font-size:0.78rem;font-weight:600;margin:3px 3px 0 0;cursor:pointer;}
.insight-tag{display:inline-block;padding:3px 10px;border-radius:99px;font-size:0.75rem;
             font-weight:600;margin:2px;}
</style>""", unsafe_allow_html=True)

df_full = render_sidebar_and_get_data()

# ── precompute all metrics ────────────────────────────────────────────────────
m_all           = compute_kpis(df_full)
m_all["vas_adoption_score"] = compute_vas_adoption_score(df_full)
hs_all          = compute_health_score(m_all)
recs_all        = get_recommendations(m_all)
sku_df          = compute_sku_perf(df_full)
cour_df         = compute_courier_perf(df_full)
state_df        = compute_state_perf(df_full)
all_sellers     = sorted(df_full["seller_name"].unique().tolist()) if "seller_name" in df_full.columns else []
is_admin        = len(all_sellers) > 1

cod_df      = df_full[df_full["payment_type"]=="COD"]
prep_df     = df_full[df_full["payment_type"]=="Prepaid"]
cod_rto_pct = len(cod_df[cod_df["delivery_status"]=="RTO"]) / max(len(cod_df),1) * 100
prep_rto_pct= len(prep_df[prep_df["delivery_status"]=="RTO"]) / max(len(prep_df),1) * 100
best_c      = cour_df.sort_values("delivery_rate",ascending=False).iloc[0] if len(cour_df)>0 else None
worst_c     = cour_df.sort_values("delivery_rate").iloc[0]                 if len(cour_df)>0 else None
worst_st    = state_df.sort_values("rto_rate",ascending=False).iloc[0]     if len(state_df)>0 else None


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

def _words(s):
    return set(re.sub(r'[^\w\s]',' ', s.lower()).split())

def _find(q_lower, candidates):
    qw = _words(q_lower)
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in q_lower: return name
    for name in candidates:
        sig = [w for w in _words(name) if len(w)>=4]
        if sig and any(w in qw for w in sig): return name
    return None

def _chart(orient, x, y, title, color="#818CF8", xlabel="", ylabel=""):
    return dict(orient=orient, x=[str(v) for v in x],
                y=[float(v) if isinstance(v,(int,float,np.integer,np.floating)) else 0 for v in y],
                title=title, color=color, xlabel=xlabel, ylabel=ylabel)

def _render_chart(c):
    if not c: return
    try:
        if c["orient"]=="h":
            fig = go.Figure(go.Bar(x=c["y"],y=c["x"],orientation="h",marker_color=c["color"],
                text=[f"{v:.1f}" for v in c["y"]],textposition="auto"))
            fig.update_layout(yaxis=dict(autorange="reversed"))
        else:
            fig = go.Figure(go.Bar(x=c["x"],y=c["y"],marker_color=c["color"],
                text=[f"{v:,.0f}" if isinstance(v,float) and v>10 else f"{v:.1f}" for v in c["y"]],
                textposition="auto"))
        fig.update_layout(title=dict(text=c["title"],font=dict(color="#FFFFFF",size=13)),
            paper_bgcolor="rgba(0,0,0,0)",plot_bgcolor="rgba(0,0,0,0)",
            font_color="#F3F4F6",height=300,margin=dict(l=0,r=0,t=40,b=0),
            showlegend=False,
            xaxis=dict(showgrid=False,title=c["xlabel"]),
            yaxis=dict(gridcolor="#1F2937",title=c["ylabel"]))
        st.plotly_chart(fig, use_container_width=True)
    except Exception: pass

def _render_sim(sim):
    if not sim: return
    st.markdown(f"""
    <div class="sim-card">
      <div class="sim-title">📊 {sim['title']}</div>
      {"".join(
        f'<div class="sim-row"><span class="sim-lbl">{r[0]}</span>'
        f'<span class="{"sim-highlight" if r[2] else "sim-val"}">{r[1]}</span></div>'
        for r in sim['rows']
      )}
    </div>""", unsafe_allow_html=True)

def _sim_ai_calling(df, m):
    rec    = int(m["ndr_count"]*0.38)
    rev    = int(rec * m["avg_order_value"])
    rto_sv = int(m["ndr_count"]*0.15 * m["avg_order_value"] * 0.4)
    stale  = len(df[(df["ndr_status"]=="Raised")&(df["ndr_age_hours"]>48)]) \
             if ("ndr_status" in df.columns and "ndr_age_hours" in df.columns) else 0
    return {
        "title": "AI Calling — NDR Recovery Simulation",
        "rows": [
            ("Total NDR Queue",            f"{m['ndr_count']:,} shipments",          False),
            ("Stale NDRs (>48h)",          f"{stale:,} — high RTO risk",             False),
            ("AI Calling Recovery Rate",   "38% (industry benchmark)",               False),
            ("Expected Recoveries",        f"{rec:,} shipments/month",               False),
            ("Avg Order Value",            f"₹{m['avg_order_value']:,.0f}",          False),
            ("Revenue Recovered",          f"₹{rev:,}/month",                        True),
            ("RTO Shipping Cost Saved",    f"₹{rto_sv:,}/month",                     False),
            ("Total Value Unlocked",       f"₹{rev+rto_sv:,}/month",                True),
        ]
    }

def _sim_whatsapp(df, m):
    saved     = int(m["rto_count"]*0.08)
    rev_saved = int(saved * m["avg_order_value"])
    cod_ndr   = len(df[(df["payment_type"]=="COD")&(df["ndr_status"]=="Raised")]) \
                if "ndr_status" in df.columns else 0
    return {
        "title": "WhatsApp AI NDR — Simulation",
        "rows": [
            ("COD Shipments",              f"{m['cod_count']:,}",                    False),
            ("COD RTO Rate",               f"{cod_rto_pct:.1f}%",                   False),
            ("COD NDR Active",             f"{cod_ndr:,} shipments",                False),
            ("WhatsApp RTO Reduction",     "~8% of COD RTOs",                       False),
            ("RTOs Prevented/month",       f"{saved:,} shipments",                  False),
            ("Revenue Protected",          f"₹{rev_saved:,}/month",                 True),
            ("Best for",                   "COD orders in high-RTO states",         False),
            ("Combined with AI Calling",   "↑ total recovery to ~46%",              True),
        ]
    }

def _sim_order_confirm(df, m):
    saved     = int(m["rto_count"]*0.12)
    rev_saved = int(saved * m["avg_order_value"])
    ship_save = int(saved * 80)
    return {
        "title": "Order Confirmation Via AI — Simulation",
        "rows": [
            ("Monthly Shipments",          f"{m['total']:,}",                       False),
            ("Current RTO Rate",           f"{m['rto_pct']:.1f}%",                  False),
            ("Fake/Impulsive Orders (est.)","~12% of COD RTOs",                     False),
            ("Orders Confirmed Pre-Dispatch",f"{saved:,}/month",                    False),
            ("Forward Shipping Saved",     f"₹{ship_save:,}/month",                 False),
            ("Revenue Impact",             f"₹{rev_saved:,}/month",                 True),
            ("Best for",                   "COD orders > ₹1,000",                   False),
            ("Total with WhatsApp NDR",    f"₹{rev_saved + int(m['rto_count']*0.08*m['avg_order_value']):,}/month", True),
        ]
    }

def _seller_card(sel_name, sel_df):
    sm  = compute_kpis(sel_df)
    sm["vas_adoption_score"] = compute_vas_adoption_score(sel_df)
    sh  = compute_health_score(sm)
    sr  = get_recommendations(sm)
    risk = "Low Risk ✅" if sh>=80 else ("Medium Risk ⚠️" if sh>=65 else "High Risk 🚨")

    # Top product
    top_prod = sel_df.groupby("product_name").agg(
        total=("delivery_status","count"),
        rto  =("delivery_status",lambda x:(x=="RTO").sum()),
    ).reset_index() if "product_name" in sel_df.columns else pd.DataFrame()
    if len(top_prod)>0:
        top_prod["rto_rate"] = top_prod["rto"]/top_prod["total"]*100
        best_p  = top_prod.sort_values("total",ascending=False).iloc[0]
        worst_p = top_prod.sort_values("rto_rate",ascending=False).iloc[0]
    else:
        best_p = worst_p = None

    # Top courier
    sel_cour = compute_courier_perf(sel_df)
    best_cp  = sel_cour.sort_values("delivery_rate",ascending=False).iloc[0] if len(sel_cour)>0 else None

    lines = [
        f"**{sel_name}** — {risk} · Health **{sh:.0f}/100**\n",
        f"- Shipments: **{sm['total']:,}** | Delivered: **{sm['delivered']:,}** | RTO: **{sm['rto_count']:,}**",
        f"- Delivery: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | NDR: **{sm['ndr_count']:,}**",
        f"- COD: **{sm['cod_pct']:.1f}%** | Avg Order: **₹{sm['avg_order_value']:,.0f}**",
    ]
    if best_p is not None:
        lines.append(f"- Top Product: **{best_p['product_name']}** ({best_p['total']:,} orders)")
    if worst_p is not None and len(top_prod)>1:
        lines.append(f"- Highest RTO Product: **{worst_p['product_name']}** ({worst_p['rto_rate']:.1f}% RTO)")
    if best_cp is not None:
        lines.append(f"- Best Courier for this seller: **{best_cp['courier']}** ({best_cp['delivery_rate']:.1f}% delivery)")
    if sr:
        lines.append(f"\n**GDI Recommends:**")
        for r in sr[:3]:
            lines.append(f"- **{r['name']}**: {r['impact']} → **₹{r['revenue']:,} unlock**")
    else:
        lines.append(f"\n✅ Operations look healthy for {sel_name}.")
    return "\n".join(lines)


# ══════════════════════════════════════════════════════════════════════════════
# CLAUDE API (if key available)
# ══════════════════════════════════════════════════════════════════════════════

def _get_api_key():
    if st.session_state.get("anthropic_api_key"): return st.session_state["anthropic_api_key"]
    try:    return st.secrets.get("ANTHROPIC_API_KEY","")
    except: return os.environ.get("ANTHROPIC_API_KEY","")

def _build_context():
    lines = [
        f"=== VELOCITY GDI — SHIPMENT DATA ===",
        f"Total: {m_all['total']:,} | Delivery: {m_all['delivery_pct']:.1f}% | RTO: {m_all['rto_pct']:.1f}% | NDR: {m_all['ndr_count']:,}",
        f"COD: {m_all['cod_pct']:.1f}% | COD-RTO: {cod_rto_pct:.1f}% | Prepaid-RTO: {prep_rto_pct:.1f}% | Avg Order: ₹{m_all['avg_order_value']:,.0f}",
        f"Health Score: {hs_all:.0f}/100",
        "",
        "SELLERS:",
    ]
    sg = df_full.groupby("seller_name").agg(
        total=("delivery_status","count"),
        delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
        rto=("delivery_status",lambda x:(x=="RTO").sum()),
    ).reset_index()
    sg["dr"] = sg["delivered"]/sg["total"]*100
    sg["rr"] = sg["rto"]/sg["total"]*100
    for _,row in sg.iterrows():
        lines.append(f"  {row['seller_name']}: {row['total']:,} shpts | delivery={row['dr']:.1f}% | RTO={row['rr']:.1f}%")
    lines += ["","COURIERS:"]
    for _,row in cour_df.iterrows():
        lines.append(f"  {row['courier']}: {row['total']:,} | delivery={row['delivery_rate']:.1f}% | RTO={row['rto_rate']:.1f}%")
    lines += ["","TOP STATES BY RTO:"]
    for _,row in state_df.sort_values("rto_rate",ascending=False).head(6).iterrows():
        lines.append(f"  {row['state']}: RTO={row['rto_rate']:.1f}% ({row['total']:,} shpts)")
    if "product_name" in df_full.columns:
        lines += ["","TOP PRODUCTS:"]
        tp = df_full.groupby("product_name").agg(total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum())).reset_index()
        tp["rr"]=tp["rto"]/tp["total"]*100
        for _,row in tp.sort_values("total",ascending=False).head(8).iterrows():
            lines.append(f"  {row['product_name']}: {row['total']:,} orders | RTO={row['rr']:.1f}%")
    lines += ["","VAS PRODUCTS (Velocity Shipping):","  AI Calling: 38% NDR recovery","  Order Confirmation Via AI: 12% RTO reduction pre-dispatch","  WhatsApp AI NDR: 8% COD RTO reduction","  ATS Address Verification: 4-6% RTO reduction at checkout"]
    lines += ["","GDI GOAL: Reduce RTO, Improve Delivery%, Improve Product Quality Insights, Best Seller Insights"]
    return "\n".join(lines)

def _claude_reply(q, api_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        ctx = _build_context()
        system = f"""You are GDI Agent — Velocity Shipping's AI consultant. Goal: reduce RTO, improve delivery %, give sellers best insights on products, customer locations, courier allocation, and VAS benefits.

Data context:
{ctx}

Rules:
- Answer using ONLY the numbers from the data above
- For VAS questions, always show specific numbers (NDR count, expected recovery, revenue impact)
- For seller questions, give their specific metrics + top products + courier recommendation
- For product questions, give RTO%, delivery%, and which state/courier causes the most issues
- Format with **bold** for key numbers, use bullet points
- End with 1-2 specific action recommendations
- Keep under 200 words"""
        resp = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=500,
            system=system, messages=[{"role":"user","content":q}])
        return resp.content[0].text
    except Exception:
        return None


# ══════════════════════════════════════════════════════════════════════════════
# MAIN REPLY ENGINE
# ══════════════════════════════════════════════════════════════════════════════

def reply(q):
    ql  = q.lower().strip()
    qw  = _words(ql)
    chart = None
    sim   = None

    def has(*phrases):   return any(p in ql for p in phrases)
    def hasw(*words_):   return any(w in qw for w in words_)

    mentioned_seller  = _find(ql, all_sellers)
    mentioned_courier = _find(ql, cour_df["courier"].tolist() if len(cour_df)>0 else [])
    mentioned_state   = _find(ql, state_df["state"].tolist()  if len(state_df)>0 else [])
    mentioned_product = _find(ql, df_full["product_name"].unique().tolist()) if "product_name" in df_full.columns else None

    # ── AI Calling Simulation ─────────────────────────────────────────────────
    if has("ai calling","simulate calling","calling benefit","ndr recovery","ivr") \
       or (hasw("calling","call") and hasw("simulate","benefit","impact","help","if","what","how much")):
        sim = _sim_ai_calling(df_full, m_all)
        stale = len(df_full[(df_full.get("ndr_status","")=="Raised") & (df_full.get("ndr_age_hours",0)>48)]) \
                if ("ndr_status" in df_full.columns and "ndr_age_hours" in df_full.columns) else 0
        rec = int(m_all["ndr_count"]*0.38)
        text = (f"**AI Calling — Here's your simulation:**\n\n"
                f"You have **{m_all['ndr_count']:,} active NDRs** ({m_all['ndr_pct']:.1f}% of volume).\n"
                f"Of these, **{stale}** are stale >48h and at high risk of becoming RTOs.\n\n"
                f"AI Calling will prioritise the highest-recovery shipments first (by state + NDR reason).\n"
                f"At 38% recovery rate → **{rec:,} shipments recovered → ₹{int(rec*m_all['avg_order_value']):,}/month**.\n\n"
                f"See simulation card below 👇")
        return text, ["Simulate WhatsApp NDR","Simulate Order Confirmation","Which NDRs to call first?"], chart, sim

    # ── WhatsApp NDR Simulation ───────────────────────────────────────────────
    if has("whatsapp","whats app","wa ndr","simulate whatsapp") \
       or (hasw("whatsapp","wa") and hasw("simulate","benefit","impact","help","if")):
        sim = _sim_whatsapp(df_full, m_all)
        saved = int(m_all["rto_count"]*0.08)
        text  = (f"**WhatsApp AI NDR — Simulation:**\n\n"
                 f"Your COD share is **{m_all['cod_pct']:.1f}%** ({m_all['cod_count']:,} shipments) "
                 f"with COD-RTO at **{cod_rto_pct:.1f}%** vs Prepaid at **{prep_rto_pct:.1f}%**.\n\n"
                 f"WhatsApp AI NDR reduces COD RTO by ~**8%** → saves **{saved:,} shipments/month** "
                 f"→ **₹{int(saved*m_all['avg_order_value']):,}/month** revenue protected.\n\n"
                 f"Most effective in: **{worst_st['state'] if worst_st is not None else 'high-RTO states'}** "
                 f"and for COD orders under ₹1,000.")
        return text, ["Simulate AI Calling","Simulate Order Confirmation","COD vs Prepaid breakdown"], chart, sim

    # ── Order Confirmation Simulation ─────────────────────────────────────────
    if has("order confirm","confirmation","pre-dispatch","simulate confirm","bogus","fake order") \
       or (hasw("confirm","confirmation","fake","bogus") and hasw("simulate","order","dispatch")):
        sim = _sim_order_confirm(df_full, m_all)
        saved = int(m_all["rto_count"]*0.12)
        text  = (f"**Order Confirmation Via AI — Simulation:**\n\n"
                 f"Your RTO rate is **{m_all['rto_pct']:.1f}%**. "
                 f"Approx 12% of RTOs are from fake/impulsive COD orders that could be caught pre-dispatch.\n\n"
                 f"Order Confirmation Via AI calls buyers BEFORE shipment → confirms address, intent, and slot.\n"
                 f"Expected prevention: **{saved:,} RTOs/month** → **₹{int(saved*m_all['avg_order_value']):,}/month**.\n\n"
                 f"Best combined with **WhatsApp AI NDR** for end-to-end COD protection.")
        return text, ["Simulate WhatsApp NDR","Simulate AI Calling","Show RTO causes"], chart, sim

    # ── Seller specific ───────────────────────────────────────────────────────
    if mentioned_seller:
        sel_df = df_full[df_full["seller_name"]==mentioned_seller]
        text   = _seller_card(mentioned_seller, sel_df)
        sp     = compute_sku_perf(sel_df).head(6)
        if len(sp)>0:
            chart = _chart("h", x=sp["product_name"], y=sp["rto_rate"],
                title=f"{mentioned_seller} — RTO % by Product",
                color="#F87171", xlabel="RTO %")
        return text, ["Simulate AI Calling for this seller","Top products for "+mentioned_seller,
                      "Compare all sellers"], chart, None

    # ── All sellers comparison ────────────────────────────────────────────────
    if has("all seller","compare seller","seller list","every seller","all client","compare client") \
       or (hasw("seller","client") and hasw("compare","all","list","rank","who","which")):
        sg = df_full.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
        ).reset_index()
        sg["delivery_rate"] = sg["delivered"]/sg["total"]*100
        sg["rto_rate"]      = sg["rto"]/sg["total"]*100
        sg = sg.sort_values("delivery_rate",ascending=False)
        chart = _chart("h", x=sg["seller_name"], y=sg["delivery_rate"],
            title="Seller Delivery Rate (%)", color="#34D399", xlabel="Delivery %")
        best_s=sg.iloc[0]; worst_s=sg.iloc[-1]
        text = f"**{len(sg)} Sellers — Delivery Comparison:**\n\n"
        text += f"🏆 Best: **{best_s['seller_name']}** — {best_s['delivery_rate']:.1f}% delivery\n"
        text += f"⚠️ Needs help: **{worst_s['seller_name']}** — {worst_s['delivery_rate']:.1f}% delivery, {worst_s['rto_rate']:.1f}% RTO\n\n"
        for _,row in sg.iterrows():
            e = "✅" if row["delivery_rate"]>=80 else ("⚠️" if row["delivery_rate"]>=65 else "🚨")
            text += f"{e} **{row['seller_name']}** — {row['delivery_rate']:.1f}% del, {row['rto_rate']:.1f}% RTO ({row['total']:,} shpts)\n"
        return text, [f"Tell me about {worst_s['seller_name']}","Simulate AI Calling",
                      "Which seller needs WhatsApp NDR?"], chart, None

    # ── Top selling products ──────────────────────────────────────────────────
    if has("top selling","best selling","most sold","top product","popular") \
       or (hasw("top","best","popular") and hasw("product","sku","item","selling")):
        grp = df_full.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index()
        grp["del_rate"] = grp["delivered"]/grp["total"]*100
        top10 = grp.sort_values("delivered",ascending=False).head(10)
        chart = _chart("v", x=top10["product_name"], y=top10["delivered"],
            title="Top 10 Products — Delivered Units", color="#818CF8", ylabel="Units Delivered")
        text = "**Top Selling Products:**\n\n"
        for _,row in top10.head(5).iterrows():
            text += f"- **{row['product_name']}** — {row['delivered']:,} delivered | {row['del_rate']:.0f}% rate | ₹{row['revenue']:,.0f}\n"
        text += f"\n{len(grp)} products total. Chart shows top 10 👇"
        return text, ["Which product has highest RTO?","Show pricing band analysis",
                      "Show worst performing product"], chart, None

    # ── Specific product ─────────────────────────────────────────────────────
    if mentioned_product:
        p_df = df_full[df_full["product_name"]==mentioned_product]
        pm   = compute_kpis(p_df)
        # State breakdown for this product
        if "state" in p_df.columns:
            ps = p_df.groupby("state").agg(
                total=("delivery_status","count"),
                rto  =("delivery_status",lambda x:(x=="RTO").sum()),
            ).reset_index()
            ps["rto_rate"] = ps["rto"]/ps["total"].clip(lower=1)*100
            worst_state_prod = ps.sort_values("rto_rate",ascending=False).iloc[0] if len(ps)>0 else None
        else: worst_state_prod=None
        text = (f"**{mentioned_product}:**\n\n"
                f"- Total orders: **{pm['total']:,}** | Delivered: **{pm['delivered']:,}** ({pm['delivery_pct']:.1f}%)\n"
                f"- RTO: **{pm['rto_count']:,}** ({pm['rto_pct']:.1f}%) | NDR: **{pm['ndr_count']:,}**\n"
                f"- COD Share: **{pm['cod_pct']:.1f}%** | Avg Value: **₹{pm['avg_order_value']:,.0f}**\n")
        if worst_state_prod is not None:
            text += f"- Worst state: **{worst_state_prod['state']}** ({worst_state_prod['rto_rate']:.1f}% RTO)\n"
        if pm["rto_pct"] > m_all["rto_pct"]*1.3:
            text += (f"\n⚠️ RTO is **{pm['rto_pct']/max(m_all['rto_pct'],1):.1f}x** above average.\n"
                     f"**Fix:** Restrict COD in {worst_state_prod['state'] if worst_state_prod is not None else 'high-risk states'} + activate Order Confirmation Via AI.")
        else:
            text += "\n✅ Performing within normal range."
        return text, ["Show top selling products","Simulate Order Confirmation",
                      "Which state has worst RTO for this product?"], None, None

    # ── Specific courier ─────────────────────────────────────────────────────
    if mentioned_courier:
        cr = cour_df[cour_df["courier"]==mentioned_courier]
        if len(cr)>0:
            row = cr.iloc[0]
            vs  = row["delivery_rate"] - m_all["delivery_pct"]
            dir_= "above" if vs>=0 else "below"
            # State performance for this courier
            if "state" in df_full.columns:
                cs = df_full[df_full["courier"]==mentioned_courier].groupby("state").agg(
                    total=("delivery_status","count"),
                    del_=("delivery_status",lambda x:(x=="Delivered").sum()),
                ).reset_index()
                cs["dr"] = cs["del_"]/cs["total"]*100
                best_state_c = cs.sort_values("dr",ascending=False).iloc[0] if len(cs)>0 else None
            else: best_state_c=None
            text = (f"**{mentioned_courier}:**\n\n"
                    f"- Shipments: **{row['total']:,}** | Delivery: **{row['delivery_rate']:.1f}%** ({abs(vs):.1f}% {dir_} avg)\n"
                    f"- RTO: **{row['rto_rate']:.1f}%**\n")
            if best_state_c is not None:
                text += f"- Best state for this courier: **{best_state_c['state']}** ({best_state_c['dr']:.1f}%)\n"
            text += ("\n⚠️ Underperforming. Reduce volume and route to better couriers."
                     if row["delivery_rate"]<m_all["delivery_pct"]-5
                     else f"\n✅ Performing well. Good for routing.")
        else:
            text = f"No data for {mentioned_courier} in current filter."
        chart = _chart("h", x=cour_df["courier"], y=cour_df["delivery_rate"],
            title="All Courier Delivery Rates (%)", color="#60A5FA", xlabel="Delivery %")
        return text, ["Compare all couriers","Which courier is best for COD?",
                      "Show 3PL performance"], chart, None

    # ── All couriers / 3PL ────────────────────────────────────────────────────
    if has("courier","3pl","carrier","logistic") or hasw("couriers","carriers","3pl"):
        chart = _chart("h", x=cour_df["courier"], y=cour_df["delivery_rate"],
            title="Courier Delivery Rates (%)", color="#60A5FA", xlabel="Delivery %")
        text = f"**Courier Performance — {len(cour_df)} partners:**\n\n"
        for _,row in cour_df.sort_values("delivery_rate",ascending=False).iterrows():
            e = "✅" if row["delivery_rate"]>=80 else ("⚠️" if row["delivery_rate"]>=70 else "🚨")
            text += f"{e} **{row['courier']}** — {row['delivery_rate']:.1f}% delivery, {row['rto_rate']:.1f}% RTO ({row['total']:,} shpts)\n"
        if best_c: text += f"\n**Recommended:** Route more to **{best_c['courier']}**."
        if worst_c: text += f" Reduce **{worst_c['courier']}** volume."
        return text, [f"Tell me about {best_c['courier'] if best_c else 'top courier'}",
                      "Best courier for COD?","Simulate Smart Routing benefit"], chart, None

    # ── State / Location ─────────────────────────────────────────────────────
    if mentioned_state:
        sr2 = state_df[state_df["state"]==mentioned_state]
        if len(sr2)>0:
            row=sr2.iloc[0]; share=row["rto"]/max(m_all["rto_count"],1)*100
            text=(f"**{mentioned_state}:**\n\n"
                  f"- Shipments: **{row['total']:,}** | RTO: **{row['rto_rate']:.1f}%** ({share:.0f}% of all RTOs)\n"
                  f"- Delivery: **{row['delivery_rate']:.1f}%**\n\n")
            if row["rto_rate"]>30:
                text+=(f"🚨 High-risk zone. Address quality + COD non-acceptance are primary drivers.\n"
                       f"**Fix:** ATS Address Verification + AI Calling for {mentioned_state} NDRs.")
            elif row["rto_rate"]>20: text+=f"⚠️ Restrict COD for low-value orders in {mentioned_state}."
            else: text+=f"✅ Within acceptable range."
        else: text=f"No data for {mentioned_state} in current filter."
        return text, ["Worst states by RTO","Best courier for this state","Restrict COD in high-risk states"], None, None

    if has("state","region","location","geography","zone","geographic") \
       or (hasw("state","location","region") and hasw("rto","delivery","worst","best")):
        top8 = state_df.sort_values("rto_rate",ascending=False).head(8)
        chart = _chart("h", x=top8["state"], y=top8["rto_rate"],
            title="Worst States by RTO %", color="#F87171", xlabel="RTO %")
        text = "**Geographic RTO Analysis:**\n\n"
        for _,row in top8.iterrows():
            e="🚨" if row["rto_rate"]>30 else ("⚠️" if row["rto_rate"]>20 else "✅")
            text+=f"{e} **{row['state']}** — {row['rto_rate']:.1f}% RTO ({row['total']:,} shpts)\n"
        if worst_st:
            share=worst_st["rto"]/max(m_all["rto_count"],1)*100
            text+=f"\n**{worst_st['state']}** is biggest hotspot — {share:.0f}% of all RTOs."
        return text, ["Tell me about Bihar","Tell me about Uttar Pradesh",
                      "Best courier for high-RTO states"], chart, None

    # ── RTO causes / reduce RTO ───────────────────────────────────────────────
    if has("rto","high rto","reduce rto","return","why rto") \
       or (hasw("rto","return") and hasw("why","high","cause","reason","reduce","improve")):
        causes=[]
        if worst_c and worst_c["delivery_rate"]<75:
            causes.append(f"**{worst_c['courier']}** delivers only {worst_c['delivery_rate']:.1f}% ({worst_c['total']:,} shpts)")
        if worst_st and worst_st["rto_rate"]>25:
            causes.append(f"**{worst_st['state']}** — {worst_st['rto_rate']:.1f}% RTO, {worst_st['rto']/max(m_all['rto_count'],1)*100:.0f}% of all RTOs")
        if m_all["cod_pct"]>60:
            causes.append(f"**{m_all['cod_pct']:.0f}% COD share** — {cod_rto_pct:.1f}% COD-RTO vs {prep_rto_pct:.1f}% Prepaid-RTO")
        text=(f"**RTO Root Cause Analysis — {m_all['rto_pct']:.1f}% RTO:**\n\n"
              +"\n".join(f"- {c}" for c in causes)+
              f"\n\n**3-step fix:**\n"
              f"1. Order Confirmation Via AI → filter fake orders pre-dispatch\n"
              f"2. ATS Address Verification → fix address-driven RTO at checkout\n"
              f"3. WhatsApp AI NDR → recover COD delivery failures\n"
              f"Expected RTO improvement: **-8 to -12%**")
        chart=_chart("h", x=state_df.sort_values("rto_rate",ascending=False).head(6)["state"],
            y=state_df.sort_values("rto_rate",ascending=False).head(6)["rto_rate"],
            title="Top States Contributing to RTO", color="#F87171", xlabel="RTO %")
        return text, ["Simulate Order Confirmation","Simulate WhatsApp NDR",
                      "Which courier reduces RTO most?"], chart, None

    # ── COD / payment ─────────────────────────────────────────────────────────
    if has("cod","prepaid","payment","cash on delivery") \
       or (hasw("cod","prepaid","payment") and hasw("rate","analysis","breakdown","rto")):
        diff=cod_rto_pct-prep_rto_pct
        text=(f"**COD vs Prepaid:**\n\n"
              f"- COD: **{m_all['cod_pct']:.1f}%** ({m_all['cod_count']:,} shpts) | COD-RTO: **{cod_rto_pct:.1f}%**\n"
              f"- Prepaid: **{100-m_all['cod_pct']:.1f}%** | Prepaid-RTO: **{prep_rto_pct:.1f}%**\n"
              f"- Premium: **+{diff:.1f}%** extra RTO for COD orders\n\n")
        if m_all["cod_pct"]>60:
            text+=("🚨 High COD risk. Activate:\n"
                   "1. **WhatsApp AI NDR** → recover failed COD deliveries (+8%)\n"
                   "2. **Order Confirmation Via AI** → filter fake COD orders pre-dispatch\n"
                   "3. Restrict COD for high-risk states + orders < ₹500")
        return text, ["Simulate WhatsApp NDR","Simulate Order Confirmation",
                      "Which states have worst COD RTO?"], None, None

    # ── Health / summary ──────────────────────────────────────────────────────
    if has("health","score","overall","summary","how am i","status") \
       or (hasw("health","score","overall") and hasw("doing","am","is","my","our")):
        risk="Low Risk ✅" if hs_all>=80 else ("Medium Risk ⚠️" if hs_all>=65 else "High Risk 🚨")
        fixes=[]
        if m_all["rto_pct"]>20:   fixes.append(f"RTO {m_all['rto_pct']:.0f}% — activate Order Confirmation + Address Verification")
        if m_all["ndr_pct"]>15:   fixes.append(f"NDR backlog {m_all['ndr_count']:,} — activate AI Calling now")
        if m_all["cod_pct"]>60:   fixes.append(f"COD {m_all['cod_pct']:.0f}% — activate WhatsApp AI NDR")
        if not fixes: fixes=["No critical issues. Keep monitoring."]
        text=(f"**Health: {hs_all:.0f}/100 — {risk}**\n\n"
              f"- Delivery: **{m_all['delivery_pct']:.1f}%** | RTO: **{m_all['rto_pct']:.1f}%** | NDR: **{m_all['ndr_count']:,}**\n"
              f"- COD: **{m_all['cod_pct']:.1f}%** | Shipments: **{m_all['total']:,}**\n\n"
              f"**Priority actions:**\n"+"\n".join(f"- {f}" for f in fixes))
        return text, ["Simulate AI Calling","Compare all sellers","Show RTO causes",
                      "Show me the full action plan"], None, None

    # ── Action plan / improve ────────────────────────────────────────────────
    if has("action plan","30 day","roadmap","improve","what should","help me","advice") \
       or (hasw("improve","fix","plan","action","should","help") and hasw("do","me","my","our","delivery","rto")):
        steps=[]
        if m_all["delivery_pct"]<80 and best_c:
            steps.append(f"1. **Route more to {best_c['courier']}** ({best_c['delivery_rate']:.1f}% delivery) — reduce {worst_c['courier'] if worst_c else 'weakest courier'} share")
        if m_all["rto_pct"]>20:
            steps.append("2. **Activate Order Confirmation Via AI** — stop fake COD orders before dispatch")
            steps.append("3. **Enable ATS Address Verification** — fix address RTOs at checkout")
        if m_all["ndr_pct"]>15:
            steps.append("4. **Launch AI Calling** — recover 38% of NDR shipments with IVR outreach")
        if m_all["cod_pct"]>60:
            steps.append("5. **Activate WhatsApp AI NDR** — protect COD deliveries, reduce COD RTO 8%")
        if not steps: steps=["1. VAS stack is healthy. Expand to new pincodes with your best courier."]
        total=sum(r["revenue"] for r in recs_all)
        text=("**Your GDI 30-Day Action Plan:**\n\n"+"\n".join(steps)+
              f"\n\n💰 Total VAS revenue unlock: **₹{total:,}**\n"
              f"📈 Expected health score improvement: **+12–18 points**")
        return text, ["Simulate AI Calling","Simulate WhatsApp NDR",
                      "Simulate Order Confirmation","Show seller breakdown"], None, None

    # ── NDR ───────────────────────────────────────────────────────────────────
    if has("ndr","non delivery","undelivered","not delivered","failed delivery") or hasw("ndr","undelivered"):
        stale=0
        if "ndr_status" in df_full.columns and "ndr_age_hours" in df_full.columns:
            stale=len(df_full[(df_full["ndr_status"]=="Raised")&(df_full["ndr_age_hours"]>48)])
        rec=int(m_all["ndr_count"]*0.38)
        text=(f"**NDR Analysis:**\n\n"
              f"- Total NDR: **{m_all['ndr_count']:,}** ({m_all['ndr_pct']:.1f}%)\n"
              f"- Stale >48h: **{stale}** — high risk of becoming RTO\n"
              f"- AI Calling recovery: **{rec:,} shipments** → ₹{int(rec*m_all['avg_order_value']):,}\n"
              f"- WhatsApp NDR: additional **8% COD RTO** protection\n\n"
              f"**Action:** Launch AI Calling for stale NDRs immediately.")
        sim=_sim_ai_calling(df_full, m_all)
        return text, ["Simulate AI Calling","Simulate WhatsApp NDR","Show NDR by state"], None, sim

    # ── Default / fallback ────────────────────────────────────────────────────
    mode=f"{len(all_sellers)} sellers loaded" if is_admin else (all_sellers[0] if all_sellers else "your data")
    text=(f"I have **{m_all['total']:,} shipments** analysed ({mode}).\n\n"
          f"- Delivery: **{m_all['delivery_pct']:.1f}%** | RTO: **{m_all['rto_pct']:.1f}%** | NDR: **{m_all['ndr_count']:,}**\n"
          f"- Health Score: **{hs_all:.0f}/100** | COD: **{m_all['cod_pct']:.1f}%**\n\n"
          f"**I can help you with:**\n"
          f"- *Simulations* — 'Simulate AI Calling', 'Simulate WhatsApp NDR', 'Simulate Order Confirmation'\n"
          f"- *Seller analysis* — 'Tell me about [seller name]' or 'Compare all sellers'\n"
          f"- *Product insights* — 'Top selling products', 'Which product has highest RTO?'\n"
          f"- *Courier allocation* — 'Which courier is best?', 'Tell me about Delhivery'\n"
          f"- *Location strategy* — 'Which state has worst RTO?', 'Tell me about Bihar'\n"
          f"- *RTO reduction plan* — 'Why is RTO high?', 'Give me an action plan'")
    return text, ["Simulate AI Calling","Simulate WhatsApp NDR","Compare all sellers",
                  "Top selling products","Why is RTO high?","Give me action plan"], None, None


# ══════════════════════════════════════════════════════════════════════════════
# UNIFIED REPLY (Claude → keyword fallback)
# ══════════════════════════════════════════════════════════════════════════════

def ask(q):
    api_key = _get_api_key()
    text, chips, chart, sim = reply(q)

    if api_key and len(api_key)>20 and sim is None:
        ai_text = _claude_reply(q, api_key)
        if ai_text:
            return ai_text, chips, chart, sim

    return text, chips, chart, sim


# ══════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ══════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🤖 Ask GDI Agent</h1>
  <p class="header-subtitle">Your AI Delivery Consultant — simulates VAS impact, analyses every seller, product & courier from your real data.</p>
</div>""", unsafe_allow_html=True)

# API key in sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("<div style='color:#9CA3AF;font-size:0.73rem;font-weight:600;text-transform:uppercase;'>🔑 Claude AI (Optional)</div>", unsafe_allow_html=True)
    api_in = st.text_input("Anthropic API Key",type="password",placeholder="sk-ant-...",
                           help="Get free key at console.anthropic.com",label_visibility="collapsed")
    if api_in:
        st.session_state["anthropic_api_key"] = api_in
        st.success("✅ Claude AI active")
    elif st.session_state.get("anthropic_api_key"):
        st.success("✅ Claude AI active")
    else:
        st.caption("Smart keyword mode active")

# Stats bar
rc = "#34D399" if hs_all>=80 else ("#FBBF24" if hs_all>=65 else "#F87171")
st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-radius:12px;
     padding:14px 20px;margin-bottom:16px;display:flex;gap:24px;align-items:center;flex-wrap:wrap;">
  <div><div style="font-size:1.3rem;font-weight:800;color:{rc};">{hs_all:.0f}/100</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">Health</div></div>
  <div style="width:1px;background:#1F2937;height:32px;"></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#34D399;">{m_all['delivery_pct']:.1f}%</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">Delivery</div></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#F87171;">{m_all['rto_pct']:.1f}%</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">RTO</div></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#FBBF24;">{m_all['ndr_count']:,}</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">NDR Active</div></div>
  <div style="width:1px;background:#1F2937;height:32px;"></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#60A5FA;">{m_all['total']:,}</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">Shipments</div></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#C084FC;">{len(all_sellers)}</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">Sellers</div></div>
  <div><div style="font-size:1.3rem;font-weight:800;color:#818CF8;">{len(cour_df)}</div>
       <div style="font-size:0.7rem;color:#6B7280;text-transform:uppercase;">Couriers</div></div>
</div>""", unsafe_allow_html=True)

# Quick chips
quick = ["Simulate AI Calling","Simulate WhatsApp NDR","Simulate Order Confirmation",
         "Compare all sellers","Top selling products","Why is RTO high?",
         "Show courier performance","Give me action plan"]
qc = st.columns(4)
sel_q = None
for i,qq in enumerate(quick):
    if qc[i%4].button(qq,key=f"qb_{i}",use_container_width=True): sel_q=qq

# Init chat
if "gdi_chat" not in st.session_state:
    ws = worst_st["state"] if worst_st else "N/A"
    wr = f"{worst_st['rto_rate']:.0f}%" if worst_st else "N/A"
    opener=(f"I've analysed **{m_all['total']:,} shipments** across **{len(all_sellers)} sellers** & **{len(cour_df)} couriers**.\n\n"
            f"Health Score: **{hs_all:.0f}/100** · Delivery: **{m_all['delivery_pct']:.1f}%** · "
            f"RTO: **{m_all['rto_pct']:.1f}%** · NDR Queue: **{m_all['ndr_count']:,}**\n\n"
            f"Biggest RTO hotspot: **{ws}** at {wr}. "
            f"AI Calling can recover **~{int(m_all['ndr_count']*0.38):,} NDR shipments**.\n\n"
            f"Ask me to **simulate AI Calling, WhatsApp NDR, or Order Confirmation** — "
            f"or ask about any seller, product, or courier.")
    st.session_state["gdi_chat"]=[{"role":"assistant","content":opener,
        "chips":["Simulate AI Calling","Simulate WhatsApp NDR","Compare all sellers","Top selling products"],
        "chart":None,"sim":None}]

# Render chat
for msg in st.session_state["gdi_chat"]:
    if msg["role"]=="user":
        st.markdown('<div class="user-lbl">You</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="agent-lbl">🤖 GDI Agent</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("sim"):   _render_sim(msg["sim"])
        if msg.get("chart"): _render_chart(msg["chart"])
        if msg.get("chips"):
            st.markdown("".join(f'<span class="qchip">{c}</span>' for c in msg["chips"]),
                        unsafe_allow_html=True)

# Input
user_input = st.chat_input("Ask about simulations, sellers, products, couriers, RTO, NDR…")
if sel_q or user_input:
    prompt = sel_q or user_input
    st.session_state["gdi_chat"].append({"role":"user","content":prompt,"chips":None,"chart":None,"sim":None})
    text, chips, chart, sim = ask(prompt)
    st.session_state["gdi_chat"].append({"role":"assistant","content":text,"chips":chips,"chart":chart,"sim":sim})
    st.rerun()

if st.button("🗑 Clear Chat"):
    del st.session_state["gdi_chat"]
    st.rerun()
