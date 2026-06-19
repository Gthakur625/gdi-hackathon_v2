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

st.set_page_config(page_title="Ask GDI Agent · Velocity", page_icon="🤖", layout="wide")
apply_styles()

st.markdown("""
<style>
.agent-label{display:flex;align-items:center;gap:8px;color:#818CF8;font-size:0.78rem;
             font-weight:700;text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;}
.user-label{text-align:right;color:#9CA3AF;font-size:0.78rem;font-weight:600;
            margin-bottom:4px;text-transform:uppercase;letter-spacing:0.05em;}
.chip-quick{display:inline-block;background:rgba(79,70,229,0.10);color:#818CF8;
            border:1px solid rgba(79,70,229,0.25);padding:5px 13px;border-radius:99px;
            font-size:0.8rem;font-weight:600;margin:3px 3px 0 0;cursor:pointer;}
.top-bar{background:#111827;border:1px solid #1F2937;border-radius:14px;
         padding:16px 22px;margin-bottom:18px;display:flex;gap:28px;align-items:center;flex-wrap:wrap;}
.top-stat-v{font-size:1.4rem;font-weight:800;}
.top-stat-l{font-size:0.72rem;color:#9CA3AF;text-transform:uppercase;letter-spacing:0.05em;}
</style>""", unsafe_allow_html=True)

df = render_sidebar_and_get_data()

m               = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs              = compute_health_score(m)
recs            = get_recommendations(m)
sku_df          = compute_sku_perf(df)
cour_df         = compute_courier_perf(df)
state_df        = compute_state_perf(df)
all_sellers     = sorted(df["seller_name"].unique().tolist()) if "seller_name" in df.columns else []
is_admin        = len(all_sellers) > 1

cod_df      = df[df["payment_type"] == "COD"]
prepaid_df  = df[df["payment_type"] == "Prepaid"]
cod_rto     = len(cod_df[cod_df["delivery_status"] == "RTO"]) / max(len(cod_df), 1) * 100
prepaid_rto = len(prepaid_df[prepaid_df["delivery_status"] == "RTO"]) / max(len(prepaid_df), 1) * 100
best_c  = cour_df.sort_values("delivery_rate", ascending=False).iloc[0] if len(cour_df) > 0 else None
worst_c = cour_df.sort_values("delivery_rate").iloc[0]                  if len(cour_df) > 0 else None
worst_st= state_df.sort_values("rto_rate", ascending=False).iloc[0]    if len(state_df) > 0 else None


# ── Claude API setup ───────────────────────────────────────────────────────────

def _get_api_key():
    if st.session_state.get("anthropic_api_key"):
        return st.session_state["anthropic_api_key"]
    try:
        return st.secrets.get("ANTHROPIC_API_KEY", "")
    except Exception:
        return os.environ.get("ANTHROPIC_API_KEY", "")


def _build_data_context():
    lines = [
        f"=== VELOCITY SHIPPING — GDI DATA SNAPSHOT ===",
        f"Total shipments: {m['total']:,}",
        f"Delivered: {m['delivered']:,} ({m['delivery_pct']:.1f}%)",
        f"RTO: {m['rto_count']:,} ({m['rto_pct']:.1f}%)",
        f"NDR (active): {m['ndr_count']:,} ({m['ndr_pct']:.1f}%)",
        f"COD share: {m['cod_pct']:.1f}%  |  COD-RTO rate: {cod_rto:.1f}%  |  Prepaid-RTO rate: {prepaid_rto:.1f}%",
        f"Avg order value: ₹{m['avg_order_value']:,.0f}",
        f"Health Score: {hs:.0f}/100",
        "",
        "--- SELLERS ---",
    ]
    sg = df.groupby("seller_name").agg(
        total=("delivery_status","count"),
        delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
        rto=("delivery_status", lambda x: (x=="RTO").sum()),
        ndr_count=("ndr_status", lambda x: (x=="Raised").sum()) if "ndr_status" in df.columns else ("delivery_status","count"),
        cod=("payment_type", lambda x: (x=="COD").sum()),
        revenue=("order_value","sum"),
    ).reset_index()
    sg["del_rate"] = sg["delivered"]/sg["total"]*100
    sg["rto_rate"] = sg["rto"]/sg["total"]*100
    sg["cod_pct"]  = sg["cod"]/sg["total"]*100
    for _, row in sg.sort_values("del_rate",ascending=False).iterrows():
        lines.append(f"  {row['seller_name']}: {row['total']:,} shipments | delivery={row['del_rate']:.1f}% | RTO={row['rto_rate']:.1f}% | COD={row['cod_pct']:.1f}% | revenue=₹{row['revenue']:,.0f}")

    lines += ["", "--- COURIERS ---"]
    for _, row in cour_df.sort_values("delivery_rate",ascending=False).iterrows():
        lines.append(f"  {row['courier']}: {row['total']:,} shipments | delivery={row['delivery_rate']:.1f}% | RTO={row['rto_rate']:.1f}%")

    lines += ["", "--- TOP STATES BY RTO ---"]
    for _, row in state_df.sort_values("rto_rate",ascending=False).head(8).iterrows():
        lines.append(f"  {row['state']}: RTO={row['rto_rate']:.1f}% ({row['rto']:,} RTOs / {row['total']:,} shipments)")

    lines += ["", "--- TOP PRODUCTS (by volume) ---"]
    if "product_name" in df.columns:
        tp = df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index()
        tp["del_rate"] = tp["delivered"]/tp["total"]*100
        tp["rto_rate"] = tp["rto"]/tp["total"]*100
        for _, row in tp.sort_values("total",ascending=False).head(10).iterrows():
            lines.append(f"  {row['product_name']}: {row['total']:,} orders | delivery={row['del_rate']:.1f}% | RTO={row['rto_rate']:.1f}% | revenue=₹{row['revenue']:,.0f}")

    lines += ["", "--- VAS RECOMMENDATIONS ---"]
    if recs:
        for r in recs:
            lines.append(f"  TRIGGERED: {r['name']} — {r['impact']} — revenue unlock ₹{r['revenue']:,}")
    else:
        lines.append("  No VAS gaps triggered by current metrics.")

    lines += [
        "",
        "--- VELOCITY SHIPPING VAS PRODUCTS ---",
        "  1. AI Calling: Outbound AI IVR calls for NDR recovery. 38% recovery rate. Triggered when NDR > 15%.",
        "  2. Order Confirmation Via AI: AI call before dispatch to confirm COD orders. Reduces fake RTO 10-15%. Triggered when RTO>15% or COD>50%.",
        "  3. WhatsApp AI NDR: WhatsApp messages for failed COD deliveries. Reduces COD RTO ~8%. Triggered when COD>60% and NDR>10%.",
        "  4. ATS Address Verification: AI address correction at checkout (ATS partner feature). Reduces RTO 4-6%. Triggered when RTO>20%.",
    ]
    return "\n".join(lines)


def _claude_reply(question, api_key):
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        context = _build_data_context()
        system = f"""You are GDI Agent — Velocity Shipping's AI Delivery Intelligence Consultant.
You have access to real shipment data below. Answer every question using ONLY the numbers from this data.
Be specific, concise, and actionable. Use markdown with **bold** for key numbers.
When asked about a seller, give their specific metrics. When asked about a courier, give its specific stats.
Always end with 1-2 concrete action recommendations relevant to the question.
Keep answers under 250 words.

{context}"""
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=600,
            system=system,
            messages=[{"role":"user","content":question}],
        )
        return resp.content[0].text
    except Exception as e:
        return None


# ── chart helpers ──────────────────────────────────────────────────────────────

def _chart(ctype, x, y, title, color="#818CF8", xlabel="", ylabel="", orient="v"):
    return dict(ctype=ctype, x=[str(v) for v in x], y=[float(v) if isinstance(v,(int,float,np.integer,np.floating)) else 0 for v in y],
                title=title, color=color, xlabel=xlabel, ylabel=ylabel, orient=orient)


def render_chart(c):
    if not c:
        return
    vals = c["y"]; labels = c["x"]
    try:
        if c["orient"] == "h":
            fig = go.Figure(go.Bar(x=vals, y=labels, orientation="h", marker_color=c["color"],
                                   text=[f"{v:.1f}" for v in vals], textposition="auto"))
            fig.update_layout(yaxis=dict(autorange="reversed"))
        else:
            fig = go.Figure(go.Bar(x=labels, y=vals, marker_color=c["color"],
                                   text=[f"{v:.1f}" if isinstance(v,float) else f"{int(v):,}" for v in vals],
                                   textposition="auto"))
        fig.update_layout(title=dict(text=c["title"],font=dict(color="#FFFFFF",size=13)),
                          paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                          font_color="#F3F4F6", height=300, margin=dict(l=10,r=10,t=44,b=10),
                          xaxis=dict(showgrid=False,title=c["xlabel"],tickfont=dict(size=10)),
                          yaxis=dict(gridcolor="#1F2937",title=c["ylabel"]))
        st.markdown('<div class="saas-card" style="padding:12px;">', unsafe_allow_html=True)
        st.plotly_chart(fig, use_container_width=True)
        st.markdown("</div>", unsafe_allow_html=True)
    except Exception:
        pass


# ── entity detection ───────────────────────────────────────────────────────────

def _words(s):
    return set(re.sub(r'[^\w\s]',' ',s.lower()).split())

def _find_entity(q_lower, candidates):
    qw = _words(q_lower)
    # exact substring first
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in q_lower:
            return name
    # word overlap: ≥1 significant word matches
    for name in candidates:
        sig = [w for w in _words(name) if len(w) >= 4]
        if sig and any(w in qw for w in sig):
            return name
    return None


def _seller_summary(sel_name, sel_df):
    sm = compute_kpis(sel_df)
    sm["vas_adoption_score"] = compute_vas_adoption_score(sel_df)
    sh = compute_health_score(sm)
    sr = get_recommendations(sm)
    risk = "Low Risk ✅" if sh>=80 else ("Medium Risk ⚠️" if sh>=65 else "High Risk 🚨")
    active = sel_df["vas_active"].dropna().str.split(", ").explode().unique().tolist() if "vas_active" in sel_df.columns else []
    lines = [
        f"**{sel_name} — {risk} · Health {sh:.0f}/100**\n",
        f"- Shipments: **{sm['total']:,}** | Delivered: **{sm['delivered']:,}** | RTO: **{sm['rto_count']:,}**",
        f"- Delivery: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | NDR: **{sm['ndr_pct']:.1f}%**",
        f"- COD: **{sm['cod_pct']:.1f}%** | Avg Order Value: **₹{sm['avg_order_value']:,.0f}**",
    ]
    if active and active != ['']:
        lines.append(f"- Active VAS: {', '.join(a for a in active if a)}")
    if sr:
        lines.append(f"\n**GDI Recommendations for {sel_name}:**")
        for r in sr[:3]:
            lines.append(f"- **{r['name']}**: {r['impact']} → ₹{r['revenue']:,} unlock")
    else:
        lines.append(f"\n✅ No urgent VAS gaps for {sel_name}. Maintain current performance.")
    return "\n".join(lines)


# ── keyword-based reply engine (fallback) ──────────────────────────────────────

def _keyword_reply(q):
    ql = q.lower().strip()
    qw = _words(ql)
    chart = None

    mentioned_seller  = _find_entity(ql, all_sellers)
    mentioned_courier = _find_entity(ql, cour_df["courier"].tolist() if len(cour_df)>0 else [])
    mentioned_state   = _find_entity(ql, state_df["state"].tolist()  if len(state_df)>0 else [])
    mentioned_product = (_find_entity(ql, df["product_name"].unique().tolist()) if "product_name" in df.columns else None)
    if mentioned_product is None and "sku" in df.columns:
        mentioned_product = _find_entity(ql, df["sku"].unique().tolist())

    # intent helpers
    def has(*words): return any(w in ql for w in words)
    def hasw(*words): return any(w in qw for w in words)

    # ── Top Selling / Best Products ──────────────────────────────────────────
    if has("top selling","best selling","most sold","bestseller","popular product","top product") \
       or (hasw("top","best","popular") and hasw("product","sku","item","selling","sold")):
        if "product_name" not in df.columns:
            return "No product name column found in the uploaded data.", [], None
        grp = df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index()
        grp["del_rate"] = grp["delivered"]/grp["total"]*100
        top10 = grp.sort_values("delivered",ascending=False).head(10)
        chart = _chart("bar", x=top10["product_name"], y=top10["delivered"],
                       title="Top 10 Products by Delivered Units", color="#818CF8",
                       xlabel="Product", ylabel="Units Delivered")
        text = "**Top Selling Products (from your data):**\n\n"
        for _, row in top10.head(5).iterrows():
            text += f"- **{row['product_name']}** — {row['delivered']:,} delivered | {row['del_rate']:.0f}% rate | ₹{row['revenue']:,.0f}\n"
        text += f"\n📊 Chart below. {len(grp)} products total across {m['total']:,} shipments."
        return text, ["Which product has highest RTO?","Show worst performing product","Revenue by product"], chart

    # ── Specific Seller ──────────────────────────────────────────────────────
    if mentioned_seller:
        sel_df2 = df[df["seller_name"] == mentioned_seller]
        text = _seller_summary(mentioned_seller, sel_df2)
        sp = compute_sku_perf(sel_df2).head(8)
        if len(sp)>0 and "rto_rate" in sp.columns:
            chart = _chart("bar", x=sp["product_name"], y=sp["rto_rate"],
                           title=f"{mentioned_seller} — RTO % by Product",
                           color="#F87171", xlabel="Product", ylabel="RTO %")
        return text, ["Compare all sellers","Will AI Calling help this seller?",
                      "What VAS should this seller activate?"], chart

    # ── All Sellers Comparison ───────────────────────────────────────────────
    if has("all seller","compare seller","seller comparison","every seller","seller performance",
           "seller list","seller analysis","all client","compare client") \
       or (hasw("seller","client") and hasw("compare","all","list","rank","best","worst","who")):
        sg = df.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
        ).reset_index()
        sg["delivery_rate"] = sg["delivered"]/sg["total"]*100
        sg["rto_rate"]      = sg["rto"]/sg["total"]*100
        sg = sg.sort_values("delivery_rate",ascending=False)
        chart = _chart("bar", orient="h", x=sg["seller_name"], y=sg["delivery_rate"],
                       title="Seller Delivery Rate Comparison (%)",
                       color="#34D399", xlabel="Delivery %", ylabel="Seller")
        best_s  = sg.iloc[0]; worst_s = sg.iloc[-1]
        text  = f"**Seller Comparison — {len(sg)} sellers:**\n\n"
        text += f"🏆 Best: **{best_s['seller_name']}** — {best_s['delivery_rate']:.1f}% delivery\n"
        text += f"⚠️ Needs help: **{worst_s['seller_name']}** — {worst_s['delivery_rate']:.1f}% delivery, {worst_s['rto_rate']:.1f}% RTO\n\n"
        for _, row in sg.iterrows():
            e = "✅" if row["delivery_rate"]>=80 else ("⚠️" if row["delivery_rate"]>=65 else "🚨")
            text += f"{e} **{row['seller_name']}** — {row['delivery_rate']:.1f}% delivery, {row['rto_rate']:.1f}% RTO ({row['total']:,} shipments)\n"
        return text, [f"Tell me about {worst_s['seller_name']}", "Which seller needs AI Calling?",
                      "Which seller has highest RTO?"], chart

    # ── Specific Courier ─────────────────────────────────────────────────────
    if mentioned_courier and not (hasw("all","compare","best","worst","which") and not mentioned_courier):
        row = cour_df[cour_df["courier"]==mentioned_courier].iloc[0] if len(cour_df[cour_df["courier"]==mentioned_courier])>0 else None
        if row is not None:
            vs = row["delivery_rate"] - m["delivery_pct"]
            direction = "above" if vs>=0 else "below"
            text = (f"**{mentioned_courier} Performance:**\n\n"
                    f"- Shipments: **{row['total']:,}**\n"
                    f"- Delivery Rate: **{row['delivery_rate']:.1f}%** ({abs(vs):.1f}% {direction} your avg {m['delivery_pct']:.1f}%)\n"
                    f"- RTO Rate: **{row['rto_rate']:.1f}%**\n\n")
            text += ("⚠️ Underperforming. Consider reducing volume here."
                     if row["delivery_rate"] < m["delivery_pct"]-5
                     else f"✅ Performing well. Keep routing volume to {mentioned_courier}.")
        else:
            text = f"No data for {mentioned_courier} in the current filter."
        chart = _chart("bar", orient="h", x=cour_df["courier"], y=cour_df["delivery_rate"],
                       title="All Courier Delivery Rates (%)", color="#60A5FA",
                       xlabel="Delivery %", ylabel="Courier")
        return text, ["Compare all couriers","Which courier should I shift volume to?"], chart

    # ── All Couriers / 3PL ───────────────────────────────────────────────────
    if has("courier","carrier","3pl","shipping partner","logistic") \
       or hasw("courier","couriers","carrier","3pl"):
        chart = _chart("bar", orient="h", x=cour_df["courier"], y=cour_df["delivery_rate"],
                       title="Courier Delivery Rates (%)", color="#60A5FA",
                       xlabel="Delivery %", ylabel="Courier")
        text = f"**Courier Performance — {len(cour_df)} partners active:**\n\n"
        for _, row in cour_df.sort_values("delivery_rate",ascending=False).iterrows():
            e = "✅" if row["delivery_rate"]>=80 else ("⚠️" if row["delivery_rate"]>=70 else "🚨")
            text += f"{e} **{row['courier']}** — {row['delivery_rate']:.1f}% delivery, {row['rto_rate']:.1f}% RTO ({row['total']:,} shipments)\n"
        if best_c is not None:
            text += f"\n✅ Route more to: **{best_c['courier']}** ({best_c['delivery_rate']:.1f}%)"
        if worst_c is not None:
            text += f"\n⚠️ Reduce volume from: **{worst_c['courier']}** ({worst_c['delivery_rate']:.1f}%)"
        return text, ["Tell me about Delhivery","How much will shifting couriers save?",
                      "Which courier is best for COD?"], chart

    # ── Specific Product / SKU ───────────────────────────────────────────────
    if mentioned_product:
        p_df = df[df["product_name"]==mentioned_product] if "product_name" in df.columns else df[df["sku"]==mentioned_product]
        pm   = compute_kpis(p_df)
        text = (f"**{mentioned_product}:**\n\n"
                f"- Total Shipments: **{pm['total']:,}**\n"
                f"- Delivered: **{pm['delivered']:,}** ({pm['delivery_pct']:.1f}%)\n"
                f"- RTO: **{pm['rto_count']:,}** ({pm['rto_pct']:.1f}%)\n"
                f"- NDR: **{pm['ndr_count']:,}** | COD: **{pm['cod_pct']:.1f}%** | Avg Value: **₹{pm['avg_order_value']:,.0f}**\n\n")
        if pm["rto_pct"] > m["rto_pct"]*1.3:
            text += (f"⚠️ RTO is **{pm['rto_pct']:.1f}%** — {pm['rto_pct']/max(m['rto_pct'],1):.1f}x above average.\n"
                     f"Activate **AI Calling + Order Confirmation Via AI** to reduce.")
        else:
            text += "✅ This product performs within normal range."
        return text, ["Show top selling products","Which product has highest RTO?"], None

    # ── SKU / Products general ───────────────────────────────────────────────
    if has("sku","product","item") or (hasw("product","sku","item") and hasw("worst","bad","underperform","rto","issue","problem")):
        if len(sku_df)>0:
            worst_p = sku_df.iloc[0]
            text = (f"**Product Analysis:**\n\n"
                    f"⚠️ Worst: **{worst_p['product_name']}** — {worst_p['rto_rate']:.1f}% RTO, "
                    f"₹{worst_p['revenue_at_risk']:,.0f} revenue at risk\n\n"
                    f"Ask me about a specific product by name for deeper analysis.")
            chart = _chart("bar", orient="h",
                x=sku_df.head(8)["product_name"], y=sku_df.head(8)["rto_rate"],
                title="Worst Products by RTO Rate (%)", color="#F87171",
                xlabel="RTO %", ylabel="Product")
            return text, ["Show top selling products","Why is this product RTO high?"], chart
        return "No product data available.", [], None

    # ── State specific ───────────────────────────────────────────────────────
    if mentioned_state:
        row_s = state_df[state_df["state"]==mentioned_state]
        if len(row_s)>0:
            row_s = row_s.iloc[0]
            share = row_s["rto"]/max(m["rto_count"],1)*100
            text  = (f"**{mentioned_state} — State Analysis:**\n\n"
                     f"- Shipments: **{row_s['total']:,}** | RTO: **{row_s['rto_rate']:.1f}%** ({share:.0f}% of all RTOs)\n"
                     f"- Delivery Rate: **{row_s['delivery_rate']:.1f}%**\n\n")
            if row_s["rto_rate"]>30:
                text += (f"🚨 **High-risk zone.** Address quality + COD non-acceptance are primary drivers.\n"
                         f"**Fix:** Enable ATS Address Verification + AI Calling for {mentioned_state} orders.")
            elif row_s["rto_rate"]>20:
                text += f"⚠️ Moderate RTO. Restrict COD for low-value orders in {mentioned_state}."
            else:
                text += f"✅ {mentioned_state} is within acceptable range."
        else:
            text = f"No data for {mentioned_state} in the current filter."
        return text, ["Compare all states","Which state has worst RTO?","Enable address verification?"], None

    # ── Geographic / State comparison ────────────────────────────────────────
    if has("state","region","geographic","zone","geography") \
       or (hasw("state","states","region") and hasw("rto","delivery","worst","best","compare")):
        top8 = state_df.sort_values("rto_rate",ascending=False).head(8)
        chart = _chart("bar", orient="h", x=top8["state"], y=top8["rto_rate"],
                       title="Top States by RTO Rate (%)", color="#F87171",
                       xlabel="RTO %", ylabel="State")
        text = "**State-wise RTO Analysis:**\n\n"
        for _, row in top8.iterrows():
            e = "🚨" if row["rto_rate"]>30 else ("⚠️" if row["rto_rate"]>20 else "✅")
            text += f"{e} **{row['state']}** — {row['rto_rate']:.1f}% RTO ({row['total']:,} shipments)\n"
        if worst_st is not None:
            share = worst_st["rto"]/max(m["rto_count"],1)*100
            text += f"\n**{worst_st['state']} is your biggest hotspot** — {share:.0f}% of all RTOs."
        return text, ["Tell me about Bihar","Tell me about Uttar Pradesh","How to fix state RTO?"], chart

    # ── AI Calling ────────────────────────────────────────────────────────────
    if has("ai calling","ai call") or (hasw("calling","call","ivr") and not hasw("whatsapp","wa","whats")):
        ndr_q = df[df["ndr_status"]=="Raised"] if "ndr_status" in df.columns else pd.DataFrame()
        stale = len(ndr_q[ndr_q["ndr_age_hours"]>48]) if "ndr_age_hours" in ndr_q.columns and len(ndr_q)>0 else 0
        rec = int(m["ndr_count"]*0.38)
        text = (f"**AI Calling — {'🚨 Strongly Recommended' if m['ndr_pct']>15 else ('⚠️ Recommended' if m['ndr_count']>10 else '✅ Optional')}**\n\n"
                f"- NDR queue: **{m['ndr_count']:,}** ({m['ndr_pct']:.1f}% of shipments)\n"
                f"- Stale NDRs >48h: **{stale}** — risk of conversion to RTO\n"
                f"- AI Calling expected recovery: **38%** → **{rec:,} shipments** → **₹{int(rec*m['avg_order_value']):,}**\n\n"
                f"**How it works:** AI IVR calls buyers in priority order. Press 1=reschedule, 2=update address, 3=speak to delivery partner.\n\n"
                f"Go to **📞 AI Calling Engine** page to see the priority queue.")
        return text, ["Show me NDR queue","What about WhatsApp AI NDR?","Tell me about Order Confirmation"], None

    # ── WhatsApp AI NDR ───────────────────────────────────────────────────────
    if has("whatsapp","whats app") or (hasw("whatsapp","wa","wha") and hasw("ndr","calling","message")):
        saved = int(m["rto_count"]*0.08)
        triggered = m["cod_pct"]>60 and m["ndr_pct"]>10
        text = (f"**WhatsApp AI NDR — {'🚨 Triggered' if triggered else '⚠️ Recommended'}**\n\n"
                f"- COD Share: **{m['cod_pct']:.1f}%** | COD-RTO Rate: **{cod_rto:.1f}%**\n"
                f"- WhatsApp reduces COD RTO by ~8% → saves **{saved:,} shipments** → **₹{int(saved*m['avg_order_value']):,}**\n\n"
                f"**How it works:** On failed COD delivery, AI WhatsApp message goes to buyer with reschedule link + prepaid conversion nudge.\n"
                f"Buyers respond 3× faster to WhatsApp vs calls for orders under ₹1,000.\n\n"
                f"Best paired with **AI Calling** for high-value orders (₹1,000+).")
        return text, ["Tell me about AI Calling","Tell me about Order Confirmation Via AI",
                      "What's my COD breakdown?"], None

    # ── Order Confirmation Via AI ─────────────────────────────────────────────
    if has("order confirm","confirmation","pre-dispatch","predispatch") \
       or (hasw("confirm","confirmation","intent","fake","bogus","pre") and hasw("order","dispatch","cod")):
        saved = int(m["rto_count"]*0.12)
        text  = (f"**Order Confirmation Via AI — {'🚨 Recommended' if (m['rto_pct']>15 or m['cod_pct']>50) else '✅ Optional'}**\n\n"
                 f"- RTO Rate: **{m['rto_pct']:.1f}%** | COD Share: **{m['cod_pct']:.1f}%**\n"
                 f"- Can prevent **{saved:,} RTOs** before dispatch → save **₹{int(saved*m['avg_order_value']):,}**\n\n"
                 f"**How it works:** After COD order is placed, AI call confirms address, delivery intent, and preferred slot — BEFORE the shipment is dispatched.\n"
                 f"Reduces fake/impulsive COD RTOs by 10–15%.\n\n"
                 f"Works best with **WhatsApp AI NDR** as a complete NDR-prevention funnel.")
        return text, ["Tell me about WhatsApp AI NDR","Tell me about AI Calling","Show VAS plan"], None

    # ── ATS Address Verification ─────────────────────────────────────────────
    if has("address verif","address check","ats address","wrong address","address quality"):
        saved = int(m["total"]*0.05)
        text  = (f"**ATS Address Verification — New ATS Feature (Recommended)**\n\n"
                 f"- RTO Rate: **{m['rto_pct']:.1f}%** (threshold for benefit: >20%)\n"
                 f"- Reduces RTO by 4–6% by fixing address at checkout\n"
                 f"- Saves ~**{saved:,} shipments** → **₹{int(saved*m['avg_order_value']):,}**\n\n"
                 f"**Feature by ATS (Amazon Transport Services)** — Velocity is recommending this to eligible sellers.\n"
                 f"Best impact in: **{worst_st['state'] if worst_st is not None else 'high-RTO states'}**")
        return text, ["Which state benefits most?","Tell me about AI Calling"], None

    # ── VAS / Recommendations ─────────────────────────────────────────────────
    if has("vas","recommend","activate","adopt","velocity product","which product") \
       or (hasw("recommend","recommendation","should","use","activate","enable") \
           and hasw("vas","product","calling","whatsapp","confirmation","verification")):
        if not recs:
            return (f"✅ All VAS triggers are within healthy limits. Health Score: **{hs:.0f}/100**.\n\nKeep monitoring NDR age and COD ratios.", [], None)
        total_rev = sum(r["revenue"] for r in recs)
        text = f"**GDI VAS Recommendation Plan — {len(recs)} products triggered:**\n\n"
        labels = ["#1 Highest Impact","#2 High Impact","#3 Medium Impact","#4","#5"]
        for i, r in enumerate(recs):
            text += f"**{labels[min(i,4)]}: {r['name']}**\n- {r['impact']}\n- Revenue unlock: **₹{r['revenue']:,}**\n\n"
        text += f"💰 **Total estimated revenue unlock: ₹{total_rev:,}**\n\nGo to 🚀 ATS Recommendations page for full plan."
        return text, ["Tell me about AI Calling","Tell me about WhatsApp AI NDR",
                      "Tell me about Order Confirmation Via AI"], None

    # ── COD / Payment ─────────────────────────────────────────────────────────
    if has("cod","prepaid","cash on delivery","payment mode","payment type") \
       or (hasw("cod","prepaid","payment","cash") and hasw("rate","analysis","impact","rto","breakdown")):
        text = (f"**COD vs Prepaid Analysis:**\n\n"
                f"- COD: **{m['cod_pct']:.1f}%** ({m['cod_count']:,} shipments) | COD-RTO: **{cod_rto:.1f}%**\n"
                f"- Prepaid: **{100-m['cod_pct']:.1f}%** | Prepaid-RTO: **{prepaid_rto:.1f}%**\n"
                f"- COD premium risk: **+{cod_rto-prepaid_rto:.1f}%** extra RTO vs Prepaid\n\n")
        if m["cod_pct"]>70:
            text += ("🚨 **High COD concentration.** Actions:\n"
                     "1. Activate **WhatsApp AI NDR** to recover failed COD deliveries\n"
                     "2. Activate **Order Confirmation Via AI** to filter fake COD orders\n"
                     "3. Offer 3–5% prepaid discount at checkout\n"
                     "4. Restrict COD in high-risk state + high-RTO SKU combos")
        elif m["cod_pct"]>50:
            text += "⚠️ Moderate COD risk. **WhatsApp AI NDR** will protect your COD deliveries."
        else:
            text += "✅ COD share is manageable. Continue monitoring."
        return text, ["Tell me about WhatsApp AI NDR","Show state-wise COD breakdown",
                      "How to push prepaid conversions?"], None

    # ── Health Score / Summary ────────────────────────────────────────────────
    if has("health","score","overall","summary") \
       or (hasw("health","score","overall","performance","status","how") and hasw("doing","am","is","are","my","our")):
        risk = "Low Risk ✅" if hs>=80 else ("Medium Risk ⚠️" if hs>=65 else "High Risk 🚨")
        fixes = []
        if m["rto_pct"]>20:  fixes.append(f"RTO at {m['rto_pct']:.0f}% — activate Order Confirmation Via AI + Address Verification")
        if m["ndr_pct"]>15:  fixes.append(f"NDR backlog {m['ndr_count']:,} shipments — activate AI Calling now")
        if m["cod_pct"]>70:  fixes.append(f"COD at {m['cod_pct']:.0f}% — launch WhatsApp AI NDR")
        fix_str = "\n".join(f"- {f}" for f in fixes) if fixes else "- No critical issues. Maintain momentum."
        text = (f"**Health Score: {hs:.0f}/100 — {risk}**\n\n"
                f"- Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_pct']:.1f}%**\n"
                f"- Shipments: **{m['total']:,}** | COD: **{m['cod_pct']:.1f}%**\n\n"
                f"**Actions to improve:**\n{fix_str}")
        return text, ["What's dragging my score?","Show VAS plan","Compare all sellers",
                      "Which courier should I use?"], None

    # ── NDR ──────────────────────────────────────────────────────────────────
    if has("ndr","non delivery","undelivered","not delivered","pending delivery","failed delivery") \
       or (hasw("ndr","undelivered","pending","failed") and not hasw("rate","percent")):
        stale = 0
        if "ndr_status" in df.columns and "ndr_age_hours" in df.columns:
            stale = len(df[(df["ndr_status"]=="Raised") & (df["ndr_age_hours"]>48)])
        rec = int(m["ndr_count"]*0.38)
        text = (f"**NDR Analysis:**\n\n"
                f"- Total NDR: **{m['ndr_count']:,}** ({m['ndr_pct']:.1f}%)\n"
                f"- Stale >48h: **{stale}** — high risk of converting to RTO\n"
                f"- AI Calling expected recovery: **{rec:,} shipments** → ₹{int(rec*m['avg_order_value']):,}\n"
                f"- WhatsApp AI NDR: additional **8% COD RTO** protection\n\n"
                f"**Priority:** Activate AI Calling → Go to **📞 AI Calling Engine** page for queue.")
        return text, ["Open AI Calling queue","Tell me about WhatsApp AI NDR",
                      "Which state has most NDRs?"], None

    # ── RTO analysis ─────────────────────────────────────────────────────────
    if has("rto","return","high rto","why rto") \
       or (hasw("rto","return","returning") and hasw("why","reason","cause","high","issue","problem")):
        causes = []
        if worst_c is not None and worst_c["delivery_rate"]<75:
            causes.append(f"**{worst_c['courier']}** delivering only {worst_c['delivery_rate']:.1f}% ({worst_c['total']:,} shipments)")
        if worst_st is not None and worst_st["rto_rate"]>25:
            share = worst_st["rto"]/max(m["rto_count"],1)*100
            causes.append(f"**{worst_st['state']}** — {worst_st['rto_rate']:.1f}% RTO, {share:.0f}% of all RTOs")
        if m["cod_pct"]>70:
            causes.append(f"**{m['cod_pct']:.0f}% COD share** with {cod_rto:.1f}% COD-RTO rate")
        cause_str = "\n".join(f"- {c}" for c in causes) if causes else "- Checking data..."
        text = (f"**RTO Root Cause Analysis — {m['rto_pct']:.1f}% RTO:**\n\n{cause_str}\n\n"
                f"**Fix:** Activate **Order Confirmation Via AI** (stop fake orders) + **ATS Address Verification** (fix address RTOs)")
        chart = _chart("bar", orient="h", x=state_df.sort_values("rto_rate",ascending=False).head(6)["state"],
                       y=state_df.sort_values("rto_rate",ascending=False).head(6)["rto_rate"],
                       title="States Contributing Most to RTO", color="#F87171",
                       xlabel="RTO %", ylabel="State")
        return text, ["Tell me about Order Confirmation Via AI","Which state has worst RTO?",
                      "Which courier is underperforming?"], chart

    # ── Improve / Action Plan ─────────────────────────────────────────────────
    if has("improve","how to","action","fix","what should","help me","steps","plan","roadmap","advice","what can") \
       or (hasw("improve","fix","help","action","plan","steps","should","recommend") \
           and hasw("do","i","we","me","my","our")):
        steps = []
        if m["delivery_pct"]<75 and best_c:
            steps.append(f"1. **Route more volume to {best_c['courier']}** ({best_c['delivery_rate']:.1f}% delivery)")
        if m["rto_pct"]>20:
            steps.append("2. **Activate Order Confirmation Via AI** — stop fake/unintentional COD orders before dispatch")
            steps.append("3. **Enable ATS Address Verification** — fix address-driven RTO at checkout")
        if m["ndr_pct"]>15:
            steps.append("4. **Launch AI Calling** — recover 38% of NDR shipments immediately")
        if m["cod_pct"]>60 and m["ndr_pct"]>10:
            steps.append("5. **Enable WhatsApp AI NDR** — protect COD deliveries via WhatsApp engagement")
        if not steps:
            steps.append("1. VAS stack looks good. Focus on expanding to new states with your best courier.")
        total = sum(r["revenue"] for r in recs)
        text  = "**Your GDI Action Plan:**\n\n" + "\n".join(steps)
        text += f"\n\n💰 Total estimated revenue unlock: **₹{total:,}**\n📈 Expected health score improvement: **+12–18 points**"
        return text, ["Tell me about AI Calling","Tell me about WhatsApp AI NDR","Open Impact Simulator"], None

    # ── Default ───────────────────────────────────────────────────────────────
    mode = f"{len(all_sellers)} sellers" if is_admin else (all_sellers[0] if all_sellers else "All sellers")
    text = (f"I have **{m['total']:,} shipments** analysed ({mode}).\n\n"
            f"- Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_pct']:.1f}%**\n"
            f"- Health Score: **{hs:.0f}/100** | COD: **{m['cod_pct']:.1f}%**\n\n"
            f"**Try asking:**\n"
            f"- *'Compare all sellers'* or *'Tell me about [seller name]'*\n"
            f"- *'Top selling products'* or *'Which product has highest RTO?'*\n"
            f"- *'Will AI Calling help?'* or *'Should I use WhatsApp NDR?'*\n"
            f"- *'Which courier is best?'* or *'Tell me about Delhivery'*\n"
            f"- *'Why is RTO high?'* or *'Which state is causing RTO?'*")
    return text, ["Compare all sellers","Top selling products","Will AI Calling help?",
                  "Which courier is best?","Why is RTO high?","What's my health score?"], None


# ── unified reply (Claude API → keyword fallback) ──────────────────────────────

def reply(q):
    ql = q.lower()
    api_key = _get_api_key()

    # Always compute chart regardless of API usage
    chart = _detect_chart(ql)

    if api_key and len(api_key) > 20:
        ai_text = _claude_reply(q, api_key)
        if ai_text:
            return ai_text, _followup_chips(ql), chart

    # Fallback
    text, chips, kw_chart = _keyword_reply(q)
    return text, chips, kw_chart or chart


def _detect_chart(ql):
    qw = _words(ql)
    if any(x in ql for x in ["top selling","best selling","popular product","top product"]) \
       or (any(w in qw for w in ["top","best","popular"]) and any(w in qw for w in ["product","sku","item"])):
        if "product_name" in df.columns:
            grp = df.groupby("product_name").agg(
                delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            ).reset_index().sort_values("delivered",ascending=False).head(10)
            return _chart("bar", x=grp["product_name"], y=grp["delivered"],
                          title="Top 10 Products by Delivered Units", color="#818CF8",
                          xlabel="Product", ylabel="Delivered Units")
    if any(x in ql for x in ["all seller","compare seller","seller comparison","every seller"]) \
       or (any(w in qw for w in ["seller","client"]) and any(w in qw for w in ["compare","all","rank"])):
        sg = df.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
        ).reset_index()
        sg["delivery_rate"] = sg["delivered"]/sg["total"]*100
        return _chart("bar", orient="h", x=sg.sort_values("delivery_rate",ascending=False)["seller_name"],
                      y=sg.sort_values("delivery_rate",ascending=False)["delivery_rate"],
                      title="Seller Delivery Rate Comparison (%)", color="#34D399",
                      xlabel="Delivery %", ylabel="Seller")
    if any(x in ql for x in ["courier","carrier","3pl"]) or any(w in qw for w in ["courier","couriers","carrier"]):
        return _chart("bar", orient="h", x=cour_df["courier"], y=cour_df["delivery_rate"],
                      title="Courier Delivery Rates (%)", color="#60A5FA",
                      xlabel="Delivery %", ylabel="Courier")
    if any(x in ql for x in ["state","region","geographic"]) or any(w in qw for w in ["state","states","region"]):
        top8 = state_df.sort_values("rto_rate",ascending=False).head(8)
        return _chart("bar", orient="h", x=top8["state"], y=top8["rto_rate"],
                      title="Top States by RTO Rate (%)", color="#F87171",
                      xlabel="RTO %", ylabel="State")
    return None


def _followup_chips(ql):
    qw = _words(ql)
    if any(w in qw for w in ["seller","client"]): return ["Compare all sellers","Show VAS plan","Why is RTO high?"]
    if any(w in qw for w in ["product","sku","item"]): return ["Show top selling products","Which SKU has worst RTO?"]
    if any(w in qw for w in ["courier","carrier"]): return ["Which courier is best?","Show state RTO breakdown"]
    if any(w in qw for w in ["calling","whatsapp","confirm"]): return ["Show me the full VAS plan","What's my health score?"]
    return ["Compare all sellers","Top selling products","Will AI Calling help?","Which courier is best?"]


# ── PAGE LAYOUT ────────────────────────────────────────────────────────────────

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🤖 Ask GDI Agent</h1>
  <p class="header-subtitle">AI Delivery Consultant — grounded in your real shipment data. Ask about any seller, product, courier, or VAS.</p>
</div>""", unsafe_allow_html=True)

# API key input in sidebar
with st.sidebar:
    st.markdown("---")
    st.markdown("<div style='color:#9CA3AF;font-size:0.78rem;font-weight:600;text-transform:uppercase;'>🔑 Claude AI (Optional)</div>", unsafe_allow_html=True)
    api_input = st.text_input("Paste Anthropic API Key for smarter answers",
                               type="password", placeholder="sk-ant-...",
                               help="Get free key at console.anthropic.com → API Keys")
    if api_input:
        st.session_state["anthropic_api_key"] = api_input
        st.success("✅ Claude AI active")
    elif st.session_state.get("anthropic_api_key"):
        st.success("✅ Claude AI active")
    else:
        st.info("Running in smart keyword mode")

# Stats bar
risk_color = "#34D399" if hs>=80 else ("#FBBF24" if hs>=65 else "#F87171")
admin_badge = (f"<div style='margin-left:auto;background:rgba(79,70,229,0.12);border:1px solid rgba(79,70,229,0.3);"
               f"padding:6px 14px;border-radius:8px;color:#818CF8;font-size:0.82rem;font-weight:700;'>"
               f"👤 Admin · {len(all_sellers)} Sellers</div>") if is_admin else ""
st.markdown(f"""
<div class="top-bar">
  <div><div class="top-stat-v" style="color:{risk_color};">{hs:.0f}/100</div><div class="top-stat-l">Health</div></div>
  <div style="width:1px;background:#1F2937;height:36px;"></div>
  <div><div class="top-stat-v" style="color:#34D399;">{m['delivery_pct']:.1f}%</div><div class="top-stat-l">Delivery</div></div>
  <div><div class="top-stat-v" style="color:#F87171;">{m['rto_pct']:.1f}%</div><div class="top-stat-l">RTO</div></div>
  <div><div class="top-stat-v" style="color:#FBBF24;">{m['ndr_pct']:.1f}%</div><div class="top-stat-l">NDR</div></div>
  <div style="width:1px;background:#1F2937;height:36px;"></div>
  <div><div class="top-stat-v" style="color:#60A5FA;">{m['total']:,}</div><div class="top-stat-l">Shipments</div></div>
  <div><div class="top-stat-v" style="color:#C084FC;">{len(all_sellers)}</div><div class="top-stat-l">Sellers</div></div>
  <div><div class="top-stat-v" style="color:#818CF8;">{len(cour_df)}</div><div class="top-stat-l">Couriers</div></div>
  {admin_badge}
</div>""", unsafe_allow_html=True)

# Top Products chart (always visible)
if "product_name" in df.columns:
    with st.expander("📊 Top Selling Products Overview", expanded=False):
        tp2 = df.groupby("product_name").agg(
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
            total=("delivery_status","count"),
        ).reset_index().sort_values("delivered",ascending=False).head(10)
        tp2["rto_rate"] = tp2["rto"]/tp2["total"]*100
        c1,c2 = st.columns(2)
        with c1:
            fig1 = px.bar(tp2, x="product_name", y="delivered", title="Top 10 Products — Deliveries",
                          color="delivered", color_continuous_scale=["#4F46E5","#818CF8"],
                          labels={"product_name":"","delivered":"Delivered"})
            fig1.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#F3F4F6", height=280,
                               margin=dict(l=0,r=0,t=36,b=0), showlegend=False, coloraxis_showscale=False,
                               xaxis_tickangle=-35)
            st.plotly_chart(fig1, use_container_width=True)
        with c2:
            fig2 = px.bar(tp2, x="product_name", y="rto_rate", title="Top 10 Products — RTO %",
                          color="rto_rate", color_continuous_scale=["#10B981","#EF4444"],
                          labels={"product_name":"","rto_rate":"RTO %"})
            fig2.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                               font_color="#F3F4F6", height=280,
                               margin=dict(l=0,r=0,t=36,b=0), showlegend=False, coloraxis_showscale=False,
                               xaxis_tickangle=-35)
            st.plotly_chart(fig2, use_container_width=True)

st.markdown("---")

# Quick chips
quick_qs = ["Show top selling products","Compare all sellers",
            "Will AI Calling help me?","Should I use WhatsApp AI NDR?",
            "Which courier is best?","Which state has worst RTO?",
            "Why is RTO high?","Show me the VAS plan"]
cols = st.columns(4)
selected_q = None
for i, qq in enumerate(quick_qs):
    if cols[i%4].button(qq, key=f"qc_{i}", use_container_width=True):
        selected_q = qq

# Init chat
if "gdi_chat" not in st.session_state:
    ws_name = worst_st["state"] if worst_st is not None else "N/A"
    ws_rto  = f"{worst_st['rto_rate']:.0f}%" if worst_st is not None else "N/A"
    mode_str = f"**{len(all_sellers)} sellers** in view (admin mode)." if is_admin else f"Seller: **{all_sellers[0] if all_sellers else 'All data'}**."
    opener = (f"I've analysed **{m['total']:,} shipments**. {mode_str}\n\n"
              f"Health Score: **{hs:.0f}/100** | Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_count']:,} active**\n\n"
              f"Biggest RTO hotspot: **{ws_name}** at {ws_rto} RTO rate. "
              f"AI Calling can recover ~**{int(m['ndr_count']*0.38):,}** NDR shipments.\n\n"
              f"Ask me about any seller, product, courier, or VAS product 👇")
    st.session_state["gdi_chat"] = [{"role":"assistant","content":opener,"chips":[
        "Compare all sellers","Top selling products","Will AI Calling help?","Which courier is best?"
    ],"chart":None}]

# Render chat
for msg in st.session_state["gdi_chat"]:
    if msg["role"]=="user":
        st.markdown('<div class="user-label">You</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="agent-label">🤖 GDI Agent</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("chart"):
            render_chart(msg["chart"])
        if msg.get("chips"):
            chip_html = "".join(f'<span class="chip-quick">{c}</span>' for c in msg["chips"])
            st.markdown(f"<div style='margin:6px 0 18px 0;'>{chip_html}</div>", unsafe_allow_html=True)

# Input
user_input = st.chat_input("Ask about any seller, product, courier, or VAS…")
if selected_q or user_input:
    prompt = selected_q or user_input
    st.session_state["gdi_chat"].append({"role":"user","content":prompt,"chips":None,"chart":None})
    text, chips, chart_data = reply(prompt)
    st.session_state["gdi_chat"].append({"role":"assistant","content":text,"chips":chips,"chart":chart_data})
    st.rerun()

if st.button("🗑 Clear Chat"):
    del st.session_state["gdi_chat"]
    st.rerun()
