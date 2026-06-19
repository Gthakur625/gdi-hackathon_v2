"""
Inline GDI Agent chat dialog — opened via floating Joker icon.
Call render_chat_button(df) from any page to add the floating Joker trigger.
"""
import streamlit as st
import pandas as pd
import re
from utils.metrics import (compute_kpis, compute_health_score, compute_vas_adoption_score,
                            compute_courier_perf, compute_state_perf, get_recommendations)


def _words(s):
    return set(re.sub(r'[^\w\s]', ' ', s.lower()).split())


def _find(q_lower, candidates):
    for name in sorted(candidates, key=len, reverse=True):
        if name.lower() in q_lower:
            return name
    for name in candidates:
        ws = [w for w in _words(name) if len(w) >= 5]
        if ws and any(w in q_lower for w in ws):
            return name
    return None


def _sim_card(title, rows):
    rows_html = "".join(
        f'<div class="sim-row">'
        f'<span style="color:#9CA3AF;">{r[0]}</span>'
        f'<span style="color:{"#34D399" if r[2] else "#FFFFFF"};font-weight:{"800" if r[2] else "600"};">{r[1]}</span>'
        f'</div>'
        for r in rows
    )
    st.markdown(
        f'<div class="sim-card">'
        f'<div style="color:#818CF8;font-weight:800;font-size:0.9rem;margin-bottom:10px;">📊 {title}</div>'
        f'{rows_html}</div>',
        unsafe_allow_html=True,
    )


def _quick_reply(q, df, m, hs, cour_df, state_df, all_sellers):
    """Compact reply function for the dialog chat."""
    ql  = q.lower().strip()
    qw  = _words(ql)

    def has(*p): return any(x in ql for x in p)
    def hasw(*w): return any(x in qw for x in w)

    cod_df   = df[df["payment_type"] == "COD"]
    prep_df  = df[df["payment_type"] == "Prepaid"]
    cod_rto  = len(cod_df[cod_df["delivery_status"] == "RTO"])   / max(len(cod_df), 1)  * 100
    prep_rto = len(prep_df[prep_df["delivery_status"] == "RTO"]) / max(len(prep_df), 1) * 100

    best_c  = cour_df.sort_values("delivery_rate", ascending=False).iloc[0] if len(cour_df) > 0 else None
    worst_c = cour_df.sort_values("delivery_rate").iloc[0]                  if len(cour_df) > 0 else None
    worst_st= state_df.sort_values("rto_rate", ascending=False).iloc[0]     if len(state_df) > 0 else None

    sel  = _find(ql, all_sellers)
    cour = _find(ql, cour_df["courier"].tolist() if len(cour_df) > 0 else [])
    stat = _find(ql, state_df["state"].tolist()  if len(state_df) > 0 else [])
    prod = _find(ql, df["product_name"].unique().tolist()) if "product_name" in df.columns else None

    if has("ai calling", "simulate call", "ndr recovery", "calling benefit") \
       or (hasw("calling", "call") and hasw("simulate", "benefit", "help", "impact")):
        rec = int(m["ndr_count"] * 0.38)
        rev = int(rec * m["avg_order_value"])
        _sim_card("AI Calling — NDR Recovery Simulation", [
            ("NDR Queue",               f"{m['ndr_count']:,} active",                    False),
            ("Recovery Rate",           "38%",                                           False),
            ("Shipments Recovered",     f"{rec:,} / month",                              False),
            ("Revenue Recovered",       f"₹{rev:,} / month",                            True),
            ("Total Value Unlocked",    f"₹{rev + int(m['ndr_count']*0.15*80):,}/month",True),
        ])
        return f"AI Calling can recover **{rec:,} NDR shipments** → **₹{rev:,}/month**. See simulation above."

    if has("whatsapp", "whats app") or (hasw("whatsapp", "wa") and hasw("simulate", "benefit", "help")):
        saved = int(m["rto_count"] * 0.08)
        rev   = int(saved * m["avg_order_value"])
        _sim_card("WhatsApp AI NDR — Simulation", [
            ("COD Share",              f"{m['cod_pct']:.1f}%",                           False),
            ("COD-RTO Rate",           f"{cod_rto:.1f}%",                                False),
            ("RTOs Prevented",         f"{saved:,} / month",                             False),
            ("Revenue Protected",      f"₹{rev:,} / month",                             True),
        ])
        return f"WhatsApp AI NDR prevents **{saved:,} RTOs/month** → **₹{rev:,}** revenue protected."

    if has("order confirm", "confirmation", "fake order", "pre-dispatch"):
        saved = int(m["rto_count"] * 0.12)
        rev   = int(saved * m["avg_order_value"])
        _sim_card("Order Confirmation Via AI — Simulation", [
            ("Current RTO Rate",       f"{m['rto_pct']:.1f}%",                           False),
            ("Fake Orders (est.)",     "~12% of RTOs",                                   False),
            ("Orders Saved",           f"{saved:,} / month",                             False),
            ("Revenue Impact",         f"₹{rev:,} / month",                             True),
        ])
        return f"Order Confirmation prevents **{saved:,} RTOs/month** before dispatch."

    if sel:
        s_df = df[df["seller_name"] == sel]
        sm   = compute_kpis(s_df); sm["vas_adoption_score"] = compute_vas_adoption_score(s_df)
        sh   = compute_health_score(sm)
        risk = "Low Risk" if sh>=80 else ("Medium Risk" if sh>=65 else "High Risk")
        return (f"**{sel}** — {risk} · Health **{sh:.0f}/100**\n\n"
                f"- Delivery: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | NDR: **{sm['ndr_count']:,}**\n"
                f"- Shipments: **{sm['total']:,}** | COD: **{sm['cod_pct']:.1f}%** | Avg: **₹{sm['avg_order_value']:,.0f}**")

    if has("all seller", "compare seller", "seller list") \
       or (hasw("seller", "sellers", "client", "clients") and hasw("all", "compare", "list", "rank")):
        sg = df.groupby("seller_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
        ).reset_index()
        sg["dr"] = sg["delivered"]/sg["total"]*100; sg["rr"] = sg["rto"]/sg["total"]*100
        sg = sg.sort_values("dr", ascending=False)
        out = f"**{len(sg)} Sellers — Ranking:**\n\n"
        for _, r in sg.iterrows():
            e = "✅" if r["dr"]>=80 else ("⚠️" if r["dr"]>=65 else "🚨")
            out += f"{e} **{r['seller_name']}** — {r['dr']:.1f}% del | {r['rr']:.1f}% RTO | {r['total']:,} shpts\n"
        return out

    if has("top product", "top selling", "best selling", "popular") \
       or (hasw("top", "best", "popular") and hasw("product", "sku", "selling")):
        if "product_name" not in df.columns:
            return "No product data available."
        grp = df.groupby("product_name").agg(
            total=("delivery_status","count"),
            delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
        ).reset_index()
        grp["dr"] = grp["delivered"]/grp["total"]*100
        top5 = grp.sort_values("delivered", ascending=False).head(5)
        out = "**Top Selling Products:**\n\n"
        for _, r in top5.iterrows():
            out += f"- **{r['product_name']}** — {r['delivered']:,} delivered ({r['dr']:.0f}%)\n"
        return out

    if prod:
        p_df = df[df["product_name"] == prod]
        pm   = compute_kpis(p_df)
        return (f"**{prod}:**\n\n"
                f"- Orders: **{pm['total']:,}** | Delivered: **{pm['delivered']:,}** ({pm['delivery_pct']:.1f}%)\n"
                f"- RTO: **{pm['rto_count']:,}** ({pm['rto_pct']:.1f}%) | COD: **{pm['cod_pct']:.1f}%**\n"
                f"- Avg Value: **₹{pm['avg_order_value']:,.0f}**")

    if cour or has("courier", "3pl") or hasw("couriers", "carrier"):
        if cour:
            r = cour_df[cour_df["courier"] == cour].iloc[0] if len(cour_df[cour_df["courier"]==cour])>0 else None
            if r is not None:
                return (f"**{cour}:** {r['total']:,} shpts | Delivery: **{r['delivery_rate']:.1f}%** | RTO: **{r['rto_rate']:.1f}%**")
        out = f"**{len(cour_df)} Courier Partners:**\n\n"
        for _, r in cour_df.sort_values("delivery_rate", ascending=False).iterrows():
            e = "✅" if r["delivery_rate"]>=80 else ("⚠️" if r["delivery_rate"]>=70 else "🚨")
            out += f"{e} **{r['courier']}** — {r['delivery_rate']:.1f}% del | {r['rto_rate']:.1f}% RTO\n"
        return out

    if stat or has("state", "location", "geographic") or hasw("states", "region"):
        if stat:
            r = state_df[state_df["state"]==stat]
            if len(r)>0:
                r=r.iloc[0]
                return f"**{stat}:** {r['total']:,} shpts | RTO: **{r['rto_rate']:.1f}%** | Delivery: **{r['delivery_rate']:.1f}%**"
        out = "**Top States by RTO:**\n\n"
        for _, r in state_df.sort_values("rto_rate", ascending=False).head(6).iterrows():
            e = "🚨" if r["rto_rate"]>30 else ("⚠️" if r["rto_rate"]>20 else "✅")
            out += f"{e} **{r['state']}** — {r['rto_rate']:.1f}% RTO\n"
        return out

    if has("rto", "high rto", "reduce rto") or (hasw("rto", "return") and hasw("why", "high", "cause", "fix")):
        return (f"**RTO at {m['rto_pct']:.1f}%** — 3 main causes:\n\n"
                f"- {worst_c['courier'] if worst_c else 'Weakest courier'} delivering only {worst_c['delivery_rate']:.1f}%\n"
                f"- {worst_st['state'] if worst_st else 'High-RTO state'} at {worst_st['rto_rate']:.1f}% RTO\n"
                f"- COD {m['cod_pct']:.1f}% share with {cod_rto:.1f}% COD-RTO rate\n\n"
                f"**Fix:** Order Confirmation → WhatsApp NDR → AI Calling")

    if has("health", "score", "overall", "summary") or hasw("health", "score", "overall"):
        risk = "Low Risk" if hs>=80 else ("Medium Risk" if hs>=65 else "High Risk")
        return (f"**Health: {hs:.0f}/100 — {risk}**\n\n"
                f"- Delivery: **{m['delivery_pct']:.1f}%** | RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_count']:,}**\n"
                f"- Shipments: **{m['total']:,}** | COD: **{m['cod_pct']:.1f}%**")

    if has("cod", "prepaid", "payment") or hasw("cod", "prepaid", "payment"):
        return (f"**COD vs Prepaid:**\n\n"
                f"- COD: **{m['cod_pct']:.1f}%** | COD-RTO: **{cod_rto:.1f}%**\n"
                f"- Prepaid: **{100-m['cod_pct']:.1f}%** | Prepaid-RTO: **{prep_rto:.1f}%**\n"
                f"- Premium risk: **+{cod_rto-prep_rto:.1f}%** extra RTO for COD")

    return (f"**{m['total']:,} shipments** · Delivery **{m['delivery_pct']:.1f}%** · RTO **{m['rto_pct']:.1f}%**\n\n"
            f"Try: *Simulate AI Calling · Compare sellers · Top products · Why is RTO high?*")


@st.dialog("🃏 GDI Agent — Ask Me Anything", width="large")
def chat_dialog(df):
    """Inline chat popup — no page navigation needed."""
    m   = compute_kpis(df)
    m["vas_adoption_score"] = compute_vas_adoption_score(df)
    hs  = compute_health_score(m)
    cour_df  = compute_courier_perf(df)
    state_df = compute_state_perf(df)
    all_sellers = sorted(df["seller_name"].unique().tolist()) if "seller_name" in df.columns else []

    rc = "#34D399" if hs>=80 else ("#FBBF24" if hs>=65 else "#F87171")
    st.markdown(f"""
    <div style="display:flex;gap:20px;background:#111827;border-radius:10px;
                padding:12px 16px;margin-bottom:14px;flex-wrap:wrap;">
      <div><b style="color:{rc};">{hs:.0f}/100</b>
           <div style="color:#6B7280;font-size:0.7rem;">Health</div></div>
      <div><b style="color:#34D399;">{m['delivery_pct']:.1f}%</b>
           <div style="color:#6B7280;font-size:0.7rem;">Delivery</div></div>
      <div><b style="color:#F87171;">{m['rto_pct']:.1f}%</b>
           <div style="color:#6B7280;font-size:0.7rem;">RTO</div></div>
      <div><b style="color:#FBBF24;">{m['ndr_count']:,}</b>
           <div style="color:#6B7280;font-size:0.7rem;">NDR</div></div>
      <div><b style="color:#60A5FA;">{m['total']:,}</b>
           <div style="color:#6B7280;font-size:0.7rem;">Shipments</div></div>
    </div>""", unsafe_allow_html=True)

    quick = ["Simulate AI Calling", "Simulate WhatsApp NDR", "Simulate Order Confirmation",
             "Compare all sellers", "Top selling products", "Why is RTO high?",
             "Show courier performance", "My health score"]
    c1, c2, c3, c4 = st.columns(4)
    sel_q = None
    for i, qq in enumerate(quick):
        if [c1, c2, c3, c4][i % 4].button(qq, key=f"dchip_{i}", use_container_width=True):
            sel_q = qq

    st.markdown("---")

    if "dialog_chat" not in st.session_state:
        st.session_state["dialog_chat"] = []

    for msg in st.session_state["dialog_chat"]:
        if msg["role"] == "user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(f'<div class="chat-bubble-bot">{msg["content"]}</div>', unsafe_allow_html=True)

    user_input = st.chat_input("Ask about sellers, products, couriers, simulations…")
    if sel_q or user_input:
        prompt = sel_q or user_input
        st.session_state["dialog_chat"].append({"role": "user",   "content": prompt})
        answer = _quick_reply(prompt, df, m, hs, cour_df, state_df, all_sellers)
        st.session_state["dialog_chat"].append({"role": "assistant", "content": answer})
        st.rerun()

    if st.session_state["dialog_chat"]:
        if st.button("🗑 Clear", key="dlg_clear"):
            st.session_state["dialog_chat"] = []
            st.rerun()


def render_chat_button(df):
    """Floating Joker icon in the bottom-right corner — opens GDI Agent dialog.
    Uses st.markdown to inject directly into the page (not an iframe)."""

    # The actual Streamlit button (visible but styled as floating joker via CSS)
    if st.button("🃏 Ask GDI Agent", key="joker_trigger_btn", type="primary"):
        chat_dialog(df)

    # Inject CSS + JS to transform the button into a floating joker icon
    st.markdown("""
    <style>
    /* Target the joker button specifically and make it float */
    div[data-testid="stBottom"] ~ div button[kind="primary"]:last-of-type,
    button[kind="primary"] {
        /* don't touch other primary buttons */
    }
    </style>

    <!-- Floating Joker Icon (pure HTML, injected into page DOM) -->
    <div id="gdi-joker-float" style="
        position:fixed; bottom:28px; right:28px; z-index:999999;
        width:68px; height:68px; border-radius:50%;
        background:linear-gradient(135deg,#7C3AED 0%,#4F46E5 50%,#6D28D9 100%);
        border:3px solid rgba(255,255,255,0.18);
        box-shadow:0 6px 28px rgba(124,58,237,0.5),0 0 0 4px rgba(124,58,237,0.12);
        cursor:pointer; display:flex; align-items:center; justify-content:center;
        transition:all 0.3s cubic-bezier(0.4,0,0.2,1);
        animation:gdi-jpulse 2.5s ease-in-out infinite;
    ">
        <svg viewBox="0 0 100 100" width="42" height="42" xmlns="http://www.w3.org/2000/svg">
          <circle cx="50" cy="50" r="42" fill="#7C3AED" stroke="#A78BFA" stroke-width="2"/>
          <path d="M15 38 Q25 5 50 20 Q75 5 85 38" fill="#4F46E5" stroke="#818CF8" stroke-width="1.5"/>
          <circle cx="25" cy="12" r="5" fill="#FBBF24"/>
          <circle cx="75" cy="12" r="5" fill="#F87171"/>
          <circle cx="50" cy="5" r="5" fill="#34D399"/>
          <ellipse cx="36" cy="48" rx="5" ry="6" fill="white"/>
          <ellipse cx="64" cy="48" rx="5" ry="6" fill="white"/>
          <circle cx="37" cy="47" r="2.5" fill="#1F2937"/>
          <circle cx="65" cy="47" r="2.5" fill="#1F2937"/>
          <circle cx="38" cy="46" r="1" fill="white"/>
          <circle cx="66" cy="46" r="1" fill="white"/>
          <ellipse cx="28" cy="58" rx="6" ry="3.5" fill="rgba(248,113,113,0.35)"/>
          <ellipse cx="72" cy="58" rx="6" ry="3.5" fill="rgba(248,113,113,0.35)"/>
          <path d="M32 62 Q50 82 68 62" fill="none" stroke="white" stroke-width="3" stroke-linecap="round"/>
          <path d="M36 64 Q50 78 64 64" fill="#FBBF24" opacity="0.3"/>
        </svg>
    </div>

    <div id="gdi-joker-tip" style="
        position:fixed; bottom:102px; right:28px; z-index:999998;
        background:#1F2937; color:#E0E7FF; padding:8px 14px; border-radius:10px;
        font-size:0.8rem; font-weight:600; font-family:'Outfit',sans-serif;
        box-shadow:0 4px 14px rgba(0,0,0,0.4); border:1px solid #374151;
        white-space:nowrap; opacity:0; transition:opacity 0.3s;
        pointer-events:none;
    ">🃏 Ask GDI Agent</div>

    <style>
    @keyframes gdi-jpulse {
        0%,100% { box-shadow:0 6px 28px rgba(124,58,237,0.5),0 0 0 4px rgba(124,58,237,0.12); }
        50%     { box-shadow:0 6px 32px rgba(124,58,237,0.65),0 0 0 8px rgba(124,58,237,0.08); }
    }
    #gdi-joker-float:hover {
        transform:scale(1.12) rotate(5deg);
        box-shadow:0 8px 36px rgba(124,58,237,0.65),0 0 0 6px rgba(124,58,237,0.2) !important;
    }
    #gdi-joker-float:hover ~ #gdi-joker-tip,
    #gdi-joker-float:hover + #gdi-joker-tip { opacity:1; }
    #gdi-joker-float:active { transform:scale(0.95); }
    </style>

    <script>
    // Wire the floating joker to click the hidden Streamlit button
    (function() {
        const joker = document.getElementById('gdi-joker-float');
        if (!joker) return;

        // Hide the original Streamlit button
        const allBtns = window.document.querySelectorAll('button');
        for (const btn of allBtns) {
            const txt = btn.innerText || btn.textContent || '';
            if (txt.includes('Ask GDI Agent') && txt.includes('🃏')) {
                const wrapper = btn.closest('div[data-testid="stButton"]')
                              || btn.closest('.stButton')
                              || btn.parentElement;
                if (wrapper) {
                    wrapper.style.cssText = 'height:0;overflow:hidden;opacity:0;position:absolute;pointer-events:none;';
                }
                // Click the hidden button when joker is clicked
                joker.onclick = function() { btn.click(); };
                break;
            }
        }
    })();
    </script>
    """, unsafe_allow_html=True)
