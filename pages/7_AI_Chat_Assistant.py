import streamlit as st
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

st.markdown("""
<style>
.agent-lbl{color:#818CF8;font-size:0.75rem;font-weight:700;text-transform:uppercase;
           letter-spacing:0.06em;margin-bottom:3px;}
.user-lbl{text-align:right;color:#6B7280;font-size:0.75rem;font-weight:600;margin-bottom:3px;}
.sim-card{background:#0B0F19;border:1px solid rgba(79,70,229,0.5);border-radius:12px;
          padding:18px 22px;margin:8px 0 14px;}
.sim-row{display:flex;justify-content:space-between;padding:8px 0;
         border-bottom:1px solid #1F2937;font-size:0.85rem;}
.sim-row:last-child{border-bottom:none;padding-top:10px;}
.qchip{display:inline-block;background:rgba(79,70,229,0.10);color:#818CF8;
       border:1px solid rgba(79,70,229,0.25);padding:5px 12px;border-radius:99px;
       font-size:0.78rem;font-weight:600;margin:3px 3px 0 0;}
</style>""", unsafe_allow_html=True)

# ── load data ─────────────────────────────────────────────────────────────────
try:
    df = render_sidebar_and_get_data()
except Exception as e:
    st.error(f"Data load error: {e}")
    st.stop()

# ── precompute ────────────────────────────────────────────────────────────────
m           = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs          = compute_health_score(m)
recs        = get_recommendations(m)
cour_df     = compute_courier_perf(df)
state_df    = compute_state_perf(df)
all_sellers = sorted(df["seller_name"].unique().tolist()) if "seller_name" in df.columns else []
is_admin    = len(all_sellers) > 1

cod_df   = df[df["payment_type"]=="COD"]
prep_df  = df[df["payment_type"]=="Prepaid"]
cod_rto  = len(cod_df[cod_df["delivery_status"]=="RTO"])   / max(len(cod_df),1)  * 100
prep_rto = len(prep_df[prep_df["delivery_status"]=="RTO"]) / max(len(prep_df),1) * 100
best_c   = cour_df.sort_values("delivery_rate",ascending=False).iloc[0] if len(cour_df)>0 else None
worst_c  = cour_df.sort_values("delivery_rate").iloc[0]                 if len(cour_df)>0 else None
worst_st = state_df.sort_values("rto_rate",ascending=False).iloc[0]    if len(state_df)>0 else None


# ════════════════════════════════════════════════════════════════════════════
# RENDER HELPERS
# ════════════════════════════════════════════════════════════════════════════

def _render_sim(sim):
    if not sim: return
    rows_html = "".join(
        f'<div class="sim-row">'
        f'<span style="color:#9CA3AF;">{r[0]}</span>'
        f'<span style="color:{"#34D399" if r[2] else "#FFFFFF"};font-weight:{"800" if r[2] else "600"};">{r[1]}</span>'
        f'</div>'
        for r in sim["rows"]
    )
    st.markdown(f'<div class="sim-card"><div style="color:#818CF8;font-weight:800;font-size:0.95rem;margin-bottom:12px;">📊 {sim["title"]}</div>{rows_html}</div>', unsafe_allow_html=True)

def _render_chart(c):
    if not c: return
    try:
        if c.get("orient") == "h":
            fig = go.Figure(go.Bar(x=c["y"], y=c["x"], orientation="h",
                marker_color=c["color"], text=[f"{v:.1f}" for v in c["y"]], textposition="auto"))
            fig.update_layout(yaxis=dict(autorange="reversed"))
        else:
            fig = go.Figure(go.Bar(x=c["x"], y=c["y"], marker_color=c["color"],
                text=[f"{v:,.0f}" if v > 10 else f"{v:.1f}" for v in c["y"]], textposition="auto"))
        fig.update_layout(
            title=dict(text=c.get("title",""), font=dict(color="#FFFFFF", size=13)),
            paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
            font_color="#F3F4F6", height=280, showlegend=False,
            margin=dict(l=0, r=0, t=40, b=0),
            xaxis=dict(showgrid=False), yaxis=dict(gridcolor="#1F2937"),
        )
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        pass


# ════════════════════════════════════════════════════════════════════════════
# SIMULATIONS
# ════════════════════════════════════════════════════════════════════════════

def _sim_calling():
    rec = int(m["ndr_count"] * 0.38)
    rev = int(rec * m["avg_order_value"])
    return {"title": "AI Calling — NDR Recovery Simulation", "rows": [
        ("NDR Queue (active)",          f"{m['ndr_count']:,} shipments",         False),
        ("AI Calling Recovery Rate",    "38%  (industry benchmark)",             False),
        ("Shipments Recovered / month", f"{rec:,}",                              False),
        ("Avg Order Value",             f"₹{m['avg_order_value']:,.0f}",         False),
        ("Revenue Recovered / month",   f"₹{rev:,}",                            True),
        ("RTO Shipping Cost Saved",     f"₹{int(m['ndr_count']*0.15*80):,}",    False),
        ("Total Value Unlocked",        f"₹{rev + int(m['ndr_count']*0.15*80):,}/month", True),
    ]}

def _sim_whatsapp():
    saved = int(m["rto_count"] * 0.08)
    rev   = int(saved * m["avg_order_value"])
    return {"title": "WhatsApp AI NDR — Simulation", "rows": [
        ("COD Shipments",               f"{m['cod_count']:,}",                   False),
        ("COD RTO Rate",                f"{cod_rto:.1f}%",                       False),
        ("WhatsApp RTO Reduction",      "~8% of COD RTOs",                       False),
        ("RTOs Prevented / month",      f"{saved:,} shipments",                  False),
        ("Revenue Protected / month",   f"₹{rev:,}",                            True),
        ("Combined with AI Calling",    "Total recovery rises to ~46%",          True),
    ]}

def _sim_order_confirm():
    saved = int(m["rto_count"] * 0.12)
    rev   = int(saved * m["avg_order_value"])
    return {"title": "Order Confirmation Via AI — Simulation", "rows": [
        ("Monthly Shipments",           f"{m['total']:,}",                       False),
        ("Current RTO Rate",            f"{m['rto_pct']:.1f}%",                  False),
        ("Fake / Impulsive COD Orders", "~12% of RTOs (pre-dispatch filter)",    False),
        ("Orders Saved / month",        f"{saved:,}",                            False),
        ("Revenue Impact / month",      f"₹{rev:,}",                            True),
        ("With WhatsApp NDR",           f"₹{rev + int(m['rto_count']*0.08*m['avg_order_value']):,}/month", True),
    ]}


# ════════════════════════════════════════════════════════════════════════════
# ENTITY FINDER
# ════════════════════════════════════════════════════════════════════════════

def _find(q_lower, candidates):
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in q_lower:
            return name
    for name in candidates:
        words = [w for w in re.sub(r'[^\w\s]',' ', name.lower()).split() if len(w) >= 5]
        if words and any(w in q_lower for w in words):
            return name
    return None


# ════════════════════════════════════════════════════════════════════════════
# CLAUDE API
# ════════════════════════════════════════════════════════════════════════════

def _api_key():
    k = st.session_state.get("anthropic_api_key","")
    if k: return k
    try:    return st.secrets.get("ANTHROPIC_API_KEY","")
    except: return os.environ.get("ANTHROPIC_API_KEY","")

def _build_ctx():
    lines = [
        f"VELOCITY GDI DATA: {m['total']:,} shipments | delivery={m['delivery_pct']:.1f}% | RTO={m['rto_pct']:.1f}% | NDR={m['ndr_count']:,} | COD={m['cod_pct']:.1f}% | COD-RTO={cod_rto:.1f}% | avg_order=₹{m['avg_order_value']:,.0f} | health={hs:.0f}/100",
        "SELLERS:"
    ]
    sg = df.groupby("seller_name").agg(
        total=("delivery_status","count"),
        delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
        rto=("delivery_status",lambda x:(x=="RTO").sum()),
    ).reset_index()
    sg["dr"]=sg["delivered"]/sg["total"]*100; sg["rr"]=sg["rto"]/sg["total"]*100
    for _,r in sg.iterrows():
        lines.append(f"  {r['seller_name']}: {r['total']:,} shpts | del={r['dr']:.1f}% | rto={r['rr']:.1f}%")
    lines.append("COURIERS:")
    for _,r in cour_df.iterrows():
        lines.append(f"  {r['courier']}: {r['total']:,} | del={r['delivery_rate']:.1f}% | rto={r['rto_rate']:.1f}%")
    lines.append("TOP STATES BY RTO:")
    for _,r in state_df.sort_values("rto_rate",ascending=False).head(5).iterrows():
        lines.append(f"  {r['state']}: rto={r['rto_rate']:.1f}% ({r['total']:,} shpts)")
    if "product_name" in df.columns:
        lines.append("TOP PRODUCTS:")
        tp = df.groupby("product_name").agg(total=("delivery_status","count"),rto=("delivery_status",lambda x:(x=="RTO").sum())).reset_index()
        tp["rr"]=tp["rto"]/tp["total"]*100
        for _,r in tp.sort_values("total",ascending=False).head(8).iterrows():
            lines.append(f"  {r['product_name']}: {r['total']:,} orders | rto={r['rr']:.1f}%")
    lines += ["VAS: AI Calling=38% NDR recovery | WhatsApp NDR=8% COD RTO reduction | Order Confirmation=12% pre-dispatch RTO reduction | ATS Address Verification=4-6% RTO reduction"]
    return "\n".join(lines)

def _claude(q):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=_api_key())
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001", max_tokens=500,
            system=f"""You are GDI Agent for Velocity Shipping. Goal: reduce RTO, improve delivery %, give sellers best product/location/courier insights.

{_build_ctx()}

Rules: Answer using ONLY the numbers above. Be specific. Use **bold** for key numbers. End with 1-2 action recommendations. Under 180 words.""",
            messages=[{"role":"user","content":q}]
        )
        return resp.content[0].text
    except Exception:
        return None


# ════════════════════════════════════════════════════════════════════════════
# REPLY ENGINE
# ════════════════════════════════════════════════════════════════════════════

def reply(q):
    ql  = q.lower().strip()
    qw  = set(re.sub(r'[^\w\s]',' ', ql).split())
    chart, sim = None, None

    def has(*p):  return any(x in ql for x in p)
    def hasw(*w): return any(x in qw for x in w)

    # entity detection
    sel  = _find(ql, all_sellers)
    cour = _find(ql, cour_df["courier"].tolist() if len(cour_df)>0 else [])
    stat = _find(ql, state_df["state"].tolist()  if len(state_df)>0 else [])
    prod = _find(ql, df["product_name"].unique().tolist()) if "product_name" in df.columns else None

    # ── Simulations (highest priority) ──────────────────────────────────────
    if has("ai calling","simulate call","ndr recovery","ivr","calling benefit","calling impact","calling help") \
       or (hasw("calling","call","ivr") and hasw("simulate","benefit","impact","help","if","what","how","recover")):
        sim  = _sim_calling()
        rec  = int(m["ndr_count"]*0.38)
        text = (f"**AI Calling Simulation** — based on your {m['ndr_count']:,} active NDRs:\n\n"
                f"At 38% recovery rate → **{rec:,} shipments recovered** → **₹{int(rec*m['avg_order_value']):,}/month**\n\n"
                f"Priority: call stale NDRs (>48h) first — highest RTO risk. See simulation below 👇")
        return text, ["Simulate WhatsApp NDR","Simulate Order Confirmation","Show NDR breakdown"], sim, None

    if has("whatsapp","whats app","wa ndr","whatsapp benefit","whatsapp help","whatsapp impact") \
       or (hasw("whatsapp","wa") and hasw("simulate","benefit","impact","help","if","how")):
        sim  = _sim_whatsapp()
        saved = int(m["rto_count"]*0.08)
        text = (f"**WhatsApp AI NDR Simulation** — your COD share is **{m['cod_pct']:.1f}%**:\n\n"
                f"WhatsApp reduces COD RTO by ~8% → **{saved:,} RTOs prevented** → **₹{int(saved*m['avg_order_value']):,}/month**\n\n"
                f"Best for: COD orders under ₹1,000 in high-RTO states. See simulation below 👇")
        return text, ["Simulate AI Calling","Simulate Order Confirmation","COD analysis"], sim, None

    if has("order confirm","confirmation","pre-dispatch","predispatch","fake order","bogus","confirm benefit") \
       or (hasw("confirm","confirmation","fake","bogus") and hasw("simulate","order","dispatch","benefit")):
        sim  = _sim_order_confirm()
        saved = int(m["rto_count"]*0.12)
        text = (f"**Order Confirmation Via AI Simulation** — {m['rto_pct']:.1f}% RTO rate:\n\n"
                f"AI call confirms intent BEFORE dispatch → catches fake/impulsive COD orders.\n"
                f"Prevents **{saved:,} RTOs/month** → **₹{int(saved*m['avg_order_value']):,}/month**\n\nSee simulation below 👇")
        return text, ["Simulate WhatsApp NDR","Simulate AI Calling","Show RTO causes"], sim, None

    # ── Specific named seller ────────────────────────────────────────────────
    if sel and (hasw("tell","about","show","how","analyse","analyze","analysis","performance","check","seller","client") or sel.lower() in ql):
        s_df  = df[df["seller_name"]==sel]
        sm    = compute_kpis(s_df); sm["vas_adoption_score"]=compute_vas_adoption_score(s_df)
        sh    = compute_health_score(sm); sr=get_recommendations(sm)
        risk  = "Low Risk ✅" if sh>=80 else ("Medium Risk ⚠️" if sh>=65 else "High Risk 🚨")
        text  = (f"**{sel}** — {risk} · Health **{sh:.0f}/100**\n\n"
                 f"- Shipments: **{sm['total']:,}** | Delivered: **{sm['delivered']:,}** | RTO: **{sm['rto_count']:,}**\n"
                 f"- Delivery: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | NDR: **{sm['ndr_count']:,}**\n"
                 f"- COD: **{sm['cod_pct']:.1f}%** | Avg Order: **₹{sm['avg_order_value']:,.0f}**\n")
        if "product_name" in s_df.columns:
            tp = s_df.groupby("product_name").agg(total=("delivery_status","count"),rto=("delivery_status",lambda x:(x=="RTO").sum())).reset_index()
            tp["rr"]=tp["rto"]/tp["total"]*100
            top_p=tp.sort_values("total",ascending=False).iloc[0]
            bad_p=tp.sort_values("rr",ascending=False).iloc[0]
            text += f"- Top Product: **{top_p['product_name']}** ({top_p['total']:,} orders)\n"
            if len(tp)>1: text += f"- Highest RTO Product: **{bad_p['product_name']}** ({bad_p['rr']:.1f}%)\n"
        if sr:
            text += f"\n**GDI Recommends for {sel}:**\n"
            for r in sr[:2]: text += f"- **{r['name']}**: {r['impact']} → ₹{r['revenue']:,}\n"
        sp = compute_sku_perf(s_df).head(6)
        if len(sp)>0:
            chart = dict(orient="h", x=sp["product_name"].tolist(), y=sp["rto_rate"].tolist(),
                         title=f"{sel} — RTO % by Product", color="#F87171")
        return text, [f"Simulate AI Calling for {sel}","Compare all sellers","Top products for "+sel], None, chart

    # ── All sellers / comparison ─────────────────────────────────────────────
    if has("all seller","all client","compare seller","seller list","seller performance","compare client","every seller") \
       or (hasw("seller","sellers","client","clients") and hasw("all","compare","list","rank","who","which","best","worst")):
        sg = df.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
        ).reset_index()
        sg["dr"]=sg["delivered"]/sg["total"]*100; sg["rr"]=sg["rto"]/sg["total"]*100
        sg=sg.sort_values("dr",ascending=False)
        chart=dict(orient="h",x=sg["seller_name"].tolist(),y=sg["dr"].tolist(),
                   title="Seller Delivery Rate (%)",color="#34D399")
        best_s=sg.iloc[0]; worst_s=sg.iloc[-1]
        text=f"**{len(sg)} Sellers — Performance Ranking:**\n\n"
        text+=f"🏆 Best: **{best_s['seller_name']}** — {best_s['dr']:.1f}% delivery\n"
        text+=f"⚠️ Needs help: **{worst_s['seller_name']}** — {worst_s['dr']:.1f}% delivery, {worst_s['rr']:.1f}% RTO\n\n"
        for _,r in sg.iterrows():
            e="✅" if r["dr"]>=80 else ("⚠️" if r["dr"]>=65 else "🚨")
            text+=f"{e} **{r['seller_name']}** — {r['dr']:.1f}% del | {r['rr']:.1f}% RTO | {r['total']:,} shpts\n"
        return text, [f"Tell me about {worst_s['seller_name']}","Simulate AI Calling","Top products"], None, chart

    # ── Top / best products ──────────────────────────────────────────────────
    if has("top product","best product","top selling","best selling","most sold","popular product","top sku") \
       or (hasw("top","best","popular","selling","sold") and hasw("product","sku","item","products")):
        if "product_name" not in df.columns:
            return "No product data in current dataset.", [], None, None
        grp=df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index()
        grp["dr"]=grp["delivered"]/grp["total"]*100
        top10=grp.sort_values("delivered",ascending=False).head(10)
        chart=dict(orient="v",x=top10["product_name"].tolist(),y=top10["delivered"].tolist(),
                   title="Top 10 Products — Delivered Units",color="#818CF8")
        text="**Top Selling Products:**\n\n"
        for _,r in top10.head(5).iterrows():
            text+=f"- **{r['product_name']}** — {r['delivered']:,} delivered | {r['dr']:.0f}% del rate | ₹{r['revenue']:,.0f}\n"
        text+=f"\n{len(grp)} products total across {m['total']:,} shipments."
        return text, ["Which product has highest RTO?","Show pricing band","Simulate Order Confirmation"], None, chart

    # ── Specific product ─────────────────────────────────────────────────────
    if prod:
        p_df=df[df["product_name"]==prod]
        pm=compute_kpis(p_df)
        text=(f"**{prod}:**\n\n"
              f"- Orders: **{pm['total']:,}** | Delivered: **{pm['delivered']:,}** ({pm['delivery_pct']:.1f}%)\n"
              f"- RTO: **{pm['rto_count']:,}** ({pm['rto_pct']:.1f}%) | COD: **{pm['cod_pct']:.1f}%** | Avg: **₹{pm['avg_order_value']:,.0f}**\n")
        if pm["rto_pct"] > m["rto_pct"]*1.3:
            text+=f"\n⚠️ RTO is **{pm['rto_pct']/max(m['rto_pct'],1):.1f}x above average**. Activate Order Confirmation Via AI for this product."
        return text, ["Show top selling products","Simulate Order Confirmation","Which state causes most RTO?"], None, None

    # ── Couriers ─────────────────────────────────────────────────────────────
    if cour or has("courier","3pl","carrier","logistics","shipping partner","courier performance") \
       or hasw("couriers","carriers","3pl","logistics"):
        if cour:
            row=cour_df[cour_df["courier"]==cour].iloc[0] if len(cour_df[cour_df["courier"]==cour])>0 else None
            if row is not None:
                vs=row["delivery_rate"]-m["delivery_pct"]
                text=(f"**{cour}:**\n\n- {row['total']:,} shipments | Delivery: **{row['delivery_rate']:.1f}%** "
                      f"({'above' if vs>=0 else 'below'} avg by {abs(vs):.1f}%) | RTO: **{row['rto_rate']:.1f}%**\n")
                text+=("\n⚠️ Underperforming — reduce volume here." if row["delivery_rate"]<m["delivery_pct"]-5
                       else "\n✅ Good performer — route more volume here.")
            else: text=f"No data for {cour}."
        else:
            text=f"**{len(cour_df)} Courier Partners:**\n\n"
            for _,r in cour_df.sort_values("delivery_rate",ascending=False).iterrows():
                e="✅" if r["delivery_rate"]>=80 else ("⚠️" if r["delivery_rate"]>=70 else "🚨")
                text+=f"{e} **{r['courier']}** — {r['delivery_rate']:.1f}% del | {r['rto_rate']:.1f}% RTO | {r['total']:,} shpts\n"
            if best_c: text+=f"\n**Best:** {best_c['courier']} · **Avoid:** {worst_c['courier'] if worst_c else '-'}"
        chart=dict(orient="h",x=cour_df["courier"].tolist(),y=cour_df["delivery_rate"].tolist(),
                   title="Courier Delivery Rates (%)",color="#60A5FA")
        return text, ["Which courier is best for COD?","Show state RTO breakdown","Simulate Smart Routing"], None, chart

    # ── State / location ─────────────────────────────────────────────────────
    if stat or has("state","location","zone","geographic","region","which state","city") \
       or (hasw("state","location","city","zone","region") and hasw("rto","delivery","worst","best","issue","problem")):
        if stat:
            row=state_df[state_df["state"]==stat]
            if len(row)>0:
                r=row.iloc[0]; share=r["rto"]/max(m["rto_count"],1)*100
                text=(f"**{stat}:**\n\n- {r['total']:,} shpts | RTO: **{r['rto_rate']:.1f}%** ({share:.0f}% of all RTOs)\n"
                      f"- Delivery: **{r['delivery_rate']:.1f}%**\n\n")
                text+=("🚨 High-risk. Activate ATS Address Verification + AI Calling for this state." if r["rto_rate"]>30
                       else ("⚠️ Restrict COD for low-value orders here." if r["rto_rate"]>20 else "✅ Within acceptable range."))
            else: text=f"No data for {stat}."
        else:
            text="**State-wise RTO Analysis:**\n\n"
            for _,r in state_df.sort_values("rto_rate",ascending=False).head(8).iterrows():
                e="🚨" if r["rto_rate"]>30 else ("⚠️" if r["rto_rate"]>20 else "✅")
                text+=f"{e} **{r['state']}** — {r['rto_rate']:.1f}% RTO | {r['total']:,} shpts\n"
            if worst_st:
                text+=f"\n**{worst_st['state']}** contributes {worst_st['rto']/max(m['rto_count'],1)*100:.0f}% of all RTOs."
        top8=state_df.sort_values("rto_rate",ascending=False).head(8)
        chart=dict(orient="h",x=top8["state"].tolist(),y=top8["rto_rate"].tolist(),
                   title="Worst States by RTO %",color="#F87171")
        return text, ["Why is RTO high in Bihar?","Best courier for high-RTO states","Restrict COD by state"], None, chart

    # ── RTO analysis / reduce RTO ────────────────────────────────────────────
    if has("rto","return","reduce rto","high rto","why rto","rto cause","rto issue","rto problem") \
       or (hasw("rto","return","returning") and hasw("why","high","cause","reduce","fix","improve","issue","problem")):
        causes=[]
        if worst_c and worst_c["delivery_rate"]<75:
            causes.append(f"**{worst_c['courier']}** delivering only {worst_c['delivery_rate']:.1f}%")
        if worst_st and worst_st["rto_rate"]>25:
            causes.append(f"**{worst_st['state']}** — {worst_st['rto_rate']:.1f}% RTO")
        if m["cod_pct"]>60:
            causes.append(f"**{m['cod_pct']:.0f}% COD** with {cod_rto:.1f}% COD-RTO rate")
        text=(f"**RTO Root Cause — {m['rto_pct']:.1f}% current rate:**\n\n"
              +("\n".join(f"- {c}" for c in causes) if causes else "- Multiple factors contributing")+
              f"\n\n**3-step RTO reduction plan:**\n"
              f"1. **Order Confirmation Via AI** → filter fake orders pre-dispatch (saves ~{int(m['rto_count']*0.12):,}/month)\n"
              f"2. **ATS Address Verification** → fix address RTOs at checkout\n"
              f"3. **WhatsApp AI NDR** → recover failed COD deliveries (saves ~{int(m['rto_count']*0.08):,}/month)\n"
              f"\nExpected improvement: **-8 to -12% RTO**")
        top6=state_df.sort_values("rto_rate",ascending=False).head(6)
        chart=dict(orient="h",x=top6["state"].tolist(),y=top6["rto_rate"].tolist(),
                   title="Top States Contributing to RTO",color="#F87171")
        return text, ["Simulate Order Confirmation","Simulate WhatsApp NDR","Which courier adds most RTO?"], None, chart

    # ── COD / payment ────────────────────────────────────────────────────────
    if has("cod","prepaid","cash on delivery","payment") \
       or (hasw("cod","prepaid","payment","cash") and hasw("analysis","breakdown","rate","rto","issue")):
        diff=cod_rto-prep_rto
        text=(f"**COD vs Prepaid Analysis:**\n\n"
              f"- COD: **{m['cod_pct']:.1f}%** ({m['cod_count']:,} shpts) | COD-RTO: **{cod_rto:.1f}%**\n"
              f"- Prepaid: **{100-m['cod_pct']:.1f}%** | Prepaid-RTO: **{prep_rto:.1f}%**\n"
              f"- COD Premium Risk: **+{diff:.1f}%** extra RTO vs Prepaid\n\n")
        text+=("🚨 Activate WhatsApp AI NDR + Order Confirmation Via AI immediately." if diff>8
               else ("⚠️ WhatsApp AI NDR will protect your COD deliveries." if diff>4 else "✅ COD risk manageable."))
        return text, ["Simulate WhatsApp NDR","Simulate Order Confirmation","Which state has worst COD RTO?"], None, None

    # ── NDR ──────────────────────────────────────────────────────────────────
    if has("ndr","non delivery","undelivered","not delivered","failed delivery","ndr queue","ndr analysis") \
       or hasw("ndr","undelivered","pending"):
        stale=0
        if "ndr_status" in df.columns and "ndr_age_hours" in df.columns:
            stale=len(df[(df["ndr_status"]=="Raised")&(df["ndr_age_hours"]>48)])
        sim=_sim_calling()
        text=(f"**NDR Analysis:**\n\n"
              f"- Active NDR: **{m['ndr_count']:,}** ({m['ndr_pct']:.1f}%)\n"
              f"- Stale >48h: **{stale}** — high RTO escalation risk\n"
              f"- AI Calling recovery: **{int(m['ndr_count']*0.38):,} shipments** → ₹{int(m['ndr_count']*0.38*m['avg_order_value']):,}\n\n"
              f"See AI Calling simulation below 👇")
        return text, ["Simulate AI Calling","Show NDR by state","Activate WhatsApp NDR"], sim, None

    # ── Health / overall summary ──────────────────────────────────────────────
    if has("health","score","overall","summary","status","how am i","how are we","dashboard","overview") \
       or (hasw("health","score","overall","performance","doing") and hasw("my","our","how","what","show")):
        risk  = "Low Risk ✅" if hs>=80 else ("Medium Risk ⚠️" if hs>=65 else "High Risk 🚨")
        pend  = m.get("pending_count", 0)
        att   = m.get("attempted_total", m["total"])
        fixes = []
        if m["rto_pct"]>20:   fixes.append(f"RTO {m['rto_pct']:.0f}% — activate Order Confirmation + Address Verification")
        if m["ndr_pct"]>15:   fixes.append(f"{m['ndr_count']:,} NDR backlog — activate AI Calling now")
        if m["cod_pct"]>60:   fixes.append(f"COD {m['cod_pct']:.0f}% — activate WhatsApp AI NDR")
        text  = (f"**Health Score: {hs:.0f}/100 — {risk}**\n\n"
                 f"- Delivery: **{m['delivery_pct']:.1f}%** ({m['delivered']:,} delivered out of {att:,} attempted)\n"
                 f"- RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_count']:,}** | COD: **{m['cod_pct']:.1f}%**\n"
                 f"- Total picked up in period: **{m['total']:,}**\n")
        if pend > 0:
            text += (f"- ℹ️ **{pend:,} shipments still In Transit / Pending Pickup** — "
                     f"these are excluded from delivery % (not yet attempted)\n")
        text += "\n" + (f"**Priority Actions:**\n"+"\n".join(f"- {f}" for f in fixes) if fixes else "✅ No critical issues.")
        return text, ["Simulate AI Calling","Compare all sellers","Show RTO causes","Give me action plan"], None, None

    # ── Action plan ──────────────────────────────────────────────────────────
    if has("action plan","30 day","roadmap","what should i do","help me improve","improve delivery","reduce rto plan") \
       or (hasw("action","plan","improve","fix","should","help","steps","roadmap") and hasw("do","me","my","our","delivery","rto","performance")):
        steps=[]
        if m["delivery_pct"]<80 and best_c:
            steps.append(f"1. **Route more to {best_c['courier']}** ({best_c['delivery_rate']:.1f}% del) — cut {worst_c['courier'] if worst_c else 'worst courier'}")
        if m["rto_pct"]>20:
            steps.append("2. **Order Confirmation Via AI** — stop fake COD orders before dispatch")
            steps.append("3. **ATS Address Verification** — fix address-driven RTOs at checkout")
        if m["ndr_pct"]>15:
            steps.append("4. **AI Calling** — recover 38% of NDR shipments with IVR outreach")
        if m["cod_pct"]>60 and m["ndr_pct"]>10:
            steps.append("5. **WhatsApp AI NDR** — protect COD deliveries, reduce COD RTO 8%")
        if not steps: steps=["1. Operations healthy. Expand to new pincodes with best couriers."]
        total=sum(r["revenue"] for r in recs)
        text=("**Your GDI 30-Day Action Plan:**\n\n"+"\n".join(steps)+
              f"\n\n💰 Total VAS revenue unlock: **₹{total:,}**\n"
              f"📈 Expected health score improvement: **+12–18 points**")
        return text, ["Simulate AI Calling","Simulate WhatsApp NDR","Show seller breakdown"], None, None

    # ── Product quality / insights ────────────────────────────────────────────
    if has("product quality","product insight","product performance","product analysis","sku analysis","sku performance") \
       or (hasw("product","products","sku") and hasw("quality","insight","performance","analysis","issue","problem","bad","worst")):
        if "product_name" in df.columns:
            grp=df.groupby("product_name").agg(
                total=("delivery_status","count"),
                rto=("delivery_status",lambda x:(x=="RTO").sum()),
                revenue=("order_value","sum"),
            ).reset_index()
            grp["rr"]=grp["rto"]/grp["total"]*100
            worst5=grp.nlargest(5,"rr")
            text="**Product Quality Insights — Worst RTO Products:**\n\n"
            for _,r in worst5.iterrows():
                text+=f"- **{r['product_name']}** — {r['rr']:.1f}% RTO | {r['total']:,} orders | ₹{r['rto']*r['revenue']/max(r['total'],1):,.0f} at risk\n"
            text+=f"\n**Fix:** Activate Order Confirmation Via AI for high-RTO products. Restrict COD for ₹0–499 price band."
            chart=dict(orient="h",x=worst5["product_name"].tolist(),y=worst5["rr"].tolist(),
                       title="Worst Products by RTO %",color="#F87171")
            return text, ["Show top selling products","Simulate Order Confirmation","Pricing band analysis"], None, chart
        return "No product data available in current dataset.", [], None, None

    # ── Pricing band ─────────────────────────────────────────────────────────
    if has("pricing band","price band","order value","value band","price range") \
       or (hasw("price","pricing","band","range","value") and hasw("rto","delivery","analysis","show","breakdown")):
        bins=[0,499,999,1999,4999,float("inf")]; blbls=["₹0–499","₹500–999","₹1K–2K","₹2K–5K","₹5K+"]
        df_pb=df.copy(); df_pb["pb"]=pd.cut(df_pb["order_value"],bins=bins,labels=blbls,right=True)
        pb=df_pb.groupby("pb",observed=True).agg(
            total=("delivery_status","count"),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
        ).reset_index()
        pb["rr"]=pb["rto"]/pb["total"].clip(lower=1)*100
        text="**Pricing Band Analysis:**\n\n"
        for _,r in pb.iterrows():
            e="🚨" if r["rr"]>30 else ("⚠️" if r["rr"]>20 else "✅")
            text+=f"{e} **{r['pb']}** — {r['rr']:.1f}% RTO | {r['total']:,} orders\n"
        text+="\n**Insight:** Restrict COD for bands with RTO > 25%. Activate Order Confirmation for ₹1K+ COD orders."
        chart=dict(orient="v",x=pb["pb"].astype(str).tolist(),y=pb["rr"].tolist(),
                   title="RTO % by Price Band",color="#F87171")
        return text, ["Show top selling products","Simulate Order Confirmation","COD analysis"], None, chart

    # ── Default — always give something useful ────────────────────────────────
    mode=f"{len(all_sellers)} sellers" if is_admin else (all_sellers[0] if all_sellers else "your data")
    text=(f"**GDI Agent ready** — {m['total']:,} shipments analysed ({mode})\n\n"
          f"Health: **{hs:.0f}/100** | Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_count']:,}**\n\n"
          f"**Try any of these:**")
    return text, ["Simulate AI Calling","Simulate WhatsApp NDR","Simulate Order Confirmation",
                  "Compare all sellers","Top selling products","Why is RTO high?",
                  "Show courier performance","Give me action plan"], None, None


# ════════════════════════════════════════════════════════════════════════════
# ASK (with error handling + Claude fallback)
# ════════════════════════════════════════════════════════════════════════════

def ask(q):
    try:
        text, chips, sim, chart = reply(q)

        # Try Claude API if key available and no simulation needed
        key = _api_key()
        if key and len(key) > 20 and sim is None:
            ai = _claude(q)
            if ai:
                return ai, chips, sim, chart

        return text, chips, sim, chart
    except Exception as e:
        return (f"I encountered an issue processing that: `{e}`\n\nTry asking:\n"
                f"- 'Simulate AI Calling'\n- 'Compare all sellers'\n- 'Why is RTO high?'",
                ["Simulate AI Calling","Compare all sellers","Show health score"], None, None)


# ════════════════════════════════════════════════════════════════════════════
# PAGE LAYOUT
# ════════════════════════════════════════════════════════════════════════════

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🤖 Ask GDI Agent</h1>
  <p class="header-subtitle">Velocity Shipping's AI Consultant — simulates VAS impact, analyses every seller, product & courier from your live data.</p>
</div>""", unsafe_allow_html=True)

# API key
with st.sidebar:
    st.markdown("---")
    st.markdown("<div style='color:#9CA3AF;font-size:0.72rem;font-weight:600;text-transform:uppercase;margin-bottom:6px;'>🔑 Claude AI (Recommended)</div>", unsafe_allow_html=True)
    st.markdown("<div style='color:#6B7280;font-size:0.72rem;margin-bottom:6px;'>Get free key → console.anthropic.com</div>", unsafe_allow_html=True)
    api_in = st.text_input("API Key", type="password", placeholder="sk-ant-...", label_visibility="collapsed")
    if api_in:
        st.session_state["anthropic_api_key"] = api_in
        st.success("✅ Claude AI active — full NLU enabled")
    elif st.session_state.get("anthropic_api_key"):
        st.success("✅ Claude AI active")
    else:
        st.info("Smart mode active. Add Claude API key for natural language.")

# Stats
rc="#34D399" if hs>=80 else ("#FBBF24" if hs>=65 else "#F87171")
st.markdown(f"""
<div style="background:#111827;border:1px solid #1F2937;border-radius:12px;
     padding:12px 18px;margin-bottom:14px;display:flex;gap:22px;flex-wrap:wrap;align-items:center;">
  <div><div style="font-size:1.2rem;font-weight:800;color:{rc};">{hs:.0f}/100</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Health</div></div>
  <div style="width:1px;background:#1F2937;height:28px;"></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#34D399;">{m['delivery_pct']:.1f}%</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Delivery</div></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#F87171;">{m['rto_pct']:.1f}%</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">RTO</div></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#FBBF24;">{m['ndr_count']:,}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">NDR</div></div>
  <div style="width:1px;background:#1F2937;height:28px;"></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#60A5FA;">{m['total']:,}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Shipments</div></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#C084FC;">{len(all_sellers)}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Sellers</div></div>
  <div><div style="font-size:1.2rem;font-weight:800;color:#818CF8;">{len(cour_df)}</div>
       <div style="font-size:0.68rem;color:#6B7280;text-transform:uppercase;">Couriers</div></div>
</div>""", unsafe_allow_html=True)

# Quick chips
quick = ["Simulate AI Calling","Simulate WhatsApp NDR","Simulate Order Confirmation",
         "Compare all sellers","Top selling products","Why is RTO high?",
         "Show courier performance","Give me action plan"]
qcols = st.columns(4)
sel_q = None
for i, qq in enumerate(quick):
    if qcols[i%4].button(qq, key=f"qb_{i}", use_container_width=True): sel_q = qq

# Init chat
if "gdi_chat" not in st.session_state:
    ws  = worst_st["state"] if worst_st is not None else "N/A"
    wsr = f"{worst_st['rto_rate']:.0f}%" if worst_st is not None else "N/A"
    opener = (f"I've analysed **{m['total']:,} shipments** · **{len(all_sellers)} sellers** · **{len(cour_df)} couriers**.\n\n"
              f"Health: **{hs:.0f}/100** · Delivery: **{m['delivery_pct']:.1f}%** · RTO: **{m['rto_pct']:.1f}%** · NDR: **{m['ndr_count']:,}**\n\n"
              f"Biggest RTO hotspot: **{ws}** at {wsr}. AI Calling can recover **~{int(m['ndr_count']*0.38):,} NDRs**.\n\n"
              f"Click a button above or type any question about your operations 👇")
    st.session_state["gdi_chat"] = [{"role":"assistant","content":opener,
        "chips":["Simulate AI Calling","Simulate WhatsApp NDR","Compare all sellers","Why is RTO high?"],
        "sim":None,"chart":None}]

# Render chat
for msg in st.session_state["gdi_chat"]:
    if msg["role"] == "user":
        st.markdown('<div class="user-lbl">You</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="agent-lbl">🤖 GDI Agent</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("sim"):   _render_sim(msg["sim"])
        if msg.get("chart"): _render_chart(msg["chart"])
        if msg.get("chips"):
            st.markdown("".join(f'<span class="qchip">{c}</span>' for c in msg["chips"]), unsafe_allow_html=True)

# Input
user_input = st.chat_input("Type any question — or click a button above…")
if sel_q or user_input:
    prompt = sel_q or user_input
    st.session_state["gdi_chat"].append({"role":"user","content":prompt,"chips":None,"sim":None,"chart":None})
    txt, chips, sim, chart = ask(prompt)
    st.session_state["gdi_chat"].append({"role":"assistant","content":txt,"chips":chips,"sim":sim,"chart":chart})
    st.rerun()

if st.button("🗑 Clear Chat"):
    del st.session_state["gdi_chat"]
    st.rerun()
