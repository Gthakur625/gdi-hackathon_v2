import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                           compute_sku_perf, compute_courier_perf, compute_state_perf,
                           get_recommendations)

st.set_page_config(page_title="AI Chat Assistant · GDI", page_icon="🤖", layout="wide")
apply_styles()
df = render_sidebar_and_get_data()

m          = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
hs         = compute_health_score(m)
recs       = get_recommendations(m)
sku_df     = compute_sku_perf(df)
cour_df    = compute_courier_perf(df)
state_df   = compute_state_perf(df)

cod_df     = df[df["payment_type"]=="COD"]
prepaid_df = df[df["payment_type"]=="Prepaid"]
cod_rto    = len(cod_df[cod_df["delivery_status"]=="RTO"]) / max(len(cod_df),1) * 100
prepaid_rto= len(prepaid_df[prepaid_df["delivery_status"]=="RTO"]) / max(len(prepaid_df),1) * 100

best_courier  = cour_df.sort_values("delivery_rate",ascending=False).iloc[0] if len(cour_df)>0 else None
worst_courier = cour_df.sort_values("delivery_rate").iloc[0] if len(cour_df)>0 else None
worst_state   = state_df.sort_values("rto_rate",ascending=False).iloc[0] if len(state_df)>0 else None
worst_sku     = sku_df.iloc[0] if len(sku_df)>0 else None

def build_context():
    return {
        "m":m, "hs":hs, "recs":recs, "cod_rto":cod_rto, "prepaid_rto":prepaid_rto,
        "best_courier":best_courier, "worst_courier":worst_courier,
        "worst_state":worst_state, "worst_sku":worst_sku,
    }

def reply(q):
    q = q.lower().strip()
    c = build_context()
    bc = c["best_courier"]; wc = c["worst_courier"]; ws = c["worst_state"]; wsku = c["worst_sku"]

    # Health score
    if any(x in q for x in ["health","score","overall"]):
        risk = "Low Risk ✅" if c["hs"]>=80 else ("Medium Risk ⚠️" if c["hs"]>=65 else "High Risk 🚨")
        fixes = []
        if c["m"]["rto_pct"]>20:  fixes.append(f"RTO is {c['m']['rto_pct']:.0f}% — activate Address Verification")
        if c["m"]["ndr_pct"]>15:  fixes.append(f"NDR is {c['m']['ndr_pct']:.0f}% — launch AI Calling")
        if c["m"]["cod_pct"]>70:  fixes.append(f"COD is {c['m']['cod_pct']:.0f}% — add prepaid nudge")
        fix_str = " | ".join(fixes) if fixes else "Keep up current performance."
        return (f"**Your Health Score is {c['hs']:.0f}/100 — {risk}**\n\n"
                f"Delivery: **{c['m']['delivery_pct']:.1f}%** | RTO: **{c['m']['rto_pct']:.1f}%** | "
                f"NDR: **{c['m']['ndr_pct']:.1f}%**\n\n"
                f"Top fixes: {fix_str}",
                ["What's dragging my score?","Which VAS should I adopt?"])

    # Delivery dropping
    if any(x in q for x in ["delivery drop","why is delivery","falling","dropping","low delivery"]):
        causes = []
        if wc is not None:
            causes.append(f"**{wc['courier']}** delivers only {wc['delivery_rate']:.1f}% (your worst courier)")
        if ws is not None:
            causes.append(f"**{ws['state']}** drives {ws['rto_rate']:.1f}% RTO (geographic cluster)")
        if c["m"]["cod_pct"]>70:
            causes.append(f"**{c['m']['cod_pct']:.0f}% COD share** with {c['cod_rto']:.1f}% COD-RTO rate")
        cause_str = "\n".join(f"- {x}" for x in causes)
        return (f"**Delivery is at {c['m']['delivery_pct']:.1f}% — here's why:**\n\n{cause_str}\n\n"
                f"Fixing all three can recover up to **{int(c['m']['total']*0.08)} shipments/week**.",
                ["Which courier should I switch to?","Which state should I fix first?"])

    # Courier
    if any(x in q for x in ["courier","carrier","shipping partner","partner"]):
        worst_str = f"**{wc['courier']}** is your weakest at {wc['delivery_rate']:.1f}% delivery and {wc['rto_rate']:.1f}% RTO." if wc is not None else ""
        best_str  = f"**{bc['courier']}** tops the leaderboard at {bc['delivery_rate']:.1f}% delivery." if bc is not None else ""
        return (f"**Courier Recommendation:**\n\n"
                f"✅ Route to: {best_str}\n\n"
                f"❌ Reduce: {worst_str}\n\n"
                f"Shift at least 30–40% of non-ATS volume to **{bc['courier'] if bc is not None else 'ATS (Velocity)'}** immediately.",
                ["What's the delivery gap between couriers?","How do I set routing rules?"])

    # SKU
    if any(x in q for x in ["sku","product","item","underperform","which product"]):
        if wsku is not None:
            cat = wsku.get("sku_category","") if hasattr(wsku,"get") else ""
            return (f"**Worst Performing SKU: {wsku['sku']} — {wsku['product_name']}**\n\n"
                    f"- RTO Rate: **{wsku['rto_rate']:.1f}%** (vs avg {c['m']['rto_pct']:.1f}%)\n"
                    f"- Category: {cat}\n"
                    f"- Revenue at Risk: **₹{wsku['revenue_at_risk']:,.0f}**\n\n"
                    f"Recommended fix: Restrict COD for this SKU in high-risk states like Bihar/UP.",
                    ["Show me all critical SKUs","How do I fix this SKU?"])
        return ("No SKU data available in the current filter.", [])

    # State / RTO
    if any(x in q for x in ["state","rto","return","bihar","which state","geographic"]):
        if ws is not None:
            share = ws["rto"] / max(c["m"]["rto_count"],1) * 100
            return (f"**{ws['state']} is your RTO hotspot.**\n\n"
                    f"- Contributes **{share:.0f}%** of all RTOs ({int(ws['rto'])} shipments)\n"
                    f"- RTO rate in {ws['state']}: **{ws['rto_rate']:.1f}%**\n"
                    f"- Root cause: address quality + COD non-acceptance\n\n"
                    f"Fix: Enable **ATS Address Verification** for {ws['state']} orders at checkout.",
                    ["What VAS fixes this?","Show me all state RTO data"])
        return ("No state RTO data found.", [])

    # VAS
    if any(x in q for x in ["vas","velocity","activate","adopt","product","recommend"]):
        if not c["recs"]:
            return ("All recommended VAS products appear to be active already! "
                    f"Your health score is {c['hs']:.0f}/100.", [])
        top = c["recs"][0]
        others = ", ".join(r["name"] for r in c["recs"][1:3])
        return (f"**Top VAS Recommendation: {top['name']}**\n\n"
                f"- Impact: {top['impact']}\n"
                f"- Revenue unlock: **₹{top['revenue']:,}**\n\n"
                f"Also consider: {others}\n\n"
                f"Total potential revenue unlock across all recommended VAS: "
                f"**₹{sum(r['revenue'] for r in c['recs']):,}**",
                ["How much will this cost?","Show me the full VAS plan"])

    # Revenue / savings
    if any(x in q for x in ["save","revenue","money","impact","₹","rupee","how much"]):
        total_rev = sum(r["revenue"] for r in c["recs"])
        additional = max(0, int(c["m"]["total"] * ((c["m"]["delivery_pct"]+8)/100 - c["m"]["delivery_pct"]/100)))
        avg_ov = df["order_value"].mean() if len(df)>0 else 0
        return (f"**Revenue Impact Analysis:**\n\n"
                f"- Current Revenue at Risk (RTO): **₹{int(c['m']['rto_count']*avg_ov):,}**\n"
                f"- Activating recommended VAS can unlock: **₹{total_rev:,}**\n"
                f"- Expected additional deliveries/month: **+{additional}**\n\n"
                f"Go to the **Impact Simulator** page to model specific scenarios.",
                ["Open Impact Simulator","Which VAS gives best ROI?"])

    # NDR
    if any(x in q for x in ["ndr","non delivery","undelivered","pending"]):
        ndr_stale = df[(df["ndr_status"]=="Raised") & (df.get("ndr_age_hours",0)>48)].pipe(len) if "ndr_age_hours" in df.columns else 0
        return (f"**NDR Analysis:**\n\n"
                f"- Total NDR shipments: **{c['m']['ndr_count']}** ({c['m']['ndr_pct']:.1f}%)\n"
                f"- Stale NDRs (>48h unresolved): **{ndr_stale}** — escalation risk\n\n"
                f"**Recommended action:** Activate AI Calling for the top 47 shipments by recovery probability. "
                f"Expected 38% recovery rate = ~{int(c['m']['ndr_count']*0.38)} shipments saved.",
                ["Show me the calling queue","Activate AI Calling"])

    # Improve
    if any(x in q for x in ["improve","how to","action","fix","what should","help me","steps"]):
        steps = []
        if c["m"]["delivery_pct"] < 75: steps.append(f"1. **Shift volume to {bc['courier'] if bc else 'ATS'}** — best delivery rate")
        if c["m"]["rto_pct"] > 20:      steps.append("2. **Enable ATS Address Verification** — reduce RTO 4–6%")
        if c["m"]["ndr_pct"] > 15:      steps.append("3. **Activate AI Calling** — recover 38% of NDR shipments")
        if c["m"]["cod_pct"] > 70:      steps.append("4. **Launch WhatsApp NDR** — reduce COD RTO 8%")
        if not steps:                    steps.append("1. Maintain current performance. Focus on VAS adoption.")
        return ("**Your 30-Day Improvement Plan:**\n\n" + "\n".join(steps) +
                f"\n\nProjected health score improvement: **+12–18 points**",
                ["Show my health score","Open Impact Simulator"])

    # Default
    return (f"I have **{c['m']['total']:,} shipments** analysed. Here's a quick snapshot:\n\n"
            f"- Delivery: **{c['m']['delivery_pct']:.1f}%** | RTO: **{c['m']['rto_pct']:.1f}%** | "
            f"NDR: **{c['m']['ndr_pct']:.1f}%**\n"
            f"- Health Score: **{c['hs']:.0f}/100**\n\n"
            f"Ask me anything about your operations 👇",
            ["Why is delivery dropping?","Which courier should I use?",
             "Which SKU is underperforming?","Which VAS should I adopt?"])


st.markdown("""
<div class="header-card">
  <h1 class="header-title">🤖 GDI AI Consultant</h1>
  <p class="header-subtitle">Ask anything about your delivery operations. Every answer is grounded in your actual shipment data.</p>
</div>""", unsafe_allow_html=True)

# Init history with proactive opener
if "gdi_chat" not in st.session_state:
    worst_issue = "delivery dropping" if m["delivery_pct"]<75 else ("high RTO" if m["rto_pct"]>20 else "NDR backlog")
    ws_name = worst_state["state"] if worst_state is not None else "N/A"
    opener = (f"I've analysed your **{m['total']:,} shipments**. "
              f"Your health score is **{hs:.0f}/100**. "
              f"Biggest issue right now: **{worst_issue}** — "
              f"**{ws_name}** is driving {int(worst_state['rto_rate']) if worst_state is not None else 'N/A'}% RTO. "
              f"Want me to show you exactly what's wrong and what to do?")
    st.session_state["gdi_chat"] = [{"role":"assistant","content":opener,"chips":[
        "Why is delivery dropping?","Which courier should I use?",
        "Which SKU is underperforming?","Which VAS should I adopt?"
    ]}]

# Quick question chips
st.markdown("<div style='margin-bottom:12px;'>", unsafe_allow_html=True)
qs = ["Why is delivery dropping?","Which courier should I use?",
      "Which SKU is underperforming?","Which state is causing RTO?",
      "Which VAS should I adopt?","How much revenue can I save?"]
cols = st.columns(len(qs))
selected_q = None
for i, q in enumerate(qs):
    if cols[i].button(q, key=f"chip_{i}"):
        selected_q = q
st.markdown("</div>", unsafe_allow_html=True)

# Render chat
for msg in st.session_state["gdi_chat"]:
    if msg["role"]=="user":
        st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)
        if msg.get("chips"):
            chip_html = "".join(
                f'<span class="chip-btn">{c}</span>' for c in msg["chips"]
            )
            st.markdown(f"<div style='margin-bottom:12px;'>{chip_html}</div>", unsafe_allow_html=True)

# Input
user_input = st.chat_input("Ask about your shipments, couriers, SKUs, VAS products…")
if selected_q or user_input:
    prompt = selected_q or user_input
    st.session_state["gdi_chat"].append({"role":"user","content":prompt})
    answer, follow_ups = reply(prompt)
    st.session_state["gdi_chat"].append({"role":"assistant","content":answer,"chips":follow_ups})
    st.rerun()

if st.button("🗑 Clear Chat"):
    del st.session_state["gdi_chat"]
    st.rerun()
