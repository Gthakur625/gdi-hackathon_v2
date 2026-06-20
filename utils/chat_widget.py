"""
JaGau AI — Floating chat widget.
Simple, reliable: pure CSS fixed button → st.dialog on click.
No JS hacks, no iframe injection, no hidden buttons.
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
        ws = [w for w in _words(name) if len(w) >= 4]
        if ws and any(w in q_lower for w in ws):
            return name
    return None


def _obs_card(obs, cause, rec, impact):
    """Formats a structured KAM-style response."""
    return (f"**📊 Observation:** {obs}\n\n"
            f"**🔍 Root Cause:** {cause}\n\n"
            f"**✅ Recommendation:** {rec}\n\n"
            f"**📈 Expected Impact:** {impact}")


def _product_table(df, top_n=8):
    """Return a markdown table of top products with key metrics."""
    if "product_name" not in df.columns:
        return ""
    pg = df.groupby("product_name").agg(
        orders   =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        ndr      =("ndr_status",      lambda x:(x=="Raised").sum()) if "ndr_status" in df.columns
                   else ("delivery_status","count"),
    ).reset_index()
    pg["del_pct"] = pg["delivered"]/pg["orders"].clip(lower=1)*100
    pg["rto_pct"] = pg["rto"]/pg["orders"].clip(lower=1)*100

    rows = []
    for _, r in pg.sort_values("orders", ascending=False).head(top_n).iterrows():
        flag = "🚨" if r["rto_pct"]>30 else ("⚠️" if r["rto_pct"]>20 else "✅")
        rows.append(f"| {r['product_name'][:28]} | {int(r['orders']):,} | "
                    f"{r['del_pct']:.0f}% | {r['rto_pct']:.0f}% {flag} |")

    if not rows:
        return ""
    return ("| Product | Orders | Delivery% | RTO% |\n"
            "|---------|--------|-----------|------|\n"
            + "\n".join(rows))


def _courier_table(cour_df, df, top_n=8):
    """Return courier allocation recommendation table."""
    if len(cour_df) == 0:
        return ""
    total = max(len(df), 1)
    best_dr = cour_df["delivery_rate"].max()
    rows = []
    for _, r in cour_df.sort_values("delivery_rate", ascending=False).head(top_n).iterrows():
        vol_pct = r["total"]/total*100
        gap     = best_dr - r["delivery_rate"]
        action  = "✅ Maintain" if gap < 3 else ("⬆️ Increase" if r["delivery_rate"] >= cour_df["delivery_rate"].mean() else "⬇️ Reduce")
        rows.append(f"| {r['courier']} | {int(r['total']):,} ({vol_pct:.0f}%) | "
                    f"{r['delivery_rate']:.0f}% | {r['rto_rate']:.0f}% | {action} |")
    if not rows:
        return ""
    return ("| Courier | Volume | Delivery% | RTO% | Action |\n"
            "|---------|--------|-----------|------|--------|\n"
            + "\n".join(rows))


def _pincode_table(df, top_n=10):
    """4-type pincode intelligence table."""
    if "pincode" not in df.columns:
        return {}
    pg = df.groupby("pincode").agg(
        orders  =("delivery_status","count"),
        del_    =("delivery_status", lambda x:(x=="Delivered").sum()),
        rto     =("delivery_status", lambda x:(x=="RTO").sum()),
        ndr     =("ndr_status",      lambda x:(x=="Raised").sum()) if "ndr_status" in df.columns
                  else ("delivery_status","count"),
        cod     =("payment_type",    lambda x:(x=="COD").sum()) if "payment_type" in df.columns
                  else ("delivery_status","count"),
        state   =("state","first") if "state" in df.columns else ("delivery_status","count"),
    ).reset_index()
    pg["dr"]   = pg["del_"]/pg["orders"].clip(lower=1)*100
    pg["rr"]   = pg["rto"]/pg["orders"].clip(lower=1)*100
    pg["ndrr"] = pg["ndr"]/pg["orders"].clip(lower=1)*100
    pg["codr"] = pg["cod"]/pg["orders"].clip(lower=1)*100

    best_courier = "top courier"
    cour_df = compute_courier_perf(df)
    if len(cour_df) > 0:
        best_courier = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["courier"]

    result = {}

    # 1. Opportunity pincodes (high volume, high delivery)
    opp = pg[(pg["orders"]>=3)&(pg["dr"]>=80)].nlargest(5,"orders")
    if len(opp) > 0:
        r = ["| Pincode | State | Orders | Delivery% |",
             "|---------|-------|--------|-----------|"]
        for _, row in opp.iterrows():
            r.append(f"| {row['pincode']} | {str(row.get('state',''))[:10]} | {int(row['orders'])} | {row['dr']:.0f}% |")
        result["opportunity"] = "\n".join(r)

    # 2. High NDR pincodes
    ndr_pins = pg[(pg["orders"]>=3)&(pg["ndrr"]>25)].nlargest(5,"ndrr")
    if len(ndr_pins) > 0:
        r = ["| Pincode | State | Orders | NDR% |",
             "|---------|-------|--------|------|"]
        for _, row in ndr_pins.iterrows():
            r.append(f"| {row['pincode']} | {str(row.get('state',''))[:10]} | {int(row['orders'])} | {row['ndrr']:.0f}% |")
        result["high_ndr"] = "\n".join(r)

    # 3. Risk pincodes (high RTO + COD)
    risk = pg[(pg["orders"]>=3)&(pg["rr"]>40)&(pg["codr"]>50)].nlargest(5,"rr")
    if len(risk) > 0:
        r = ["| Pincode | State | RTO% | COD% | Action |",
             "|---------|-------|------|------|--------|"]
        for _, row in risk.iterrows():
            r.append(f"| {row['pincode']} | {str(row.get('state',''))[:10]} | {row['rr']:.0f}% | {row['codr']:.0f}% | Restrict COD |")
        result["risk"] = "\n".join(r)

    # 4. Courier mismatch (high RTO, likely wrong courier)
    mismatch = pg[(pg["orders"]>=3)&(pg["rr"]>35)].nlargest(5,"rr")
    if len(mismatch) > 0:
        r = ["| Pincode | State | RTO% | Recommended Courier |",
             "|---------|-------|------|---------------------|"]
        for _, row in mismatch.iterrows():
            r.append(f"| {row['pincode']} | {str(row.get('state',''))[:10]} | {row['rr']:.0f}% | {best_courier} |")
        result["mismatch"] = "\n".join(r)

    return result


def _quick_reply(q, df, m, hs, cour_df, state_df, all_sellers):
    ql  = q.lower().strip()
    qw  = _words(ql)

    def has(*p): return any(x in ql for x in p)
    def hasw(*w): return any(x in qw for x in w)

    cod_df   = df[df["payment_type"]=="COD"] if "payment_type" in df.columns else pd.DataFrame()
    prep_df  = df[df["payment_type"]=="Prepaid"] if "payment_type" in df.columns else pd.DataFrame()
    cod_rto  = len(cod_df[cod_df["delivery_status"]=="RTO"])/max(len(cod_df),1)*100 if len(cod_df)>0 else 0
    best_c   = cour_df.sort_values("delivery_rate",ascending=False).iloc[0] if len(cour_df)>0 else None
    worst_c  = cour_df.sort_values("delivery_rate").iloc[0]                 if len(cour_df)>0 else None
    worst_st = state_df.sort_values("rto_rate",ascending=False).iloc[0]    if len(state_df)>0 else None

    sel  = _find(ql, all_sellers)
    cour = _find(ql, cour_df["courier"].tolist() if len(cour_df)>0 else [])

    # ── Seller specific ──────────────────────────────────────────────────────
    if sel:
        s_df = df[df["seller_name"]==sel]
        sm   = compute_kpis(s_df); sm["vas_adoption_score"]=compute_vas_adoption_score(s_df)
        sh   = compute_health_score(sm)
        risk = "Low Risk ✅" if sh>=80 else ("Medium Risk ⚠️" if sh>=65 else "High Risk 🚨")
        tbl  = _product_table(s_df, top_n=5)
        text = _obs_card(
            obs=f"**{sel}** has Health Score **{sh:.0f}/100** ({risk}). "
                f"Delivery: **{sm['delivery_pct']:.1f}%** | RTO: **{sm['rto_pct']:.1f}%** | "
                f"NDR: **{sm['ndr_count']:,}** | COD: **{sm['cod_pct']:.1f}%**",
            cause=(f"High COD share ({sm['cod_pct']:.0f}%) with low prepaid incentive" if sm['cod_pct']>65
                   else f"{'Courier performance gap' if sm['rto_pct']>20 else 'Operations within normal range'}"),
            rec=(f"Activate AI Calling for {sm['ndr_count']:,} NDRs + WhatsApp NDR for COD failures"
                 if sm['ndr_count']>5 else "Monitor delivery rate and restrict COD in high-RTO pincodes"),
            impact=f"~{int(sm['ndr_count']*0.38):,} NDRs recoverable via AI Calling"
        )
        if tbl:
            text += f"\n\n**Product Performance:**\n{tbl}"
        return text

    # ── All sellers ──────────────────────────────────────────────────────────
    if has("all seller","compare seller","seller list","seller performance") \
       or (hasw("seller","sellers","client","clients") and hasw("all","compare","list","rank")):
        sg = df.groupby("seller_name").agg(
            orders=("delivery_status","count"),
            delivered=("delivery_status",lambda x:(x=="Delivered").sum()),
            rto=("delivery_status",lambda x:(x=="RTO").sum()),
        ).reset_index()
        sg["dr"]=sg["delivered"]/sg["orders"]*100; sg["rr"]=sg["rto"]/sg["orders"]*100
        sg=sg.sort_values("dr",ascending=False)
        tbl = ("| Seller | Orders | Delivery% | RTO% | Status |\n"
               "|--------|--------|-----------|------|--------|\n")
        for _,r in sg.iterrows():
            flag = "✅" if r["dr"]>=80 else ("⚠️" if r["dr"]>=65 else "🚨")
            tbl += f"| {r['seller_name'][:25]} | {int(r['orders']):,} | {r['dr']:.0f}% | {r['rr']:.0f}% | {flag} |\n"
        best_s=sg.iloc[0]; worst_s=sg.iloc[-1]
        return _obs_card(
            obs=f"{len(sg)} sellers active. Best: **{best_s['seller_name']}** ({best_s['dr']:.0f}% del). "
                f"Needs attention: **{worst_s['seller_name']}** ({worst_s['dr']:.0f}% del, {worst_s['rr']:.0f}% RTO)\n\n{tbl}",
            cause=f"Delivery variance of {sg['dr'].std():.0f}% across sellers suggests inconsistent courier allocation or product mix",
            rec=f"Prioritise {worst_s['seller_name']} for AI Calling + Shipping Rule Optimization",
            impact=f"Closing the delivery gap to {best_s['dr']:.0f}% could add ~{int((best_s['dr']-worst_s['dr'])/100*worst_s['orders']):,} deliveries"
        )

    # ── Products ─────────────────────────────────────────────────────────────
    if has("product","top product","top selling","sku","best selling","worst product","product performance") \
       or hasw("products","sku","selling"):
        tbl = _product_table(df, top_n=8)
        if not tbl:
            return "No product data available in the current dataset."
        avg_rto = m["rto_pct"]
        pg = df.groupby("product_name").agg(total=("delivery_status","count"),rto=("delivery_status",lambda x:(x=="RTO").sum())).reset_index()
        pg["rr"]=pg["rto"]/pg["total"]*100
        top_vol = pg.sort_values("total",ascending=False).iloc[0] if len(pg)>0 else None
        worst_p = pg[pg["total"]>=3].sort_values("rr",ascending=False).iloc[0] if len(pg)>0 else None
        top_line  = f"Top volume: **{top_vol['product_name']}** ({int(top_vol['total']):,} orders)." if top_vol is not None else ""
        worst_line = f" Highest RTO: **{worst_p['product_name']}** ({worst_p['rr']:.0f}%)." if worst_p is not None else ""
        return _obs_card(
            obs=f"Analysed **{len(pg)} products** across {m['total']:,} shipments. {top_line}{worst_line}\n\n{tbl}",
            cause=(f"**{worst_p['product_name']}** RTO at {worst_p['rr']:.0f}% vs fleet avg {avg_rto:.0f}% — likely COD + address quality"
                   if worst_p is not None and worst_p['rr'] > avg_rto*1.3 else "Product mix within normal delivery range"),
            rec=(f"Restrict COD for **{worst_p['product_name']}** in high-RTO states. Activate Order Confirmation Via AI."
                 if worst_p is not None and worst_p['rr']>25 else "WhatsApp NDR for products with high NDR rate"),
            impact=f"Reducing worst product RTO by 10% = ~{int(worst_p['rto']*0.10):,} fewer returns" if worst_p is not None else "Monitor monthly"
        )

    # ── Couriers ──────────────────────────────────────────────────────────────
    if cour or has("courier","3pl","carrier","allocation","routing") or hasw("couriers","carriers"):
        tbl = _courier_table(cour_df, df)
        if cour:
            row = cour_df[cour_df["courier"]==cour].iloc[0] if len(cour_df[cour_df["courier"]==cour])>0 else None
            if row is not None:
                gap = (best_c["delivery_rate"] - row["delivery_rate"]) if best_c is not None else 0
                return _obs_card(
                    obs=f"**{cour}** handling {int(row['total']):,} shipments ({row['total']/max(len(df),1)*100:.0f}% of volume). "
                        f"Delivery: **{row['delivery_rate']:.0f}%** | RTO: **{row['rto_rate']:.0f}%**",
                    cause=(f"{gap:.0f}% below best courier {best_c['courier']}" if gap>5 and best_c else "Performance within expected range"),
                    rec=(f"Reduce {cour} allocation by 30–40% in underperforming states. Route to **{best_c['courier']}**."
                         if gap>5 and best_c else f"Maintain {cour} — performing well"),
                    impact=f"~{int(row['total']*(gap/100)):,} additional deliveries if volume shifted to {best_c['courier'] if best_c else 'top courier'}"
                )
        return _obs_card(
            obs=f"**{len(cour_df)} active couriers.** Best: {best_c['courier'] if best_c else 'N/A'} ({best_c['delivery_rate']:.0f}% del). "
                f"Weakest: {worst_c['courier'] if worst_c else 'N/A'} ({worst_c['delivery_rate']:.0f}% del).\n\n{tbl}",
            cause=f"Delivery spread of {cour_df['delivery_rate'].std():.0f}% across couriers — no pincode-level routing rules active",
            rec=f"Route high-COD pincodes to {best_c['courier'] if best_c else 'top courier'}. Activate Multi-Courier Allocation.",
            impact=f"~{int((cour_df['delivery_rate'].max()-cour_df['delivery_rate'].mean())/100 * len(df)):,} additional deliveries from rebalancing"
        )

    # ── Pincode intelligence ──────────────────────────────────────────────────
    if has("pincode","pincode intelligence","pin code","which pincode","problem pincode","ndr pincode","risk pincode","opportunity pincode"):
        tables = _pincode_table(df)
        parts  = []
        if tables.get("opportunity"):
            parts.append(f"**🏆 Top Opportunity Pincodes** (high volume + delivery):\n{tables['opportunity']}")
        if tables.get("high_ndr"):
            parts.append(f"**⚠️ High NDR Pincodes** (frequent failed attempts):\n{tables['high_ndr']}")
        if tables.get("risk"):
            parts.append(f"**🚨 Risk Pincodes** (high RTO + COD):\n{tables['risk']}")
        if tables.get("mismatch"):
            parts.append(f"**🔄 Courier Mismatch Pincodes** (switch courier):\n{tables['mismatch']}")
        if not parts:
            return "No pincode data available in the current dataset."
        body = "\n\n".join(parts)
        risk_pin_count = len(df.groupby("pincode").filter(lambda x: x["delivery_status"].eq("RTO").mean()>0.4)) if "pincode" in df.columns else 0
        return _obs_card(
            obs=f"Pincode analysis across {df['pincode'].nunique() if 'pincode' in df.columns else 0} pincodes:\n\n{body}",
            cause="COD accepted uniformly across all pincodes without historical RTO data gating",
            rec="Blacklist risk pincodes for COD. Route opportunity pincodes to best courier. Activate WhatsApp NDR for high-NDR pincodes.",
            impact=f"Blacklisting top risk pincodes for COD can prevent ~{int(m['rto_count']*0.15):,} RTOs/month"
        )

    # ── VAS Opportunity ───────────────────────────────────────────────────────
    if has("vas","calling opportunity","whatsapp opportunity","ndr opportunity","recoverable","recovery opportunity"):
        ndr_total = m["ndr_count"]
        cod_ndr   = len(df[(df["payment_type"]=="COD")&(df["ndr_status"]=="Raised")]) \
                    if "payment_type" in df.columns and "ndr_status" in df.columns else int(ndr_total*0.8)
        call_rec  = int(ndr_total*0.38)
        wa_rec    = int(cod_ndr*0.15)
        total_rec = call_rec + wa_rec
        call_cost = int(ndr_total * 8)   # ₹4/min × 2 min
        wa_cost   = int(cod_ndr * 1)     # ₹0.50 × 2 msgs
        return _obs_card(
            obs=(f"**NDR Volume:** {ndr_total:,} active NDRs ({m['ndr_pct']:.1f}% of shipments)\n"
                 f"- COD NDRs: **{cod_ndr:,}** — highest recovery priority\n"
                 f"- Fleet avg order value: ₹{m['avg_order_value']:,.0f}\n\n"
                 f"**AI Calling Opportunity:** {ndr_total:,} NDRs × 38% = **{call_rec:,} recoverable shipments** (cost: ₹{call_cost:,})\n"
                 f"**WhatsApp NDR Opportunity:** {cod_ndr:,} COD NDRs × 15% = **{wa_rec:,} recoverable** (cost: ₹{wa_cost:,})\n"
                 f"**Total Recoverable: {total_rec:,} shipments** across both channels"),
            cause=f"{ndr_total:,} shipments in limbo — no automated outreach active. Each day of delay increases RTO risk by ~5%",
            rec=f"Launch AI Calling for all {ndr_total:,} NDRs TODAY. Run WhatsApp NDR in parallel for {cod_ndr:,} COD cases.",
            impact=f"**{total_rec:,} shipments recoverable** · AI Calling cost ₹{call_cost:,} · WA cost ₹{wa_cost:,}"
        )

    # ── NDR ───────────────────────────────────────────────────────────────────
    if has("ndr","non delivery","undelivered","pending delivery") or hasw("ndr","undelivered"):
        rec = int(m["ndr_count"]*0.38)
        return _obs_card(
            obs=f"**{m['ndr_count']:,} active NDRs** ({m['ndr_pct']:.1f}% of shipments). "
                f"AI Calling can recover **{rec:,}** of these.",
            cause="No automated re-engagement active. NDRs aging past 48h convert to RTO at high rate.",
            rec=f"Activate AI Calling for all {m['ndr_count']:,} NDRs immediately. Use WhatsApp NDR for COD failures.",
            impact=f"{rec:,} shipments recovered · ₹{int(rec*8):,} call cost"
        )

    # ── RTO ───────────────────────────────────────────────────────────────────
    if has("rto","return","high rto","reduce rto") or (hasw("rto","return") and hasw("why","high","cause","fix")):
        ws_str = f"**{worst_st['state']}** ({worst_st['rto_rate']:.0f}% RTO)" if worst_st is not None else "multiple states"
        wc_str = f"**{worst_c['courier']}** ({worst_c['delivery_rate']:.0f}% delivery)" if worst_c is not None else "underperforming couriers"
        return _obs_card(
            obs=f"RTO at **{m['rto_pct']:.1f}%** ({m['rto_count']:,} shipments). "
                f"COD share: **{m['cod_pct']:.0f}%** with {cod_rto:.0f}% COD-RTO rate.",
            cause=f"Three drivers: (1) {ws_str} geographic cluster, "
                  f"(2) {wc_str} courier underperformance, "
                  f"(3) {m['cod_pct']:.0f}% COD with no pre-dispatch confirmation",
            rec="1. Order Confirmation Via AI (pre-dispatch filter)  2. Shipping Rule Optimization (state/pincode COD block)  3. Pincode Optimization (blacklist >50% RTO pins)",
            impact=f"~{int(m['rto_count']*0.20):,} RTOs preventable — Order Confirmation alone saves ~{int(m['rto_count']*0.12):,}/month"
        )

    # ── Health ────────────────────────────────────────────────────────────────
    if has("health","score","overall","summary","how am i") or hasw("health","score","overall"):
        risk = "Low Risk ✅" if hs>=80 else ("Medium Risk ⚠️" if hs>=65 else "High Risk 🚨")
        att  = m.get("attempted_total", m["total"])
        return _obs_card(
            obs=f"Health Score: **{hs:.0f}/100** — {risk}. "
                f"Delivery: **{m['delivery_pct']:.1f}%** ({m['delivered']:,} of {att:,} attempted) | "
                f"RTO: **{m['rto_pct']:.1f}%** | NDR: **{m['ndr_count']:,}** | COD: **{m['cod_pct']:.0f}%**",
            cause=("High RTO + High COD driving score down" if m["rto_pct"]>20 and m["cod_pct"]>65
                   else "NDR backlog reducing effective delivery rate" if m["ndr_pct"]>15
                   else "Courier concentration risk" if len(cour_df)<=1 else "Performance within range"),
            rec=("AI Calling + Order Confirmation Via AI to recover NDRs and block fake orders"
                 if m["ndr_pct"]>15 else "Focus on courier rebalancing and pincode optimization"),
            impact=f"Resolving NDRs and COD risk can improve Health Score by **+10–15 points**"
        )

    # ── COD ───────────────────────────────────────────────────────────────────
    if has("cod","prepaid","payment","cash on delivery") or hasw("cod","prepaid","payment"):
        prep_rto = len(prep_df[prep_df["delivery_status"]=="RTO"])/max(len(prep_df),1)*100 if len(prep_df)>0 else 0
        return _obs_card(
            obs=f"COD share: **{m['cod_pct']:.0f}%** ({m['cod_count']:,} orders). "
                f"COD-RTO: **{cod_rto:.0f}%** vs Prepaid-RTO: **{prep_rto:.0f}%** — gap of **+{cod_rto-prep_rto:.0f}%**",
            cause="COD buyers have lower delivery intent. No pre-dispatch confirmation or WhatsApp re-engagement active.",
            rec="Activate WhatsApp NDR for COD failures + Order Confirmation Via AI before dispatch. Offer prepaid discount.",
            impact=f"Reducing COD-RTO by 8% = ~{int(m['cod_count']*0.08):,} fewer returns/month"
        )

    # ── Default ───────────────────────────────────────────────────────────────
    att = m.get("attempted_total", m["total"])
    text = (f"**{m['total']:,} shipments** analysed · {len(all_sellers)} sellers · {len(cour_df)} couriers\n\n"
            f"Delivery: **{m['delivery_pct']:.1f}%** ({m['delivered']:,}/{att:,} attempted) · "
            f"RTO: **{m['rto_pct']:.1f}%** · NDR: **{m['ndr_count']:,}** · COD: **{m['cod_pct']:.0f}%**\n\n"
            f"**Ask me about:**\n"
            f"- *Sellers* — 'Compare all sellers' or 'Tell me about [seller name]'\n"
            f"- *Products* — 'Show product performance' or 'Which product has highest RTO?'\n"
            f"- *Couriers* — 'Show courier allocation' or 'Tell me about Delhivery'\n"
            f"- *Pincodes* — 'Pincode intelligence' or 'Show risk pincodes'\n"
            f"- *VAS* — 'VAS opportunity' or 'Simulate AI Calling'\n"
            f"- *RTO* — 'Why is RTO high?' or 'How to reduce RTO?'")
    return text


@st.dialog("🤖 JaGau AI — Your AI KAM & Operations Expert", width="large")
def chat_dialog(df):
    m        = compute_kpis(df)
    m["vas_adoption_score"] = compute_vas_adoption_score(df)
    hs       = compute_health_score(m)
    cour_df  = compute_courier_perf(df)
    state_df = compute_state_perf(df)
    all_sellers = sorted(df["seller_name"].unique().tolist()) if "seller_name" in df.columns else []

    rc = "#34D399" if hs>=80 else ("#FBBF24" if hs>=65 else "#F87171")
    att = m.get("attempted_total", m["total"])
    st.markdown(f"""
    <div style="display:flex;gap:18px;background:#111827;border-radius:10px;
                padding:12px 16px;margin-bottom:14px;flex-wrap:wrap;">
      <div><b style="color:{rc};">{hs:.0f}/100</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">Health</div></div>
      <div><b style="color:#34D399;">{m['delivery_pct']:.1f}%</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">Delivery</div></div>
      <div><b style="color:#F87171;">{m['rto_pct']:.1f}%</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">RTO</div></div>
      <div><b style="color:#FBBF24;">{m['ndr_count']:,}</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">NDR</div></div>
      <div><b style="color:#60A5FA;">{m['total']:,}</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">Shipments</div></div>
      <div><b style="color:#9CA3AF;font-size:0.72rem;">{m['delivered']:,}/{att:,} attempted</b>
           <div style="color:#6B7280;font-size:0.68rem;text-transform:uppercase;">Cohort</div></div>
    </div>""", unsafe_allow_html=True)

    quick = ["Product performance","Courier allocation","Pincode intelligence",
             "VAS opportunity","Compare sellers","Why is RTO high?","How to reduce NDR?"]
    qc = st.columns(4)
    sel_q = None
    for i, qq in enumerate(quick):
        if qc[i%4].button(qq, key=f"dq_{i}", use_container_width=True): sel_q = qq

    st.markdown("---")

    if "dialog_chat" not in st.session_state:
        st.session_state["dialog_chat"] = []

    for msg in st.session_state["dialog_chat"]:
        if msg["role"]=="user":
            st.markdown(f'<div class="chat-bubble-user">{msg["content"]}</div>', unsafe_allow_html=True)
        else:
            st.markdown(msg["content"])

    user_input = st.chat_input("Ask about products, couriers, pincodes, VAS, RTO…")
    if sel_q or user_input:
        prompt = sel_q or user_input
        st.session_state["dialog_chat"].append({"role":"user","content":prompt})
        answer = _quick_reply(prompt, df, m, hs, cour_df, state_df, all_sellers)
        st.session_state["dialog_chat"].append({"role":"assistant","content":answer})
        st.rerun()

    col1, col2 = st.columns([1, 3])
    with col1:
        if st.button("🗑 Clear", key="dlg_clear"): st.session_state["dialog_chat"]=[]; st.rerun()
    with col2:
        st.markdown(
            '<a href="/7_GDI_Consultant" target="_self" style="color:#818CF8;font-size:0.8rem;">'
            '→ Open full JaGau AI Consultant for deeper analysis</a>',
            unsafe_allow_html=True)


def render_chat_button(df):
    """Reliable floating JaGau AI button — pure CSS, no JS hacks."""
    # Inject the floating button CSS + HTML
    st.markdown("""
    <style>
    .jagau-float {
        position: fixed;
        bottom: 26px;
        right: 26px;
        z-index: 999999;
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 100%);
        color: #FFFFFF;
        border: 2px solid rgba(255,255,255,0.2);
        border-radius: 50px;
        padding: 12px 20px;
        font-size: 0.88rem;
        font-weight: 700;
        font-family: 'Outfit', system-ui, sans-serif;
        box-shadow: 0 4px 24px rgba(79,70,229,0.5);
        cursor: pointer;
        display: inline-flex;
        align-items: center;
        gap: 8px;
        text-decoration: none;
        transition: all 0.25s ease;
        animation: jagau-pulse 3s ease-in-out infinite;
    }
    .jagau-float:hover {
        transform: translateY(-3px) scale(1.04);
        box-shadow: 0 8px 32px rgba(79,70,229,0.65);
        color: #FFFFFF;
    }
    @keyframes jagau-pulse {
        0%, 100% { box-shadow: 0 4px 24px rgba(79,70,229,0.5); }
        50%       { box-shadow: 0 4px 32px rgba(79,70,229,0.7); }
    }
    </style>
    """, unsafe_allow_html=True)

    # Use Streamlit button — reliable click → dialog
    # Place at bottom of page, styled to blend with fixed position
    col = st.columns([6, 1])[1]
    with col:
        if st.button("🤖 JaGau", use_container_width=True,
                     key="jagau_float_btn", type="primary"):
            chat_dialog(df)
