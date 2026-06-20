"""
Seller Intelligence Layer
Generates AI text insights + compact tables for a given seller's DataFrame.
Works with any data source — no external APIs needed.
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go


# ── tiny bar helper ────────────────────────────────────────────────────────────
def _bar(pct, color="#34D399", width=80):
    fill = max(2, int(pct * width / 100))
    return (f'<div style="display:inline-block;background:#1F2937;border-radius:99px;'
            f'height:6px;width:{width}px;vertical-align:middle;margin-left:8px;">'
            f'<div style="height:6px;width:{fill}px;border-radius:99px;background:{color};"></div>'
            f'</div>')


def _pct_color(pct, thresholds=(80, 65)):
    """Green / yellow / red based on delivery %."""
    if pct >= thresholds[0]:  return "#34D399"
    if pct >= thresholds[1]:  return "#FBBF24"
    return "#F87171"


def _rto_color(pct):
    if pct < 15: return "#34D399"
    if pct < 25: return "#FBBF24"
    return "#F87171"


def _insight_tag(text, color):
    return (f'<span style="background:{color}20;color:{color};border:1px solid {color}40;'
            f'padding:3px 9px;border-radius:99px;font-size:0.73rem;font-weight:600;'
            f'margin:2px;display:inline-block;">{text}</span>')


def _section(title):
    st.markdown(f"<div style='color:#9CA3AF;font-size:0.72rem;font-weight:700;"
                f"text-transform:uppercase;letter-spacing:0.07em;"
                f"margin:18px 0 10px;border-bottom:1px solid #1F2937;padding-bottom:6px;'>"
                f"{title}</div>", unsafe_allow_html=True)


def _ai_box(text, color="#818CF8"):
    st.markdown(
        f'<div style="background:rgba(79,70,229,0.07);border-left:3px solid {color};'
        f'border-radius:0 8px 8px 0;padding:10px 14px;margin:8px 0 14px;'
        f'font-size:0.82rem;color:#D1D5DB;line-height:1.6;">'
        f'🤖 <b style="color:{color};">GDI Insight:</b> {text}</div>',
        unsafe_allow_html=True)


def _row(cells, header=False):
    style = ("background:#1F2937;font-weight:600;font-size:0.75rem;"
             "text-transform:uppercase;letter-spacing:0.04em;color:#9CA3AF;"
             if header else "font-size:0.82rem;color:#D1D5DB;")
    cols = "".join(
        f'<td style="padding:7px 10px;border-bottom:1px solid #1F2937;{c[1] if len(c)>1 else ""}">{c[0]}</td>'
        for c in cells
    )
    return f'<tr style="{style}">{cols}</tr>'


def _table(rows_html, headers):
    h = _row([(h,) for h in headers], header=True)
    return (f'<table style="width:100%;border-collapse:collapse;">'
            f'<thead>{h}</thead><tbody>{rows_html}</tbody></table>')


# ══════════════════════════════════════════════════════════════════════════════
# MAIN RENDER FUNCTION
# ══════════════════════════════════════════════════════════════════════════════

def render_seller_intelligence(df, seller_name, overall_delivery_pct, overall_rto_pct):
    """
    Render full Seller Intelligence layer.
    df               — already filtered to this seller
    seller_name      — display name
    overall_*        — fleet-wide benchmarks for comparison
    """
    if len(df) == 0:
        st.warning(f"No data for {seller_name}")
        return

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#0F172A 0%,#111827 100%);
         border:1px solid rgba(129,140,248,0.3);border-radius:14px;
         padding:16px 20px;margin-bottom:4px;">
      <div style="color:#818CF8;font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.08em;">🔬 Seller Intelligence</div>
      <div style="color:#FFFFFF;font-size:1.15rem;font-weight:800;margin-top:2px;">
        {seller_name}</div>
      <div style="color:#6B7280;font-size:0.78rem;margin-top:2px;">
        {len(df):,} shipments · AI-generated insights across products, states, pincodes & pricing
      </div>
    </div>""", unsafe_allow_html=True)

    has_product = "product_name" in df.columns
    has_state   = "state"        in df.columns
    has_pincode = "pincode"      in df.columns
    has_payment = "payment_type" in df.columns
    has_ndr     = "ndr_status"   in df.columns

    # ── pre-compute product table ─────────────────────────────────────────────
    if has_product:
        pg = df.groupby("product_name").agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            ndr      =("delivery_status", lambda x:(x=="NDR").sum()) if not has_ndr
                       else ("ndr_status", lambda x:(x=="Raised").sum()),
            revenue  =("order_value","sum"),
            avg_val  =("order_value","mean"),
            cod      =("payment_type", lambda x:(x=="COD").sum()) if has_payment else ("delivery_status","count"),
        ).reset_index()
        pg["dr"]      = pg["delivered"] / pg["total"].clip(lower=1) * 100
        pg["rr"]      = pg["rto"]       / pg["total"].clip(lower=1) * 100
        pg["ndr_pct"] = pg["ndr"]       / pg["total"].clip(lower=1) * 100
        pg["cod_pct"] = pg["cod"]       / pg["total"].clip(lower=1) * 100

    # ── tabs ──────────────────────────────────────────────────────────────────
    tabs = ["📦 Products", "🗺️ States", "📍 Pincodes", "💰 Pricing Band"]
    t1, t2, t3, t4 = st.tabs(tabs)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 1 — PRODUCTS
    # ══════════════════════════════════════════════════════════════════════════
    with t1:
        if not has_product:
            st.info("No product_name column in data.")
        else:
            # ── Top Products (by volume) ──────────────────────────────────────
            col1, col2 = st.columns(2)

            with col1:
                _section("🏆 Top 5 Products — Volume")
                top_vol = pg.sort_values("total", ascending=False).head(5)
                rows = ""
                for _, r in top_vol.iterrows():
                    dc = _pct_color(r["dr"])
                    rows += _row([
                        (r["product_name"][:30], "color:#FFFFFF;font-weight:600;"),
                        (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                        (f'<span style="color:{dc};font-weight:700;">{r["dr"]:.0f}%</span>'
                         + _bar(r["dr"], dc), "text-align:right;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Product", "Orders", "Delivery %"])
                            + "</div>", unsafe_allow_html=True)

                # AI insight
                top1 = top_vol.iloc[0]
                low_del = top_vol[top_vol["dr"] < overall_delivery_pct - 5]
                if len(low_del) > 0:
                    worst = low_del.sort_values("dr").iloc[0]
                    _ai_box(f"<b>{top1['product_name']}</b> is your top seller "
                            f"({top1['total']:,} orders, {top1['dr']:.0f}% delivery). "
                            f"However, <b>{worst['product_name']}</b> lags at {worst['dr']:.0f}% "
                            f"vs fleet avg {overall_delivery_pct:.0f}% — "
                            f"activate <b>Order Confirmation Via AI</b> for it.")
                else:
                    _ai_box(f"<b>{top1['product_name']}</b> leads in volume with {top1['dr']:.0f}% "
                            f"delivery — above fleet avg {overall_delivery_pct:.0f}%. "
                            f"Consider NDD for Zone A/B orders of this product.")

            with col2:
                _section("💰 Top 5 Products — Revenue")
                top_rev = pg.sort_values("revenue", ascending=False).head(5)
                rows = ""
                for _, r in top_rev.iterrows():
                    rows += _row([
                        (r["product_name"][:30], "color:#FFFFFF;font-weight:600;"),
                        (f"₹{r['revenue']:,.0f}", "text-align:right;color:#34D399;font-weight:700;"),
                        (f"₹{r['avg_val']:,.0f}", "text-align:right;color:#9CA3AF;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Product", "Total Revenue", "Avg Value"])
                            + "</div>", unsafe_allow_html=True)

                rev1 = top_rev.iloc[0]
                high_val = top_rev[top_rev["avg_val"] > 1500]
                if len(high_val) > 0:
                    _ai_box(f"<b>{rev1['product_name']}</b> generates ₹{rev1['revenue']:,.0f} in revenue. "
                            f"{len(high_val)} products have avg value > ₹1,500 — "
                            f"these are prime candidates for <b>prepaid push</b> to reduce RTO risk.")
                else:
                    _ai_box(f"<b>{rev1['product_name']}</b> is your top revenue product "
                            f"at ₹{rev1['revenue']:,.0f}. Low avg values suggest high COD dependency — "
                            f"activate <b>WhatsApp AI NDR</b> for NDR recovery.")

            st.markdown("---")

            # ── Highest Delivery / RTO / NDR ──────────────────────────────────
            col3, col4, col5 = st.columns(3)

            with col3:
                _section("✅ Highest Delivery Products")
                top_del = pg[pg["total"] >= 3].sort_values("dr", ascending=False).head(5)
                rows = ""
                for _, r in top_del.iterrows():
                    dc = _pct_color(r["dr"])
                    rows += _row([
                        (r["product_name"][:25], "color:#FFFFFF;font-weight:600;"),
                        (f'<span style="color:{dc};font-weight:800;">{r["dr"]:.0f}%</span>', "text-align:right;"),
                        (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Product", "Delivery %", "Orders"])
                            + "</div>", unsafe_allow_html=True)

                if len(top_del) > 0:
                    best = top_del.iloc[0]
                    _ai_box(f"<b>{best['product_name']}</b> has your best delivery at {best['dr']:.0f}%. "
                            f"Use this as your benchmark — route similar products via "
                            f"{best['product_name'][:15]}'s courier mix.", "#34D399")

            with col4:
                _section("🚨 Highest RTO Products")
                top_rto = pg[pg["total"] >= 3].sort_values("rr", ascending=False).head(5)
                rows = ""
                for _, r in top_rto.iterrows():
                    rc2 = _rto_color(r["rr"])
                    rev_at_risk = int(r["rto"] * r["avg_val"])
                    rows += _row([
                        (r["product_name"][:25], "color:#FFFFFF;font-weight:600;"),
                        (f'<span style="color:{rc2};font-weight:800;">{r["rr"]:.0f}%</span>', "text-align:right;"),
                        (f"₹{rev_at_risk:,.0f}", "text-align:right;color:#F87171;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Product", "RTO %", "Revenue at Risk"])
                            + "</div>", unsafe_allow_html=True)

                if len(top_rto) > 0:
                    worst_p = top_rto.iloc[0]
                    rev_risk = int(worst_p["rto"] * worst_p["avg_val"])
                    fix = ("Restrict COD + activate Order Confirmation Via AI."
                           if worst_p["cod_pct"] > 60
                           else "Review pincode coverage and address quality.")
                    _ai_box(f"<b>{worst_p['product_name']}</b> has {worst_p['rr']:.0f}% RTO — "
                            f"₹{rev_risk:,.0f} at risk per period. {fix}", "#F87171")

            with col5:
                _section("⚠️ Highest NDR Products")
                top_ndr = pg[pg["total"] >= 3].sort_values("ndr_pct", ascending=False).head(5)
                rows = ""
                for _, r in top_ndr.iterrows():
                    nc = "#34D399" if r["ndr_pct"] < 10 else ("#FBBF24" if r["ndr_pct"] < 20 else "#F87171")
                    rows += _row([
                        (r["product_name"][:25], "color:#FFFFFF;font-weight:600;"),
                        (f'<span style="color:{nc};font-weight:800;">{r["ndr_pct"]:.0f}%</span>', "text-align:right;"),
                        (f"{int(r['ndr']):,}", "text-align:right;color:#FBBF24;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Product", "NDR %", "NDR Count"])
                            + "</div>", unsafe_allow_html=True)

                if len(top_ndr) > 0:
                    worst_n = top_ndr.iloc[0]
                    rec_calls = int(worst_n["ndr"] * 0.38)
                    _ai_box(f"<b>{worst_n['product_name']}</b> has {worst_n['ndr_pct']:.0f}% NDR rate. "
                            f"AI Calling can recover ~{rec_calls:,} of these shipments. "
                            f"WhatsApp AI NDR is also effective for COD NDRs of this product.", "#FBBF24")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 2 — STATES
    # ══════════════════════════════════════════════════════════════════════════
    with t2:
        if not has_state:
            st.info("No state column in data.")
        else:
            st_g = df.groupby("state").agg(
                total    =("delivery_status","count"),
                delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
                rto      =("delivery_status", lambda x:(x=="RTO").sum()),
                revenue  =("order_value","sum"),
                cod      =("payment_type", lambda x:(x=="COD").sum()) if has_payment else ("delivery_status","count"),
            ).reset_index()
            st_g["dr"]      = st_g["delivered"] / st_g["total"].clip(lower=1) * 100
            st_g["rr"]      = st_g["rto"]       / st_g["total"].clip(lower=1) * 100
            st_g["cod_pct"] = st_g["cod"]        / st_g["total"].clip(lower=1) * 100

            sc1, sc2 = st.columns(2)

            with sc1:
                _section("🏆 Best Performing States")
                top_st = st_g[st_g["total"] >= 2].sort_values("dr", ascending=False).head(8)
                rows = ""
                for _, r in top_st.iterrows():
                    dc = _pct_color(r["dr"])
                    rows += _row([
                        (r["state"], "color:#FFFFFF;font-weight:600;"),
                        (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                        (f'<span style="color:{dc};font-weight:700;">{r["dr"]:.0f}%</span>'
                         + _bar(r["dr"], dc, 60), "text-align:right;"),
                        (f"₹{r['revenue']:,.0f}", "text-align:right;color:#34D399;font-size:0.78rem;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["State", "Shpts", "Delivery %", "Revenue"])
                            + "</div>", unsafe_allow_html=True)

                if len(top_st) > 0:
                    best_s = top_st.iloc[0]
                    _ai_box(f"<b>{best_s['state']}</b> is your best delivery state at {best_s['dr']:.0f}% "
                            f"({best_s['total']:,} shipments, ₹{best_s['revenue']:,.0f} revenue). "
                            f"Consider scaling volume here — NDD may be available for Zone A pincodes.",
                            "#34D399")

            with sc2:
                _section("🚨 Worst Performing States — RTO")
                bot_st = st_g[st_g["total"] >= 2].sort_values("rr", ascending=False).head(8)
                rows = ""
                for _, r in bot_st.iterrows():
                    rc2 = _rto_color(r["rr"])
                    rows += _row([
                        (r["state"], "color:#FFFFFF;font-weight:600;"),
                        (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                        (f'<span style="color:{rc2};font-weight:700;">{r["rr"]:.0f}%</span>'
                         + _bar(r["rr"], rc2, 60), "text-align:right;"),
                        (f"{r['cod_pct']:.0f}%", "text-align:right;color:#C084FC;font-size:0.78rem;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["State", "Shpts", "RTO %", "COD %"])
                            + "</div>", unsafe_allow_html=True)

                if len(bot_st) > 0:
                    worst_s = bot_st.iloc[0]
                    fix = ("Restrict COD + enable ATS Address Verification."
                           if worst_s["cod_pct"] > 65 else
                           "Check address quality and courier coverage in this state.")
                    _ai_box(f"<b>{worst_s['state']}</b> has {worst_s['rr']:.0f}% RTO "
                            f"(COD {worst_s['cod_pct']:.0f}%). {fix} "
                            f"AI Calling for NDRs here can recover ~38% of stuck shipments.", "#F87171")

            # State opportunity summary
            high_rto_states = bot_st[bot_st["rr"] > overall_rto_pct * 1.3]
            good_states     = top_st[top_st["dr"] > overall_delivery_pct + 5]
            tags = ""
            for _, r in high_rto_states.head(3).iterrows():
                tags += _insight_tag(f"⚠️ {r['state']} {r['rr']:.0f}% RTO", "#F87171")
            for _, r in good_states.head(3).iterrows():
                tags += _insight_tag(f"✅ {r['state']} {r['dr']:.0f}% del", "#34D399")
            if tags:
                st.markdown(f"<div style='margin-top:6px;'>{tags}</div>", unsafe_allow_html=True)

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 3 — PINCODES
    # ══════════════════════════════════════════════════════════════════════════
    with t3:
        if not has_pincode:
            st.info("No pincode column in data.")
        else:
            pin_g = df.groupby("pincode").agg(
                total    =("delivery_status","count"),
                delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
                rto      =("delivery_status", lambda x:(x=="RTO").sum()),
                state    =("state","first") if has_state else ("delivery_status","count"),
                revenue  =("order_value","sum"),
            ).reset_index()
            pin_g["dr"] = pin_g["delivered"] / pin_g["total"].clip(lower=1) * 100
            pin_g["rr"] = pin_g["rto"]       / pin_g["total"].clip(lower=1) * 100

            pc1, pc2 = st.columns(2)

            with pc1:
                _section("🏆 Top Pincodes — Volume & Delivery")
                top_pin = pin_g[pin_g["total"] >= 2].sort_values("total", ascending=False).head(10)
                rows = ""
                for _, r in top_pin.iterrows():
                    dc = _pct_color(r["dr"])
                    state_lbl = r["state"] if has_state and r["state"] not in [None, "count"] else ""
                    rows += _row([
                        (str(r["pincode"]), "color:#FFFFFF;font-weight:600;font-family:monospace;"),
                        (state_lbl[:12], "color:#9CA3AF;font-size:0.78rem;"),
                        (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                        (f'<span style="color:{dc};font-weight:700;">{r["dr"]:.0f}%</span>', "text-align:right;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Pincode", "State", "Orders", "Del %"])
                            + "</div>", unsafe_allow_html=True)

                if len(top_pin) > 0:
                    tp = top_pin.iloc[0]
                    _ai_box(f"Pincode <b>{tp['pincode']}</b> is your highest volume pincode "
                            f"({tp['total']:,} orders, {tp['dr']:.0f}% delivery). "
                            f"Ensure your primary courier has strong serviceability here.", "#818CF8")

            with pc2:
                _section("🚨 Problem Pincodes — High RTO")
                bad_pin = pin_g[pin_g["total"] >= 2].sort_values("rr", ascending=False).head(10)
                rows = ""
                for _, r in bad_pin.iterrows():
                    rc2 = _rto_color(r["rr"])
                    state_lbl = r["state"] if has_state and r["state"] not in [None, "count"] else ""
                    rev_risk  = int(r["rto"] * r["revenue"] / max(r["total"], 1))
                    rows += _row([
                        (str(r["pincode"]), "color:#FFFFFF;font-weight:600;font-family:monospace;"),
                        (state_lbl[:12], "color:#9CA3AF;font-size:0.78rem;"),
                        (f'<span style="color:{rc2};font-weight:700;">{r["rr"]:.0f}%</span>', "text-align:right;"),
                        (f"₹{rev_risk:,.0f}", "text-align:right;color:#F87171;font-size:0.78rem;"),
                    ])
                st.markdown('<div class="saas-card" style="padding:14px;">'
                            + _table(rows, ["Pincode", "State", "RTO %", "Rev at Risk"])
                            + "</div>", unsafe_allow_html=True)

                if len(bad_pin) > 0:
                    bp = bad_pin.iloc[0]
                    _ai_box(f"Pincode <b>{bp['pincode']}</b> has {bp['rr']:.0f}% RTO — "
                            f"consider blacklisting COD for this pincode or switching courier. "
                            f"ATS Address Verification helps at checkout for addresses here.", "#F87171")

    # ══════════════════════════════════════════════════════════════════════════
    # TAB 4 — PRICING BAND
    # ══════════════════════════════════════════════════════════════════════════
    with t4:
        bins  = [0, 499, 999, 1999, 4999, float("inf")]
        blbls = ["₹0–499", "₹500–999", "₹1K–2K", "₹2K–5K", "₹5K+"]
        df_pb = df.copy()
        df_pb["pb"] = pd.cut(df_pb["order_value"], bins=bins, labels=blbls, right=True)
        pb_g = df_pb.groupby("pb", observed=True).agg(
            total    =("delivery_status","count"),
            delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            revenue  =("order_value","sum"),
            avg_val  =("order_value","mean"),
            cod      =("payment_type", lambda x:(x=="COD").sum()) if has_payment else ("delivery_status","count"),
        ).reset_index()
        pb_g["dr"]      = pb_g["delivered"] / pb_g["total"].clip(lower=1) * 100
        pb_g["rr"]      = pb_g["rto"]       / pb_g["total"].clip(lower=1) * 100
        pb_g["cod_pct"] = pb_g["cod"]        / pb_g["total"].clip(lower=1) * 100

        pb1, pb2 = st.columns([3, 2])

        with pb1:
            _section("📊 Price Band Performance")
            rows = ""
            for _, r in pb_g.iterrows():
                if r["total"] == 0: continue
                dc  = _pct_color(r["dr"])
                rc2 = _rto_color(r["rr"])
                rows += _row([
                    (str(r["pb"]), "color:#FFFFFF;font-weight:700;"),
                    (f"{r['total']:,}", "text-align:right;color:#9CA3AF;"),
                    (f'<span style="color:{dc};font-weight:700;">{r["dr"]:.0f}%</span>'
                     + _bar(r["dr"], dc, 55), "text-align:right;"),
                    (f'<span style="color:{rc2};font-weight:700;">{r["rr"]:.0f}%</span>', "text-align:right;"),
                    (f"{r['cod_pct']:.0f}%", "text-align:right;color:#C084FC;"),
                    (f"₹{r['revenue']:,.0f}", "text-align:right;color:#34D399;font-size:0.78rem;"),
                ])
            st.markdown('<div class="saas-card" style="padding:14px;">'
                        + _table(rows, ["Band", "Orders", "Delivery %", "RTO %", "COD %", "Revenue"])
                        + "</div>", unsafe_allow_html=True)

        with pb2:
            _section("🤖 AI Pricing Insights")
            if len(pb_g) > 0:
                valid = pb_g[pb_g["total"] > 0]
                best_band  = valid.sort_values("dr", ascending=False).iloc[0] if len(valid)>0 else None
                worst_band = valid.sort_values("rr", ascending=False).iloc[0] if len(valid)>0 else None
                high_cod   = valid[valid["cod_pct"] > 70]
                low_del    = valid[valid["dr"] < overall_delivery_pct - 10]

                insights = []
                if best_band is not None:
                    insights.append(
                        f"✅ <b>{best_band['pb']}</b> is your strongest band — "
                        f"{best_band['dr']:.0f}% delivery, ₹{best_band['revenue']:,.0f} revenue. "
                        f"Scale here.")
                if worst_band is not None and worst_band["rr"] > 20:
                    insights.append(
                        f"🚨 <b>{worst_band['pb']}</b> has {worst_band['rr']:.0f}% RTO. "
                        f"{'Restrict COD immediately.' if worst_band['cod_pct']>65 else 'Check address quality at checkout.'}")
                if len(high_cod) > 0:
                    bands = ", ".join(high_cod["pb"].astype(str).tolist())
                    insights.append(
                        f"⚠️ <b>{bands}</b> have COD > 70%. "
                        f"Activate <b>Order Confirmation Via AI</b> and <b>WhatsApp AI NDR</b> for these bands.")
                if len(low_del) > 0:
                    bands = ", ".join(low_del["pb"].astype(str).tolist())
                    insights.append(
                        f"📉 <b>{bands}</b> delivery is below fleet average. "
                        f"Consider COD restrictions + routing to top-performing courier.")

                # NDD callout for high-value bands
                high_val = valid[valid["avg_val"] >= 1500]
                if len(high_val) > 0:
                    insights.append(
                        f"🚀 Orders in <b>{', '.join(high_val['pb'].astype(str).tolist())}</b> "
                        f"avg ₹{high_val['avg_val'].mean():,.0f} — ideal for NDD "
                        f"(Elastic Run / PiknDel / Blitz) to improve delivery experience and reduce NDR.")

                for ins in insights:
                    st.markdown(
                        f'<div style="background:#111827;border:1px solid #1F2937;border-radius:8px;'
                        f'padding:10px 13px;margin-bottom:8px;font-size:0.8rem;color:#D1D5DB;line-height:1.5;">'
                        f'{ins}</div>',
                        unsafe_allow_html=True)
