"""
GDI Agentic Operations Consultant
Detects critical issues from live data and surfaces actionable escalations.
All actions are simulation only — no real integrations.
"""
import streamlit as st
import pandas as pd
import numpy as np
import random
import string
from datetime import datetime, timedelta

# ── ticket ID generator ────────────────────────────────────────────────────────
def _ticket_id():
    return "GDI-" + "".join(random.choices(string.digits, k=5))

def _now_str():
    return datetime.now().strftime("%d %b %Y, %I:%M %p")

def _due_str(hours=4):
    return (datetime.now() + timedelta(hours=hours)).strftime("%d %b, %I:%M %p")

# ── severity style ─────────────────────────────────────────────────────────────
SEVERITY = {
    "CRITICAL": {"bg": "#EF4444", "border": "#EF4444", "icon": "🔴", "label": "CRITICAL"},
    "HIGH":     {"bg": "#F59E0B", "border": "#F59E0B", "icon": "🟠", "label": "HIGH"},
    "MEDIUM":   {"bg": "#818CF8", "border": "#818CF8", "icon": "🟡", "label": "MEDIUM"},
}

# ── detect issues from df ──────────────────────────────────────────────────────
def detect_critical_issues(df, m, cour_df, state_df):
    """
    Scan df and return list of issue dicts, each with:
      id, severity, title, what, why, impact, affected_count, affected_items
    """
    issues = []
    total  = max(len(df), 1)

    # ── 1. Multi-attempt NDR escalation ──────────────────────────────────────
    if "attempt_count" in df.columns and "ndr_status" in df.columns:
        stuck = df[(df["ndr_status"] == "Raised") & (df["attempt_count"] >= 3)]
        if len(stuck) > 0:
            top_sellers = stuck.groupby("seller_name").size().sort_values(ascending=False).head(3) \
                         if "seller_name" in stuck.columns else pd.Series()
            seller_str  = ", ".join(top_sellers.index.tolist()) if len(top_sellers) > 0 else "multiple sellers"
            issues.append({
                "id":        _ticket_id(),
                "severity":  "CRITICAL",
                "title":     f"⚠ {len(stuck):,} Shipments Stuck — 3+ Failed Delivery Attempts",
                "what":      (f"{len(stuck):,} active NDRs have had <b>3 or more failed delivery attempts</b>. "
                              f"These are at highest risk of becoming permanent RTOs within 24–48 hours."),
                "why":       (f"Courier cannot complete delivery — customer unavailable, address issues, or refusal. "
                              f"Without immediate outreach, these shipments will be returned."),
                "impact":    (f"If unresolved: <b>{len(stuck):,} RTOs</b> likely. "
                              f"Avg order ₹{m['avg_order_value']:,.0f} — "
                              f"est. <b>{len(stuck):,} shipments at risk</b>. "
                              f"Sellers affected: {seller_str}."),
                "affected_count": len(stuck),
                "affected_items": stuck.head(5)[
                    [c for c in ["awb","seller_name","state","attempt_count","ndr_reason","order_value"]
                     if c in stuck.columns]
                ].to_dict("records"),
                "action_context": {
                    "ops_msg":  f"{len(stuck)} shipments with 3+ failed attempts — immediate calling campaign required",
                    "wa_msg":   f"🚨 URGENT: {len(stuck)} NDRs at 3+ attempts. AI Calling campaign needed NOW. Sellers: {seller_str}",
                    "task_due": _due_str(2),
                    "task":     f"Resolve {len(stuck)} stuck NDRs (3+ attempts) before EOD",
                },
            })

    # ── 2. High-RTO seller alert ──────────────────────────────────────────────
    if "seller_name" in df.columns:
        sg = df.groupby("seller_name").agg(
            total    =("delivery_status","count"),
            rto      =("delivery_status", lambda x:(x=="RTO").sum()),
            ndr      =("ndr_status", lambda x:(x=="Raised").sum()) if "ndr_status" in df.columns
                       else ("delivery_status","count"),
        ).reset_index()
        sg["rr"] = sg["rto"] / sg["total"].clip(lower=1) * 100
        bad = sg[(sg["rr"] > 40) & (sg["total"] >= 5)].sort_values("rr", ascending=False)
        if len(bad) > 0:
            worst = bad.iloc[0]
            others = f" and {len(bad)-1} more sellers" if len(bad) > 1 else ""
            issues.append({
                "id":        _ticket_id(),
                "severity":  "CRITICAL" if worst["rr"] > 55 else "HIGH",
                "title":     f"⚠ {worst['seller_name'][:40]} — {worst['rr']:.0f}% RTO Rate{others}",
                "what":      (f"<b>{worst['seller_name']}</b> has <b>{worst['rr']:.0f}% RTO</b> "
                              f"({int(worst['rto'])} RTOs out of {int(worst['total'])} shipments). "
                              f"{len(bad)} seller(s) above 40% RTO threshold."),
                "why":       ("High COD concentration, address quality issues, or product-specific "
                              "refusal pattern. This seller needs VAS activation and RTO audit."),
                "impact":    (f"<b>{int(worst['rto'])} shipments returned</b> for {worst['seller_name']}. "
                              f"Seller retention risk if RTO rate not addressed within this week. "
                              f"Activate Order Confirmation Via AI immediately."),
                "affected_count": int(bad["total"].sum()),
                "affected_items": bad[["seller_name","total","rto","rr"]].head(5).to_dict("records"),
                "action_context": {
                    "ops_msg":  f"Seller {worst['seller_name']} RTO at {worst['rr']:.0f}% — needs RTO review call",
                    "wa_msg":   f"📊 Seller Alert: {worst['seller_name']} RTO = {worst['rr']:.0f}%. Schedule review.",
                    "task_due": _due_str(24),
                    "task":     f"RTO audit for {worst['seller_name']} — review product, pincode, COD mix",
                },
            })

    # ── 3. COD NDR concentration ──────────────────────────────────────────────
    cod_ndr_df = pd.DataFrame()
    if "payment_type" in df.columns and "ndr_status" in df.columns:
        cod_ndr_df = df[(df["payment_type"] == "COD") & (df["ndr_status"] == "Raised")]
    if len(cod_ndr_df) > 20:
        cod_pct = len(cod_ndr_df) / max(m.get("ndr_count", 1), 1) * 100
        top_st  = cod_ndr_df.groupby("state").size().sort_values(ascending=False).head(3).index.tolist() \
                 if "state" in cod_ndr_df.columns else []
        issues.append({
            "id":        _ticket_id(),
            "severity":  "HIGH" if cod_pct > 70 else "MEDIUM",
            "title":     f"⚠ {len(cod_ndr_df):,} COD NDRs Unresolved — WhatsApp Campaign Ready",
            "what":      (f"<b>{len(cod_ndr_df):,} COD shipments</b> are in NDR — "
                          f"{cod_pct:.0f}% of total NDR queue. "
                          f"WhatsApp AI NDR can reach these buyers immediately."),
            "why":       ("COD buyers are less committed to delivery. NDR without prompt re-engagement "
                          "converts to RTO within 48–72 hours. WhatsApp has 3× faster response than calls for COD."),
            "impact":    (f"At 15% WhatsApp recovery: <b>{int(len(cod_ndr_df)*0.15):,} shipments saved</b>. "
                          f"Cost: ₹{len(cod_ndr_df)*1:,} (₹0.50 × 2 messages). "
                          f"Top states: {', '.join(top_st) if top_st else 'multiple'}."),
            "affected_count": len(cod_ndr_df),
            "affected_items": cod_ndr_df.head(5)[
                [c for c in ["awb","seller_name","state","order_value","ndr_reason"]
                 if c in cod_ndr_df.columns]
            ].to_dict("records"),
            "action_context": {
                "ops_msg":  f"{len(cod_ndr_df)} COD NDRs ready for WhatsApp campaign — approve and launch",
                "wa_msg":   f"📦 {len(cod_ndr_df)} COD NDRs pending. WA campaign can recover ~{int(len(cod_ndr_df)*0.15)}. Cost ₹{len(cod_ndr_df)*1}.",
                "task_due": _due_str(4),
                "task":     f"Launch WhatsApp NDR campaign for {len(cod_ndr_df)} COD shipments",
            },
        })

    # ── 4. Courier underperformance ───────────────────────────────────────────
    if len(cour_df) > 1:
        avg_del  = cour_df["delivery_rate"].mean()
        bad_cour = cour_df[(cour_df["delivery_rate"] < avg_del - 15) & (cour_df["total"] >= 10)]
        if len(bad_cour) > 0:
            wc = bad_cour.sort_values("delivery_rate").iloc[0]
            vol_pct = wc["total"] / total * 100
            issues.append({
                "id":        _ticket_id(),
                "severity":  "HIGH" if vol_pct > 20 else "MEDIUM",
                "title":     f"⚠ {wc['courier']} Underperforming — {wc['delivery_rate']:.0f}% Delivery Rate",
                "what":      (f"<b>{wc['courier']}</b> delivering only <b>{wc['delivery_rate']:.0f}%</b> "
                              f"on {int(wc['total'])} shipments — <b>{vol_pct:.0f}% of your volume</b>. "
                              f"Fleet average: {avg_del:.0f}%."),
                "why":       (f"Courier pincode coverage or capacity issue. "
                              f"Gap of {avg_del - wc['delivery_rate']:.0f}% vs fleet average "
                              f"suggests routing mismatch, not demand issue."),
                "impact":    (f"If volume shifted to best courier: est. "
                              f"<b>{int(wc['total'] * (avg_del - wc['delivery_rate']) / 100):,} additional deliveries</b>. "
                              f"Immediate re-routing can recover these shipments."),
                "affected_count": int(wc["total"]),
                "affected_items": [{"courier": wc["courier"],
                                    "delivery_rate": f"{wc['delivery_rate']:.1f}%",
                                    "rto_rate": f"{wc['rto_rate']:.1f}%",
                                    "total": int(wc["total"])}],
                "action_context": {
                    "ops_msg":  f"{wc['courier']} at {wc['delivery_rate']:.0f}% delivery — review allocation and cap volume",
                    "wa_msg":   f"🚚 Courier Alert: {wc['courier']} delivering {wc['delivery_rate']:.0f}%. Ops review needed.",
                    "task_due": _due_str(6),
                    "task":     f"Review {wc['courier']} volume allocation — cap new bookings until delivery improves",
                },
            })

    # ── 5. High-RTO pincodes still receiving COD ─────────────────────────────
    if "pincode" in df.columns and "payment_type" in df.columns:
        pg = df.groupby("pincode").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
            cod  =("payment_type",    lambda x:(x=="COD").sum()),
        ).reset_index()
        pg["rr"] = pg["rto"] / pg["total"].clip(lower=1) * 100
        pg["cod_pct"] = pg["cod"] / pg["total"].clip(lower=1) * 100
        danger = pg[(pg["rr"] > 60) & (pg["total"] >= 3) & (pg["cod_pct"] > 50)]
        if len(danger) > 0:
            cod_at_risk = int(danger["cod"].sum())
            issues.append({
                "id":        _ticket_id(),
                "severity":  "HIGH",
                "title":     f"⚠ {len(danger)} Pincodes with >60% RTO Still Receiving COD Orders",
                "what":      (f"<b>{len(danger)} pincodes</b> have RTO rate above 60% but are still "
                              f"accepting COD orders. <b>{cod_at_risk} COD shipments</b> currently exposed."),
                "why":       ("No pincode-level COD restriction in place. Historical failure rates not "
                              "being used to gate new COD orders — amplifying return losses."),
                "impact":    (f"<b>{cod_at_risk} COD shipments</b> at high risk of RTO. "
                              f"Blacklisting these {len(danger)} pincodes for COD prevents future losses. "
                              f"Zero cost intervention — policy change only."),
                "affected_count": cod_at_risk,
                "affected_items": danger.nlargest(5, "rr")[["pincode","total","rr","cod_pct"]].to_dict("records"),
                "action_context": {
                    "ops_msg":  f"{len(danger)} pincodes with >60% RTO accepting COD — blacklist for COD immediately",
                    "wa_msg":   f"📍 {len(danger)} pincodes at >60% RTO. {cod_at_risk} COD orders at risk. Blacklist now.",
                    "task_due": _due_str(3),
                    "task":     f"Blacklist {len(danger)} high-RTO pincodes for COD in seller portal",
                },
            })

    # Sort: CRITICAL first, then HIGH, MEDIUM
    order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2}
    issues.sort(key=lambda x: order.get(x["severity"], 3))
    return issues


# ══════════════════════════════════════════════════════════════════════════════
# RENDER
# ══════════════════════════════════════════════════════════════════════════════

def render_agent_ops(df, m, cour_df, state_df):
    """Main entry point — renders the agentic operations section."""

    issues = detect_critical_issues(df, m, cour_df, state_df)

    # ── Agent scanner header ──────────────────────────────────────────────────
    critical_count = sum(1 for i in issues if i["severity"] == "CRITICAL")
    high_count     = sum(1 for i in issues if i["severity"] == "HIGH")
    all_clear      = len(issues) == 0

    if all_clear:
        st.markdown("""
        <div style="background:rgba(52,211,153,0.07);border:1px solid rgba(52,211,153,0.25);
             border-radius:12px;padding:14px 20px;margin-bottom:8px;
             display:flex;align-items:center;gap:14px;">
          <div style="font-size:1.8rem;">✅</div>
          <div>
            <div style="color:#34D399;font-weight:700;font-size:0.95rem;">
              GDI Agent — No Critical Issues Detected</div>
            <div style="color:#6B7280;font-size:0.8rem;margin-top:2px;">
              All shipment metrics within acceptable thresholds. Agent continues monitoring.
            </div>
          </div>
        </div>""", unsafe_allow_html=True)
        return

    # ── Agent scan summary ────────────────────────────────────────────────────
    badge_c = f'<span style="background:#EF444420;color:#EF4444;border:1px solid #EF444450;padding:2px 10px;border-radius:99px;font-size:0.75rem;font-weight:700;">{critical_count} CRITICAL</span>' if critical_count else ""
    badge_h = f'<span style="background:#F59E0B20;color:#F59E0B;border:1px solid #F59E0B50;padding:2px 10px;border-radius:99px;font-size:0.75rem;font-weight:700;margin-left:6px;">{high_count} HIGH</span>' if high_count else ""

    st.markdown(f"""
    <div style="background:linear-gradient(135deg,#1A0A0A 0%,#1F1010 100%);
         border:1px solid #EF4444;border-radius:14px;padding:16px 22px;margin-bottom:16px;">
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:10px;">
        <div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:4px;">
            <span style="font-size:1.4rem;">🤖</span>
            <span style="color:#FCA5A5;font-size:0.72rem;font-weight:700;text-transform:uppercase;
                         letter-spacing:0.08em;">GDI Agentic Consultant — Live Scan Complete</span>
          </div>
          <div style="color:#FFFFFF;font-size:1.1rem;font-weight:800;">
            {len(issues)} Critical Issue{"s" if len(issues)!=1 else ""} Require Immediate Action
          </div>
          <div style="margin-top:6px;">{badge_c}{badge_h}</div>
        </div>
        <div style="text-align:right;">
          <div style="color:#6B7280;font-size:0.72rem;">Scanned {m['total']:,} shipments</div>
          <div style="color:#9CA3AF;font-size:0.72rem;margin-top:2px;">
            Auto-refreshes with data · Simulation mode</div>
        </div>
      </div>
    </div>""", unsafe_allow_html=True)

    # ── issue cards ───────────────────────────────────────────────────────────
    for issue in issues:
        sev  = SEVERITY[issue["severity"]]
        ikey = issue["id"]

        # init session state for this issue's actions
        for action in ["ops", "wa", "task"]:
            sk = f"agent_{ikey}_{action}"
            if sk not in st.session_state:
                st.session_state[sk] = None   # None = not taken

        st.markdown(f"""
        <div style="background:#111827;border:1px solid {sev['border']}55;
             border-left:4px solid {sev['bg']};border-radius:12px;
             padding:18px 20px;margin-bottom:14px;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;
                      flex-wrap:wrap;gap:10px;margin-bottom:14px;">
            <div style="flex:1;">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
                <span style="background:{sev['bg']}20;color:{sev['bg']};
                             border:1px solid {sev['bg']}50;padding:2px 10px;
                             border-radius:99px;font-size:0.72rem;font-weight:700;">
                  {sev['icon']} {sev['label']} · #{ikey}</span>
              </div>
              <div style="color:#FFFFFF;font-size:1.0rem;font-weight:700;line-height:1.3;">
                {issue['title']}</div>
            </div>
            <div style="text-align:right;color:#6B7280;font-size:0.75rem;">
              {issue['affected_count']:,} shipments affected
            </div>
          </div>
        """, unsafe_allow_html=True)

        # Three detail columns
        d1, d2, d3 = st.columns(3)
        with d1:
            st.markdown(f"""<div style="background:#0B0F19;border-radius:8px;padding:12px;height:100%;">
              <div style="color:#9CA3AF;font-size:0.68rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.06em;margin-bottom:6px;">📋 WHAT</div>
              <div style="color:#D1D5DB;font-size:0.8rem;line-height:1.55;">{issue['what']}</div>
            </div>""", unsafe_allow_html=True)
        with d2:
            st.markdown(f"""<div style="background:#0B0F19;border-radius:8px;padding:12px;height:100%;">
              <div style="color:#9CA3AF;font-size:0.68rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.06em;margin-bottom:6px;">🔍 WHY</div>
              <div style="color:#D1D5DB;font-size:0.8rem;line-height:1.55;">{issue['why']}</div>
            </div>""", unsafe_allow_html=True)
        with d3:
            st.markdown(f"""<div style="background:#0B0F19;border-radius:8px;padding:12px;height:100%;">
              <div style="color:#9CA3AF;font-size:0.68rem;font-weight:700;text-transform:uppercase;
                          letter-spacing:0.06em;margin-bottom:6px;">💥 BUSINESS IMPACT</div>
              <div style="color:#D1D5DB;font-size:0.8rem;line-height:1.55;">{issue['impact']}</div>
            </div>""", unsafe_allow_html=True)

        st.markdown("<div style='height:12px;'></div>", unsafe_allow_html=True)

        # Affected items table (compact)
        if issue["affected_items"]:
            with st.expander(f"📊 View affected shipments ({min(5, issue['affected_count'])} shown)", expanded=False):
                try:
                    disp_df = pd.DataFrame(issue["affected_items"])
                    # Rename columns for display
                    rename_map = {
                        "awb": "AWB", "seller_name": "Seller", "state": "State",
                        "attempt_count": "Attempts", "ndr_reason": "NDR Reason",
                        "order_value": "Order ₹", "delivery_rate": "Del %",
                        "rto_rate": "RTO %", "total": "Shipments",
                        "rr": "RTO %", "cod_pct": "COD %", "pincode": "Pincode",
                        "courier": "Courier",
                    }
                    disp_df = disp_df.rename(columns={k:v for k,v in rename_map.items() if k in disp_df.columns})
                    if "Order ₹" in disp_df.columns:
                        disp_df["Order ₹"] = disp_df["Order ₹"].apply(lambda x: f"₹{float(x):,.0f}" if pd.notna(x) else "")
                    if "RTO %" in disp_df.columns and disp_df["RTO %"].dtype != object:
                        disp_df["RTO %"] = disp_df["RTO %"].apply(lambda x: f"{x:.1f}%")
                    st.dataframe(disp_df, use_container_width=True, hide_index=True)
                except Exception:
                    pass

        # ── Action buttons ────────────────────────────────────────────────────
        st.markdown("""<div style="color:#9CA3AF;font-size:0.68rem;font-weight:700;text-transform:uppercase;
                        letter-spacing:0.06em;margin:4px 0 8px;">⚡ ACTIONS</div>""",
                    unsafe_allow_html=True)

        ac = issue["action_context"]
        btn1, btn2, btn3, spacer = st.columns([2, 2, 2, 3])

        ops_key  = f"agent_{ikey}_ops"
        wa_key   = f"agent_{ikey}_wa"
        task_key = f"agent_{ikey}_task"

        with btn1:
            if st.session_state[ops_key] is None:
                if st.button("🏢 Raise to Operations", key=f"btn_ops_{ikey}", use_container_width=True):
                    ref = _ticket_id()
                    st.session_state[ops_key] = {
                        "ref":  ref,
                        "time": _now_str(),
                        "msg":  ac["ops_msg"],
                    }
                    st.rerun()
            else:
                r = st.session_state[ops_key]
                st.markdown(f"""
                <div style="background:rgba(52,211,153,0.08);border:1px solid rgba(52,211,153,0.3);
                     border-radius:8px;padding:10px 12px;">
                  <div style="color:#34D399;font-weight:700;font-size:0.8rem;">✅ Raised to Ops</div>
                  <div style="color:#9CA3AF;font-size:0.72rem;margin-top:3px;">Ref: {r['ref']}</div>
                  <div style="color:#6B7280;font-size:0.7rem;">Sent {r['time']}</div>
                  <div style="color:#D1D5DB;font-size:0.72rem;margin-top:4px;line-height:1.4;">"{r['msg']}"</div>
                </div>""", unsafe_allow_html=True)

        with btn2:
            if st.session_state[wa_key] is None:
                if st.button("💬 Raise via WhatsApp", key=f"btn_wa_{ikey}", use_container_width=True):
                    st.session_state[wa_key] = {
                        "time": _now_str(),
                        "msg":  ac["wa_msg"],
                    }
                    st.rerun()
            else:
                r = st.session_state[wa_key]
                st.markdown(f"""
                <div style="background:rgba(37,211,102,0.08);border:1px solid rgba(37,211,102,0.3);
                     border-radius:8px;padding:10px 12px;">
                  <div style="color:#25D366;font-weight:700;font-size:0.8rem;">✅ WA Message Sent</div>
                  <div style="color:#9CA3AF;font-size:0.72rem;margin-top:3px;">To: Ops Group</div>
                  <div style="color:#6B7280;font-size:0.7rem;">Sent {r['time']}</div>
                  <div style="color:#D1D5DB;font-size:0.72rem;margin-top:4px;line-height:1.4;">"{r['msg']}"</div>
                </div>""", unsafe_allow_html=True)

        with btn3:
            if st.session_state[task_key] is None:
                if st.button("📋 Create Follow-up Task", key=f"btn_task_{ikey}", use_container_width=True):
                    ref = _ticket_id()
                    st.session_state[task_key] = {
                        "ref":  ref,
                        "time": _now_str(),
                        "due":  ac["task_due"],
                        "task": ac["task"],
                    }
                    st.rerun()
            else:
                r = st.session_state[task_key]
                st.markdown(f"""
                <div style="background:rgba(129,140,248,0.08);border:1px solid rgba(129,140,248,0.3);
                     border-radius:8px;padding:10px 12px;">
                  <div style="color:#818CF8;font-weight:700;font-size:0.8rem;">✅ Task Created</div>
                  <div style="color:#9CA3AF;font-size:0.72rem;margin-top:3px;">#{r['ref']}</div>
                  <div style="color:#6B7280;font-size:0.7rem;">Due: {r['due']}</div>
                  <div style="color:#D1D5DB;font-size:0.72rem;margin-top:4px;line-height:1.4;">"{r['task']}"</div>
                </div>""", unsafe_allow_html=True)

        # dismiss button
        dismiss_key = f"agent_{ikey}_dismissed"
        if st.session_state.get(dismiss_key):
            pass
        else:
            with spacer:
                all_done = all(
                    st.session_state.get(f"agent_{ikey}_{a}") is not None
                    for a in ["ops", "wa", "task"]
                )
                if all_done:
                    if st.button("✔ Mark Resolved", key=f"btn_dismiss_{ikey}",
                                 use_container_width=True, type="primary"):
                        st.session_state[f"agent_{ikey}_dismissed"] = True
                        st.rerun()

        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown("<div style='height:4px;'></div>", unsafe_allow_html=True)
