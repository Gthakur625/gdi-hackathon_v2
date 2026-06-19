import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import numpy as np
import sys, os
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
.chat-wrap { max-width:860px; margin:0 auto; }
.agent-label { display:flex; align-items:center; gap:8px; color:#818CF8;
               font-size:0.78rem; font-weight:700; text-transform:uppercase;
               letter-spacing:0.06em; margin-bottom:4px; }
.user-label  { text-align:right; color:#9CA3AF; font-size:0.78rem;
               font-weight:600; margin-bottom:4px; text-transform:uppercase; letter-spacing:0.05em; }
.chip-quick  { display:inline-block; background:rgba(79,70,229,0.10);
               color:#818CF8; border:1px solid rgba(79,70,229,0.25);
               padding:5px 13px; border-radius:99px; font-size:0.8rem;
               font-weight:600; margin:3px 3px 0 0; cursor:pointer; }
.top-bar     { background:#111827; border:1px solid #1F2937; border-radius:14px;
               padding:16px 22px; margin-bottom:18px;
               display:flex; gap:28px; align-items:center; flex-wrap:wrap; }
.top-stat    { text-align:center; }
.top-stat-v  { font-size:1.4rem; font-weight:800; }
.top-stat-l  { font-size:0.72rem; color:#9CA3AF; text-transform:uppercase; letter-spacing:0.05em; }
</style>""", unsafe_allow_html=True)

df = render_sidebar_and_get_data()

m               = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs              = compute_health_score(m)
recs            = get_recommendations(m)
sku_df          = compute_sku_perf(df)
cour_df         = compute_courier_perf(df)
state_df        = compute_state_perf(df)
all_sellers     = sorted(df["seller_name"].unique()) if "seller_name" in df.columns else []
is_admin        = len(all_sellers) > 1

cod_df          = df[df["payment_type"] == "COD"]
prepaid_df      = df[df["payment_type"] == "Prepaid"]
cod_rto         = len(cod_df[cod_df["delivery_status"] == "RTO"]) / max(len(cod_df), 1) * 100
prepaid_rto     = len(prepaid_df[prepaid_df["delivery_status"] == "RTO"]) / max(len(prepaid_df), 1) * 100
best_c          = cour_df.sort_values("delivery_rate", ascending=False).iloc[0] if len(cour_df) > 0 else None
worst_c         = cour_df.sort_values("delivery_rate").iloc[0] if len(cour_df) > 0 else None
worst_st        = state_df.sort_values("rto_rate", ascending=False).iloc[0] if len(state_df) > 0 else None


# ── helpers ────────────────────────────────────────────────────────────────────

def _chart(ctype, x, y, title, color="#818CF8", xlabel="", ylabel="", orient="v"):
    return dict(ctype=ctype, x=x, y=y, title=title, color=color,
                xlabel=xlabel, ylabel=ylabel, orient=orient)


def render_chart(c):
    if c is None:
        return
    if c["orient"] == "h":
        fig = go.Figure(go.Bar(
            x=c["y"], y=c["x"], orientation="h",
            marker_color=c["color"],
            text=[f"{v:,.0f}" if isinstance(v, (int, float)) else str(v) for v in c["y"]],
            textposition="auto",
        ))
        fig.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig = go.Figure(go.Bar(
            x=c["x"], y=c["y"],
            marker_color=c["color"],
            text=[f"{v:,.0f}" if isinstance(v, (int, float)) else str(v) for v in c["y"]],
            textposition="auto",
        ))
    fig.update_layout(
        title=dict(text=c["title"], font=dict(color="#FFFFFF", size=14)),
        paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font_color="#F3F4F6", height=320,
        margin=dict(l=10, r=10, t=44, b=10),
        xaxis=dict(showgrid=False, title=c["xlabel"], tickfont=dict(size=11)),
        yaxis=dict(gridcolor="#1F2937", title=c["ylabel"]),
    )
    st.markdown('<div class="saas-card" style="padding:14px;">', unsafe_allow_html=True)
    st.plotly_chart(fig, use_container_width=True)
    st.markdown("</div>", unsafe_allow_html=True)


def _find_entity(q_lower, candidates):
    """Fuzzy-find first candidate whose words appear in query."""
    for name in candidates:
        if name.lower() in q_lower:
            return name
        words = [w for w in name.lower().split() if len(w) > 3]
        if words and any(w in q_lower for w in words):
            return name
    return None


def _seller_card(sel_name, sel_df):
    sm = compute_kpis(sel_df)
    sm["vas_adoption_score"] = compute_vas_adoption_score(sel_df)
    sh = compute_health_score(sm)
    sr = get_recommendations(sm)
    risk = "Low Risk ✅" if sh >= 80 else ("Medium Risk ⚠️" if sh >= 65 else "High Risk 🚨")
    lines = [
        f"**{sel_name} — {risk} · {sh:.0f}/100**\n",
        f"- Shipments: **{sm['total']:,}** | Delivered: **{sm['delivered']:,}** | RTO: **{sm['rto_count']:,}**",
        f"- Delivery Rate: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | NDR: **{sm['ndr_pct']:.1f}%**",
        f"- COD Share: **{sm['cod_pct']:.1f}%** | Avg Order: **₹{sm['avg_order_value']:,.0f}**",
    ]
    if sr:
        lines.append(f"\n**GDI Recommendations for {sel_name}:**")
        for r in sr[:3]:
            lines.append(f"- {r['name']}: {r['impact']} → **₹{r['revenue']:,} unlock**")
    else:
        lines.append(f"\n✅ No urgent VAS gaps detected for {sel_name}.")
    return "\n".join(lines)


# ── main reply engine ──────────────────────────────────────────────────────────

def reply(q):
    ql = q.lower().strip()
    chart = None

    mentioned_seller  = _find_entity(ql, all_sellers)
    mentioned_courier = _find_entity(ql, df["courier"].unique().tolist() if "courier" in df.columns else [])
    mentioned_state   = _find_entity(ql, df["state"].unique().tolist() if "state" in df.columns else [])
    mentioned_product = None
    if "product_name" in df.columns:
        mentioned_product = _find_entity(ql, df["product_name"].unique().tolist())
    if mentioned_product is None and "sku" in df.columns:
        mentioned_product = _find_entity(ql, df["sku"].unique().tolist())

    # ── top selling / best products ──────────────────────────────────────────
    if any(x in ql for x in ["top selling", "best selling", "most sold", "popular product",
                               "top product", "bestseller", "top sku"]):
        grp = df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index()
        grp["delivery_rate"] = grp["delivered"] / grp["total"] * 100
        top10 = grp.sort_values("delivered", ascending=False).head(10)
        chart = _chart("bar",
            x=top10["product_name"].tolist(),
            y=top10["delivered"].tolist(),
            title="Top 10 Best Selling Products (by Delivered Units)",
            color="#818CF8", xlabel="Product", ylabel="Delivered Units",
        )
        t3 = top10.head(3)
        text = "**Top Selling Products from your data:**\n\n"
        for _, row in t3.iterrows():
            text += f"- **{row['product_name']}** — {row['delivered']:,} delivered | {row['delivery_rate']:.0f}% rate | ₹{row['revenue']:,.0f} revenue\n"
        text += f"\n📊 Chart shows full top-10 below. Total {grp['total'].sum():,} shipments analysed across {len(grp)} products."
        return text, ["Which product has highest RTO?", "Show worst performing SKU", "Show revenue by product"], chart

    # ── seller-specific query ────────────────────────────────────────────────
    if mentioned_seller:
        sel_df2 = df[df["seller_name"] == mentioned_seller]
        text = _seller_card(mentioned_seller, sel_df2)
        # mini chart: delivery vs RTO for that seller's top products
        sp = compute_sku_perf(sel_df2).head(8)
        if len(sp) > 0:
            chart = _chart("bar",
                x=sp["product_name"].tolist(),
                y=sp["rto_rate"].tolist(),
                title=f"{mentioned_seller} — RTO % by Product",
                color="#F87171", xlabel="Product", ylabel="RTO %",
            )
        chips = [f"Compare all sellers", f"Top products for {mentioned_seller}",
                 "Will AI Calling help this seller?", "What VAS should this seller activate?"]
        return text, chips, chart

    # ── all sellers comparison ───────────────────────────────────────────────
    if any(x in ql for x in ["all seller", "compare seller", "seller comparison",
                               "which seller", "seller list", "seller performance", "every seller"]):
        if not is_admin:
            return ("Only one seller is loaded. Upload a multi-seller MIS or select all sellers in the sidebar filter.",
                    ["Upload new data", "Tell me about my health score"], None)
        sg = df.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
        ).reset_index()
        sg["delivery_rate"] = sg["delivered"] / sg["total"] * 100
        sg["rto_rate"]      = sg["rto"]       / sg["total"] * 100
        sg = sg.sort_values("delivery_rate", ascending=False)
        chart = _chart("bar", orient="h",
            x=sg["seller_name"].tolist(),
            y=sg["delivery_rate"].tolist(),
            title="Seller Delivery Rate Comparison (%)",
            color="#34D399", xlabel="Delivery %", ylabel="Seller",
        )
        best_s  = sg.iloc[0]
        worst_s = sg.iloc[-1]
        text = f"**Seller Comparison — {len(sg)} sellers in current view:**\n\n"
        text += f"- Best: **{best_s['seller_name']}** at {best_s['delivery_rate']:.1f}% delivery\n"
        text += f"- Needs help: **{worst_s['seller_name']}** at {worst_s['delivery_rate']:.1f}% delivery, {worst_s['rto_rate']:.1f}% RTO\n\n"
        for _, row in sg.iterrows():
            emoji = "✅" if row["delivery_rate"] >= 80 else ("⚠️" if row["delivery_rate"] >= 65 else "🚨")
            text += f"{emoji} **{row['seller_name']}** — {row['delivery_rate']:.1f}% delivery, {row['rto_rate']:.1f}% RTO ({row['total']:,} shipments)\n"
        chips = [f"Tell me about {sg.iloc[-1]['seller_name']}", "Which seller needs AI Calling?",
                 "Which seller has highest RTO?"]
        return text, chips, chart

    # ── specific courier query ───────────────────────────────────────────────
    if mentioned_courier:
        cr = cour_df[cour_df["courier"] == mentioned_courier]
        if len(cr) > 0:
            row = cr.iloc[0]
            vs_avg = row["delivery_rate"] - m["delivery_pct"]
            direction = "above" if vs_avg >= 0 else "below"
            text = (f"**{mentioned_courier} Performance:**\n\n"
                    f"- Shipments handled: **{row['total']:,}**\n"
                    f"- Delivery Rate: **{row['delivery_rate']:.1f}%** ({abs(vs_avg):.1f}% {direction} your avg {m['delivery_pct']:.1f}%)\n"
                    f"- RTO Rate: **{row['rto_rate']:.1f}%**\n\n")
            if row["delivery_rate"] < m["delivery_pct"] - 5:
                text += f"⚠️ **{mentioned_courier} is underperforming.** Consider reducing volume and routing to {best_c['courier'] if best_c is not None else 'a better-performing courier'}."
            else:
                text += f"✅ **{mentioned_courier} is performing well.** Keep routing volume here."
        else:
            text = f"No data found for {mentioned_courier} in the current filter."
        chart = _chart("bar", orient="h",
            x=cour_df["courier"].tolist(),
            y=cour_df["delivery_rate"].tolist(),
            title="All Courier Delivery Rates (%)",
            color="#60A5FA", xlabel="Delivery %", ylabel="Courier",
        )
        return text, ["Compare all couriers", "Which courier should I shift volume to?",
                      "How do I set routing rules?"], chart

    # ── all couriers / 3PL ──────────────────────────────────────────────────
    if any(x in ql for x in ["courier", "carrier", "3pl", "shipping partner",
                               "which courier", "courier performance", "best courier"]):
        chart = _chart("bar", orient="h",
            x=cour_df["courier"].tolist(),
            y=cour_df["delivery_rate"].tolist(),
            title="Courier Delivery Rates (%)",
            color="#60A5FA", xlabel="Delivery %", ylabel="Courier",
        )
        worst_str = (f"**{worst_c['courier']}** delivers only {worst_c['delivery_rate']:.1f}% "
                     f"({worst_c['total']:,} shipments, {worst_c['rto_rate']:.1f}% RTO). Reduce volume here."
                     ) if worst_c is not None else ""
        best_str  = (f"**{best_c['courier']}** tops at {best_c['delivery_rate']:.1f}% delivery. "
                     f"Route more volume here."
                     ) if best_c is not None else ""
        text = (f"**Courier Intelligence — {len(cour_df)} partners active:**\n\n"
                f"✅ Best: {best_str}\n\n"
                f"❌ Worst: {worst_str}\n\n"
                f"Shift 30–40% of underperformer volume to top courier. "
                f"Estimated delivery improvement: **+4–6%**.")
        return text, ["Show me courier vs state breakdown", "How much will shifting couriers save?",
                      "Which courier is best for COD?"], chart

    # ── specific product / SKU ───────────────────────────────────────────────
    if mentioned_product:
        p_rows = df[df["product_name"] == mentioned_product] if "product_name" in df.columns else df[df["sku"] == mentioned_product]
        pm     = compute_kpis(p_rows)
        pr     = get_recommendations(pm)
        text   = (f"**{mentioned_product} — SKU Analysis:**\n\n"
                  f"- Total Shipments: **{pm['total']:,}**\n"
                  f"- Delivered: **{pm['delivered']:,}** ({pm['delivery_pct']:.1f}%)\n"
                  f"- RTO: **{pm['rto_count']:,}** ({pm['rto_pct']:.1f}%)\n"
                  f"- NDR: **{pm['ndr_count']:,}** ({pm['ndr_pct']:.1f}%)\n"
                  f"- COD Share: **{pm['cod_pct']:.1f}%** | Avg Value: **₹{pm['avg_order_value']:,.0f}**\n\n")
        if pm["rto_pct"] > m["rto_pct"] * 1.3:
            text += f"⚠️ RTO is **{pm['rto_pct']:.1f}%** — {pm['rto_pct']/max(m['rto_pct'],1):.1f}x above average. "
            if pm["cod_pct"] > 60:
                text += "High COD share is the main driver. Consider restricting COD for this product in high-risk states.\n"
            text += "\n**AI Calling & Order Confirmation Via AI** can recover NDR shipments and reduce fake orders."
        else:
            text += f"✅ This product is performing within normal range."
        return text, [f"Compare {mentioned_product} across states", "Which VAS helps this product?",
                      "Show me top selling products"], None

    # ── SKU / product general ────────────────────────────────────────────────
    if any(x in ql for x in ["sku", "product", "item", "underperform", "which product", "worst product"]):
        top_rto = sku_df.head(5) if len(sku_df) > 0 else pd.DataFrame()
        top_vol = (df.groupby("product_name")["delivery_status"].count()
                     .sort_values(ascending=False).head(8).reset_index()
                     if "product_name" in df.columns else pd.DataFrame())
        chart = _chart("bar",
            x=top_vol["product_name"].tolist() if len(top_vol) > 0 else [],
            y=top_vol["delivery_status"].tolist() if len(top_vol) > 0 else [],
            title="Top 8 Products by Shipment Volume",
            color="#818CF8", xlabel="Product", ylabel="Shipments",
        )
        text = "**SKU / Product Performance:**\n\n"
        if len(top_rto) > 0:
            worst_p = top_rto.iloc[0]
            text += (f"⚠️ Worst SKU: **{worst_p['product_name']}** — {worst_p['rto_rate']:.1f}% RTO "
                     f"({worst_p['rto']:,} returns, ₹{worst_p['revenue_at_risk']:,.0f} at risk)\n\n")
        text += "📊 Chart below shows volume distribution. Type a product name to get deep analysis."
        return text, ["Show me top selling products", "Which SKU has highest RTO?",
                      "How do I fix high-RTO SKUs?"], chart

    # ── state query ─────────────────────────────────────────────────────────
    if mentioned_state:
        sr2 = state_df[state_df["state"] == mentioned_state]
        if len(sr2) > 0:
            row = sr2.iloc[0]
            share = row["rto"] / max(m["rto_count"], 1) * 100
            text  = (f"**{mentioned_state} — State Analysis:**\n\n"
                     f"- Shipments: **{row['total']:,}** | Delivered: **{row['delivered']:,}**\n"
                     f"- RTO Rate: **{row['rto_rate']:.1f}%** ({share:.0f}% of all your RTOs)\n"
                     f"- Delivery Rate: **{row['delivery_rate']:.1f}%**\n\n")
            if row["rto_rate"] > 30:
                text += (f"🚨 **{mentioned_state} is a high-risk zone.** Address quality + COD non-acceptance are the primary drivers.\n\n"
                         f"**Fix:** Enable **ATS Address Verification** for {mentioned_state} orders. "
                         f"Use **AI Calling** for NDRs in this state — recovery rate here is typically 55–65%.")
            elif row["rto_rate"] > 20:
                text += f"⚠️ Moderate RTO in {mentioned_state}. Consider restricting COD for low-value orders here."
            else:
                text += f"✅ {mentioned_state} is performing within acceptable range."
        else:
            text = f"No data for {mentioned_state} in the current filter."
        return text, [f"Compare all states", "Which state has worst RTO?",
                      "Should I restrict COD in high-risk states?"], None

    # ── geographic / state general ───────────────────────────────────────────
    if any(x in ql for x in ["state", "region", "geographic", "zone", "which state", "geography"]):
        chart = _chart("bar", orient="h",
            x=state_df.sort_values("rto_rate", ascending=False).head(8)["state"].tolist(),
            y=state_df.sort_values("rto_rate", ascending=False).head(8)["rto_rate"].tolist(),
            title="Top 8 States by RTO Rate (%)",
            color="#F87171", xlabel="RTO %", ylabel="State",
        )
        text = "**Geographic RTO Analysis:**\n\n"
        for _, row in state_df.sort_values("rto_rate", ascending=False).head(5).iterrows():
            emoji = "🚨" if row["rto_rate"] > 30 else ("⚠️" if row["rto_rate"] > 20 else "✅")
            text += f"{emoji} **{row['state']}** — {row['rto_rate']:.1f}% RTO ({row['total']:,} shipments)\n"
        if worst_st is not None:
            share = worst_st["rto"] / max(m["rto_count"], 1) * 100
            text += (f"\n**{worst_st['state']} is your biggest hotspot** — contributes {share:.0f}% of all RTOs. "
                     f"Activate ATS Address Verification for orders to this state.")
        return text, ["Tell me about Bihar", "Tell me about Uttar Pradesh",
                      "How do I fix state-level RTO?"], chart

    # ── AI Calling ────────────────────────────────────────────────────────────
    if any(x in ql for x in ["ai calling", "calling", "ivr", "call"]):
        ndr_queue = df[(df["ndr_status"] == "Raised")] if "ndr_status" in df.columns else pd.DataFrame()
        stale = len(ndr_queue[ndr_queue.get("ndr_age_hours", pd.Series(dtype=int)) > 48]) \
                if "ndr_age_hours" in df.columns else 0
        expected_rec = int(m["ndr_count"] * 0.38)
        rev_rec = int(expected_rec * m["avg_order_value"])
        text  = (f"**AI Calling — Should You Activate It?**\n\n"
                 f"{'🚨 YES — Strongly Recommended' if m['ndr_pct'] > 15 else ('⚠️ Recommended' if m['ndr_count'] > 10 else '✅ Optional — low NDR volume')}\n\n"
                 f"- NDR shipments in queue: **{m['ndr_count']:,}** ({m['ndr_pct']:.1f}% of volume)\n"
                 f"- Stale NDRs (>48h): **{stale}** — escalation risk to RTO\n"
                 f"- AI Calling expected recovery: **38%** → **{expected_rec:,} shipments saved**\n"
                 f"- Revenue recovery: **₹{rev_rec:,}**\n\n"
                 f"**How it works:** AI IVR calls buyers in priority order (by recovery probability, state, NDR reason). "
                 f"Press 1 to reschedule, 2 to update address, 3 to connect to delivery partner.\n\n"
                 f"Go to **📞 AI Calling Engine** page to see the full priority queue.")
        return text, ["Show me the calling queue", "What about WhatsApp AI NDR?",
                      "Will Order Confirmation help?"], None

    # ── WhatsApp AI NDR ───────────────────────────────────────────────────────
    if any(x in ql for x in ["whatsapp", "whats app", "wa ", "wha"]):
        expected_save = int(m["rto_count"] * 0.08)
        rev_save      = int(expected_save * m["avg_order_value"])
        text  = (f"**WhatsApp AI NDR — Should You Activate It?**\n\n"
                 f"{'🚨 YES — High COD + High NDR' if (m['cod_pct']>60 and m['ndr_pct']>10) else ('⚠️ Recommended' if m['cod_pct']>50 else '✅ Optional')}\n\n"
                 f"- COD Share: **{m['cod_pct']:.1f}%** | COD-RTO Rate: **{cod_rto:.1f}%**\n"
                 f"- WhatsApp can reduce COD RTO by ~**8%** → save **{expected_save:,} shipments**\n"
                 f"- Revenue protected: **₹{rev_save:,}**\n\n"
                 f"**How it works:** When a COD delivery attempt fails, an AI-powered WhatsApp message "
                 f"is sent to the buyer with a reschedule link, address update option, and prepaid "
                 f"conversion nudge. Buyers respond 3x faster than calls for low-value orders.\n\n"
                 f"Best used alongside **AI Calling** for high-value COD orders (₹1000+).")
        return text, ["How does AI Calling compare?", "Will Order Confirmation help?",
                      "What's the COD-to-Prepaid conversion path?"], None

    # ── Order Confirmation Via AI ─────────────────────────────────────────────
    if any(x in ql for x in ["order confirm", "confirmation", "pre-dispatch", "predispatch",
                               "fake order", "intent", "bogus"]):
        expected_save = int(m["rto_count"] * 0.12)
        rev_save      = int(expected_save * m["avg_order_value"])
        text  = (f"**Order Confirmation Via AI — Should You Activate It?**\n\n"
                 f"{'🚨 YES — High RTO + COD risk' if (m['rto_pct']>15 or m['cod_pct']>50) else '✅ Nice to have'}\n\n"
                 f"- Current RTO Rate: **{m['rto_pct']:.1f}%** | COD Share: **{m['cod_pct']:.1f}%**\n"
                 f"- Fake/unintentional orders contribute ~12% of RTO in high-COD scenarios\n"
                 f"- AI Confirmation can prevent **{expected_save:,} RTOs** before dispatch\n"
                 f"- Revenue saved on shipping + return costs: **₹{rev_save:,}**\n\n"
                 f"**How it works:** After order placement, an AI call confirms delivery intent, "
                 f"address accuracy, and preferred time slot — before the shipment is dispatched. "
                 f"Reduces RTO from fake/impulsive COD orders by 10–15%.\n\n"
                 f"Works best combined with **WhatsApp AI NDR** for a complete NDR-prevention funnel.")
        return text, ["How does AI Calling compare?", "What about WhatsApp AI NDR?",
                      "Show me the full VAS plan"], None

    # ── ATS Address Verification ─────────────────────────────────────────────
    if any(x in ql for x in ["address verif", "address check", "ats address", "wrong address",
                               "incorrect address", "address quality"]):
        expected_save = int(m["total"] * 0.05)
        rev_save      = int(expected_save * m["avg_order_value"])
        text  = (f"**ATS Address Verification — New ATS Feature (Recommended)**\n\n"
                 f"{'🚨 Strongly Recommended' if m['rto_pct']>20 else '⚠️ Recommended'}\n\n"
                 f"- Current RTO Rate: **{m['rto_pct']:.1f}%** (threshold for benefit: > 20%)\n"
                 f"- Address-related RTO typically contributes 20–35% of total RTO\n"
                 f"- AI address correction at checkout can reduce RTO by **4–6%**\n"
                 f"- Estimated shipments saved: **{expected_save:,}** | Revenue: **₹{rev_save:,}**\n\n"
                 f"**How it works:** ATS (Amazon Transport Services) AI validates and auto-corrects "
                 f"delivery addresses at checkout using India Post PIN database + Google Maps APIs. "
                 f"**This is an ATS-partner feature** — Velocity is recommending it to eligible sellers.\n\n"
                 f"Best impact in: **{worst_st['state'] if worst_st is not None else 'high-RTO states'}** "
                 f"where address quality drives the most RTOs.")
        return text, ["Which states benefit most?", "Activate AI Calling too?",
                      "Show me full VAS plan"], None

    # ── VAS / recommendations ─────────────────────────────────────────────────
    if any(x in ql for x in ["vas", "recommend", "activate", "adopt", "what should i use",
                               "what products", "velocity products", "product plan"]):
        if not recs:
            return ("✅ All VAS triggers are within healthy limits. Your current VAS stack looks good.\n\n"
                    f"Health Score: **{hs:.0f}/100**. Keep monitoring NDR age and COD ratios.", [], None)
        text = f"**GDI VAS Recommendation Plan — {len(recs)} products triggered:**\n\n"
        total_rev = sum(r["revenue"] for r in recs)
        for i, r in enumerate(recs):
            rank = ["#1 Highest Impact","#2 High Impact","#3 Medium Impact","#4","#5"][min(i,4)]
            text += f"**{rank}: {r['name']}**\n- {r['impact']}\n- Revenue unlock: **₹{r['revenue']:,}**\n\n"
        text += f"**Total estimated revenue unlock: ₹{total_rev:,}**\n\nGo to 🚀 ATS Recommendations page for the full activation plan."
        chips = ["Tell me more about AI Calling", "Tell me about WhatsApp AI NDR",
                 "Tell me about Order Confirmation Via AI", "Open Impact Simulator"]
        return text, chips, None

    # ── COD / Payment mode ────────────────────────────────────────────────────
    if any(x in ql for x in ["cod", "prepaid", "cash on delivery", "payment", "payment mode"]):
        text = (f"**COD vs Prepaid Analysis:**\n\n"
                f"- COD Share: **{m['cod_pct']:.1f}%** ({m['cod_count']:,} shipments)\n"
                f"- COD RTO Rate: **{cod_rto:.1f}%** vs Prepaid RTO: **{prepaid_rto:.1f}%**\n"
                f"- COD Premium Risk: **+{cod_rto-prepaid_rto:.1f}%** extra RTO for COD orders\n\n")
        if m["cod_pct"] > 70:
            text += ("🚨 **High COD concentration.** Actions:\n"
                     "1. Offer 3–5% prepaid discount at checkout\n"
                     "2. Activate **WhatsApp AI NDR** to recover COD delivery failures\n"
                     "3. Enable **Order Confirmation Via AI** to filter fake COD orders\n"
                     "4. Restrict COD for high-risk state + high-RTO SKU combinations")
        elif m["cod_pct"] > 50:
            text += ("⚠️ Moderate COD risk. **WhatsApp AI NDR** will protect 8% of COD RTOs.")
        else:
            text += ("✅ COD share is manageable. Continue monitoring.")
        chart = None
        return text, ["Activate WhatsApp AI NDR", "Show state-wise COD breakdown",
                      "How to push prepaid conversions?"], chart

    # ── health score ─────────────────────────────────────────────────────────
    if any(x in ql for x in ["health", "score", "overall", "summary", "how am i doing"]):
        risk = "Low Risk ✅" if hs >= 80 else ("Medium Risk ⚠️" if hs >= 65 else "High Risk 🚨")
        fixes = []
        if m["rto_pct"] > 20:  fixes.append(f"RTO is {m['rto_pct']:.0f}% — activate Order Confirmation Via AI + Address Verification")
        if m["ndr_pct"] > 15:  fixes.append(f"NDR backlog — activate AI Calling now")
        if m["cod_pct"] > 70:  fixes.append(f"COD is {m['cod_pct']:.0f}% — launch WhatsApp AI NDR")
        fix_str = "\n".join(f"- {f}" for f in fixes) if fixes else "- No critical issues. Maintain current momentum."
        text = (f"**Health Score: {hs:.0f}/100 — {risk}**\n\n"
                f"- Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_pct']:.1f}%**\n"
                f"- Shipments: **{m['total']:,}** | COD: **{m['cod_pct']:.1f}%**\n\n"
                f"**Top actions to improve your score:**\n{fix_str}")
        return text, ["What's dragging my score?", "Show me the VAS plan",
                      "Show seller breakdown", "Which courier should I use?"], None

    # ── NDR ──────────────────────────────────────────────────────────────────
    if any(x in ql for x in ["ndr", "non delivery", "undelivered", "not delivered", "pending delivery"]):
        stale = len(df[(df.get("ndr_status","") == "Raised") & (df.get("ndr_age_hours", 0) > 48)]) \
                if ("ndr_status" in df.columns and "ndr_age_hours" in df.columns) else 0
        exp_rec = int(m["ndr_count"] * 0.38)
        text  = (f"**NDR Analysis:**\n\n"
                 f"- Total NDR: **{m['ndr_count']:,}** ({m['ndr_pct']:.1f}% of shipments)\n"
                 f"- Stale >48h: **{stale}** — high escalation risk\n"
                 f"- AI Calling expected recovery: **{exp_rec:,} shipments** (₹{int(exp_rec*m['avg_order_value']):,})\n"
                 f"- WhatsApp AI NDR: additional **8% COD RTO** recovery\n\n"
                 f"**Priority action:** Activate AI Calling. Go to 📞 AI Calling Engine for the priority queue.")
        return text, ["Open AI Calling queue", "Tell me about WhatsApp AI NDR",
                      "Which state has most NDRs?"], None

    # ── improve / action plan ────────────────────────────────────────────────
    if any(x in ql for x in ["improve", "how to", "action", "fix", "what should", "help me",
                               "steps", "plan", "roadmap", "recommendation", "advice"]):
        steps = []
        if m["delivery_pct"] < 75:
            steps.append(f"1. **Shift volume to {best_c['courier'] if best_c else 'top-performing courier'}** — best delivery in your mix")
        if m["rto_pct"] > 20:
            steps.append("2. **Activate Order Confirmation Via AI** — filter fake/unintentional COD orders before dispatch")
            steps.append("3. **Activate ATS Address Verification** — fix address-related RTO at checkout")
        if m["ndr_pct"] > 15:
            steps.append("4. **Launch AI Calling** — recover 38% of NDR shipments")
        if m["cod_pct"] > 60 and m["ndr_pct"] > 10:
            steps.append("5. **Enable WhatsApp AI NDR** — protect COD deliveries via WhatsApp engagement")
        if not steps:
            steps.append("1. VAS stack looks good. Focus on expanding to new states with your best courier.")
        total_unlock = sum(r["revenue"] for r in recs)
        text = ("**Your 30-Day GDI Action Plan:**\n\n" + "\n".join(steps) +
                f"\n\n💰 Total estimated revenue unlock: **₹{total_unlock:,}**\n"
                f"📈 Projected health score improvement: **+12–18 points**")
        return text, ["Tell me about AI Calling", "Tell me about WhatsApp AI NDR",
                      "Open Impact Simulator", "Show seller breakdown"], None

    # ── default / fallback ───────────────────────────────────────────────────
    mode_note = f"({len(all_sellers)} sellers loaded — admin view)" if is_admin else f"(Seller: {all_sellers[0] if all_sellers else 'All'})"
    text = (f"I have **{m['total']:,} shipments** analysed {mode_note}.\n\n"
            f"- Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_pct']:.1f}%**\n"
            f"- Health Score: **{hs:.0f}/100** | COD: **{m['cod_pct']:.1f}%** | Couriers: **{len(cour_df)}**\n\n"
            f"**I can answer questions about:**\n"
            f"- Specific sellers (e.g. 'How is Brand Alpha doing?')\n"
            f"- Top selling / worst products (e.g. 'Show top selling products')\n"
            f"- Couriers & 3PLs (e.g. 'How is Delhivery performing?')\n"
            f"- VAS guidance (e.g. 'Will AI Calling help?', 'Should I use WhatsApp NDR?')\n"
            f"- States & RTO (e.g. 'Which state is causing most RTO?')\n"
            f"- COD & payment strategy (e.g. 'How does COD affect RTO?')")
    chips = ["Show top selling products", "Compare all sellers", "Will AI Calling help?",
             "Which courier is best?", "Which state has worst RTO?", "Show me my health score"]
    return text, chips, None


# ── PAGE LAYOUT ────────────────────────────────────────────────────────────────

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🤖 Ask GDI Agent</h1>
  <p class="header-subtitle">Your AI Delivery Intelligence Consultant — grounded in your actual shipment data. Ask anything.</p>
</div>""", unsafe_allow_html=True)

# Live stats bar
risk_color = "#34D399" if hs >= 80 else ("#FBBF24" if hs >= 65 else "#F87171")
st.markdown(f"""
<div class="top-bar">
  <div class="top-stat">
    <div class="top-stat-v" style="color:{risk_color};">{hs:.0f}/100</div>
    <div class="top-stat-l">Health Score</div>
  </div>
  <div style="width:1px;background:#1F2937;height:36px;"></div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#34D399;">{m['delivery_pct']:.1f}%</div>
    <div class="top-stat-l">Delivery Rate</div>
  </div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#F87171;">{m['rto_pct']:.1f}%</div>
    <div class="top-stat-l">RTO Rate</div>
  </div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#FBBF24;">{m['ndr_pct']:.1f}%</div>
    <div class="top-stat-l">NDR Rate</div>
  </div>
  <div style="width:1px;background:#1F2937;height:36px;"></div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#60A5FA;">{m['total']:,}</div>
    <div class="top-stat-l">Shipments</div>
  </div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#C084FC;">{len(all_sellers)}</div>
    <div class="top-stat-l">Sellers</div>
  </div>
  <div class="top-stat">
    <div class="top-stat-v" style="color:#818CF8;">{len(cour_df)}</div>
    <div class="top-stat-l">Couriers</div>
  </div>
  {"<div style='margin-left:auto;background:rgba(79,70,229,0.12);border:1px solid rgba(79,70,229,0.3);padding:6px 14px;border-radius:8px;color:#818CF8;font-size:0.82rem;font-weight:700;'>👤 Admin View — " + str(len(all_sellers)) + " Sellers</div>" if is_admin else ""}
</div>""", unsafe_allow_html=True)

# Top products chart (always visible)
if "product_name" in df.columns:
    with st.expander("📊 Top Selling Products — Overview", expanded=False):
        top_prod = (df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
            revenue=("order_value","sum"),
        ).reset_index().sort_values("delivered", ascending=False).head(10))
        top_prod["rto_rate"] = top_prod["rto"] / top_prod["total"] * 100
        c1, c2 = st.columns(2)
        with c1:
            fig_v = px.bar(top_prod, x="product_name", y="delivered",
                           title="Top 10 Products by Deliveries",
                           color="delivered",
                           color_continuous_scale=["#4F46E5","#818CF8"],
                           labels={"product_name":"Product","delivered":"Delivered Units"})
            fig_v.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font_color="#F3F4F6", height=300,
                                margin=dict(l=0,r=0,t=36,b=0), showlegend=False,
                                coloraxis_showscale=False,
                                xaxis_tickangle=-30)
            st.plotly_chart(fig_v, use_container_width=True)
        with c2:
            fig_r = px.bar(top_prod, x="product_name", y="rto_rate",
                           title="RTO Rate % by Product",
                           color="rto_rate",
                           color_continuous_scale=["#10B981","#EF4444"],
                           labels={"product_name":"Product","rto_rate":"RTO %"})
            fig_r.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                                font_color="#F3F4F6", height=300,
                                margin=dict(l=0,r=0,t=36,b=0), showlegend=False,
                                coloraxis_showscale=False,
                                xaxis_tickangle=-30)
            st.plotly_chart(fig_r, use_container_width=True)

st.markdown("---")

# Quick chips
quick_qs = [
    "Show top selling products", "Compare all sellers",
    "Will AI Calling help me?", "Should I use WhatsApp AI NDR?",
    "Which courier is performing best?", "Which state has worst RTO?",
    "What is my health score?", "Tell me about Order Confirmation Via AI",
]
cols = st.columns(4)
selected_q = None
for i, qq in enumerate(quick_qs):
    if cols[i % 4].button(qq, key=f"qchip_{i}", use_container_width=True):
        selected_q = qq

# Init chat
if "gdi_chat" not in st.session_state:
    ws_name = worst_st["state"] if worst_st is not None else "N/A"
    ws_rto  = f"{worst_st['rto_rate']:.0f}%" if worst_st is not None else "N/A"
    mode_str = f"Viewing **{len(all_sellers)} sellers** in admin mode." if is_admin else f"Viewing **{all_sellers[0] if all_sellers else 'All'}** data."
    opener = (f"I've analysed your **{m['total']:,} shipments**. {mode_str} "
              f"Health Score: **{hs:.0f}/100**. "
              f"Biggest RTO hotspot: **{ws_name}** at {ws_rto} RTO rate. "
              f"You have **{m['ndr_count']} active NDRs** — "
              f"AI Calling can recover ~{int(m['ndr_count']*0.38)} of them.\n\n"
              f"Ask me about any seller, product, courier, or VAS product 👇")
    st.session_state["gdi_chat"] = [{"role":"assistant","content":opener,"chips":[
        "Show top selling products","Compare all sellers",
        "Will AI Calling help?","Which courier is best?"
    ],"chart":None}]

# Render chat
st.markdown('<div class="chat-wrap">', unsafe_allow_html=True)
for msg in st.session_state["gdi_chat"]:
    if msg["role"] == "user":
        st.markdown(f'<div class="user-label">You</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="agent-label">🤖 GDI Agent</div>', unsafe_allow_html=True)
        st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("chart"):
            render_chart(msg["chart"])
        if msg.get("chips"):
            chip_html = "".join(f'<span class="chip-quick">{c}</span>' for c in msg["chips"])
            st.markdown(f"<div style='margin:6px 0 18px 0;'>{chip_html}</div>", unsafe_allow_html=True)
st.markdown("</div>", unsafe_allow_html=True)

# Input
user_input = st.chat_input("Ask about sellers, products, couriers, VAS, RTO, NDR…")
if selected_q or user_input:
    prompt = selected_q or user_input
    st.session_state["gdi_chat"].append({"role":"user","content":prompt,"chips":None,"chart":None})
    answer, follow_ups, chart_data = reply(prompt)
    st.session_state["gdi_chat"].append({
        "role":"assistant","content":answer,
        "chips":follow_ups,"chart":chart_data,
    })
    st.rerun()

# Footer controls
col_clear, col_export = st.columns([1, 5])
with col_clear:
    if st.button("🗑 Clear Chat"):
        del st.session_state["gdi_chat"]
        st.rerun()
