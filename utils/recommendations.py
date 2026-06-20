"""
GDI Recommendation Engine — Velocity-first, data-backed, KAM persona.

Priority order (never ATS-first):
  1. AI Calling           — NDR recovery
  2. WhatsApp NDR         — COD NDR re-engagement
  3. Order Confirmation   — Pre-dispatch fake-order filter
  4. NDR Automation       — Rule-based NDR routing
  5. Courier Optimization — Delivery rate rebalancing
  6. Shipping Rules       — State/pincode COD restrictions
  7. Pincode Optimization — Blacklist high-RTO pincodes
  8. Multi-Courier Alloc. — Concentration risk fix
  9. NDD Activation       — ElasticRun / PiknDel / Blitz for Zone A/B
 10. ATS Address Verif.   — Only after all Velocity options exhausted

ATS is NEVER the first recommendation.
"""
import pandas as pd
import numpy as np

# ── Velocity NDD partners ─────────────────────────────────────────────────────
NDD_COURIERS = {
    "ElasticRun": {
        "strength": "Zone A/B NDD, metro + Tier-1 density",
        "best_for":  ["Zone A", "Zone B", "metro pincodes"],
        "del_rate":  88,    # fleet benchmark
    },
    "PiknDel": {
        "strength": "Zone B/C NDD, Tier-2 coverage",
        "best_for":  ["Zone B", "Zone C"],
        "del_rate":  84,
    },
    "Blitz": {
        "strength": "Tier-1 NDD, tech-first last-mile",
        "best_for":  ["Zone A", "Tier-1 cities"],
        "del_rate":  86,
    },
}

VELOCITY_SERVICES = [
    "AI Calling", "WhatsApp NDR", "Order Confirmation Via AI",
    "NDR Automation", "Courier Optimization", "Shipping Rule Optimization",
    "Pincode Optimization", "Multi-Courier Allocation", "NDD Activation",
]

# ── courier concentration detection ───────────────────────────────────────────
def detect_courier_concentration(df):
    """
    Returns dict with:
      is_concentrated: bool
      courier_count: int
      couriers_used: list
      dominant_courier: str
      dominant_pct: float
      recommended_add: list of NDD couriers to activate
    """
    if "courier" not in df.columns or len(df) == 0:
        return {"is_concentrated": False}

    cg = df.groupby("courier").agg(total=("delivery_status","count")).reset_index()
    cg["pct"] = cg["total"] / len(df) * 100
    cg = cg.sort_values("pct", ascending=False)

    n_couriers = len(cg)
    dominant   = cg.iloc[0]

    # Concentration = 1 courier OR 1 courier with >80% share
    is_concentrated = (n_couriers == 1) or (dominant["pct"] > 80)

    # Recommend NDD couriers not already used
    couriers_used    = cg["courier"].tolist()
    ndd_to_recommend = [c for c in NDD_COURIERS if c not in couriers_used
                        and not any(c.lower() in u.lower() for u in couriers_used)]

    return {
        "is_concentrated":    is_concentrated,
        "courier_count":      n_couriers,
        "couriers_used":      couriers_used,
        "dominant_courier":   dominant["courier"],
        "dominant_pct":       round(dominant["pct"], 1),
        "dominant_volume":    int(dominant["total"]),
        "all_couriers":       cg.to_dict("records"),
        "recommended_add":    ndd_to_recommend[:3] or list(NDD_COURIERS.keys()),
    }


# ── state × courier recommendations ───────────────────────────────────────────
def recommend_by_state(df, cour_df):
    """
    For every state, find current courier mix and recommend best courier.
    Returns list of dicts with state, current_del%, current_courier,
    recommended_courier, expected_improvement.
    """
    if "state" not in df.columns or "courier" not in df.columns:
        return []

    # Best courier per state from data
    state_cour = df.groupby(["state","courier"]).agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
    ).reset_index()
    state_cour["dr"] = state_cour["delivered"] / state_cour["total"].clip(lower=1) * 100

    # State totals (all couriers combined)
    state_total = df.groupby("state").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
    ).reset_index()
    state_total["current_dr"] = state_total["delivered"] / state_total["total"].clip(lower=1) * 100

    # Best courier fleet-wide (from cour_df)
    best_fleet = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["courier"] \
                 if len(cour_df) > 0 else None
    best_fleet_dr = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["delivery_rate"] \
                    if len(cour_df) > 0 else 80

    results = []
    for _, row in state_total[state_total["total"] >= 3].sort_values("current_dr").head(10).iterrows():
        state = row["state"]
        curr_dr = row["current_dr"]

        # Find best courier in this state from actual data
        state_data = state_cour[state_cour["state"] == state]
        current_courier = "Mixed"
        best_in_state   = None
        best_in_state_dr= curr_dr

        if len(state_data) > 0:
            best_row = state_data.sort_values("dr", ascending=False).iloc[0]
            current_courier  = state_data.sort_values("total", ascending=False).iloc[0]["courier"]
            best_in_state    = best_row["courier"]
            best_in_state_dr = best_row["dr"]

        # Recommend: if best in state is different from dominant → recommend it
        # Otherwise recommend best fleet courier
        if best_in_state and best_in_state != current_courier and best_in_state_dr > curr_dr + 3:
            rec_courier = best_in_state
            exp_dr      = best_in_state_dr
        elif best_fleet and best_fleet != current_courier:
            rec_courier = best_fleet
            exp_dr      = best_fleet_dr
        else:
            rec_courier = current_courier
            exp_dr      = curr_dr

        gap = exp_dr - curr_dr
        if gap < 2:
            continue   # skip if improvement < 2%

        results.append({
            "state":           state,
            "shipments":       int(row["total"]),
            "current_dr":      round(curr_dr, 1),
            "current_courier": current_courier,
            "rec_courier":     rec_courier,
            "expected_dr":     round(exp_dr, 1),
            "improvement":     round(gap, 1),
            "rto_reduction":   round(gap * 0.7, 1),  # conservative: 70% of delivery gain = RTO reduction
        })

    return sorted(results, key=lambda x: x["improvement"], reverse=True)


# ── product × courier recommendations ─────────────────────────────────────────
def recommend_by_product(df, cour_df):
    """
    For top products with worst RTO, recommend courier + shipping rule.
    """
    if "product_name" not in df.columns:
        return []

    pg = df.groupby("product_name").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        cod      =("payment_type",    lambda x:(x=="COD").sum()) if "payment_type" in df.columns
                   else ("delivery_status","count"),
        avg_val  =("order_value","mean"),
    ).reset_index()
    pg["dr"]      = pg["delivered"] / pg["total"].clip(lower=1) * 100
    pg["rr"]      = pg["rto"]       / pg["total"].clip(lower=1) * 100
    pg["cod_pct"] = pg["cod"]        / pg["total"].clip(lower=1) * 100

    fleet_avg_rr = pg["rr"].mean()
    best_cour    = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["courier"] \
                  if len(cour_df) > 0 else "top courier"

    results = []
    for _, row in pg[pg["total"] >= 3].sort_values("rr", ascending=False).head(8).iterrows():
        if row["rr"] < fleet_avg_rr * 1.2:
            continue

        # Build data-backed recommendation
        rec_actions = []
        if row["cod_pct"] > 65 and row["rr"] > 25:
            rec_actions.append(f"Restrict COD for orders < ₹{int(row['avg_val']*0.7):,}")
        if row["rr"] > 30:
            rec_actions.append(f"Route via {best_cour} (best delivery in your network)")
        if row["rr"] > 40:
            rec_actions.append("Activate Order Confirmation Via AI before dispatch")

        if not rec_actions:
            rec_actions.append("Enable WhatsApp NDR for failed deliveries")

        results.append({
            "product":       row["product_name"],
            "shipments":     int(row["total"]),
            "rto_pct":       round(row["rr"], 1),
            "cod_pct":       round(row["cod_pct"], 1),
            "avg_val":       round(row["avg_val"], 0),
            "fleet_avg_rto": round(fleet_avg_rr, 1),
            "vs_avg":        round(row["rr"] - fleet_avg_rr, 1),
            "actions":       rec_actions,
        })

    return results


# ── pincode cluster recommendations ───────────────────────────────────────────
def recommend_by_pincode(df, cour_df):
    """
    High-RTO pincodes + recommended action (restrict COD / switch courier / blacklist).
    """
    if "pincode" not in df.columns:
        return []

    pin_g = df.groupby("pincode").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x:(x=="Delivered").sum()),
        rto      =("delivery_status", lambda x:(x=="RTO").sum()),
        cod      =("payment_type",    lambda x:(x=="COD").sum()) if "payment_type" in df.columns
                   else ("delivery_status","count"),
        state    =("state","first") if "state" in df.columns else ("delivery_status","count"),
    ).reset_index()
    pin_g["dr"]      = pin_g["delivered"] / pin_g["total"].clip(lower=1) * 100
    pin_g["rr"]      = pin_g["rto"]       / pin_g["total"].clip(lower=1) * 100
    pin_g["cod_pct"] = pin_g["cod"]        / pin_g["total"].clip(lower=1) * 100

    best_cour = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]["courier"] \
                if len(cour_df) > 0 else "top courier"

    results = []
    for _, row in pin_g[pin_g["total"] >= 2].sort_values("rr", ascending=False).head(12).iterrows():
        if row["rr"] < 35:
            continue

        if row["rr"] >= 70:
            action   = "Blacklist for COD — zero tolerance zone"
            severity = "CRITICAL"
        elif row["rr"] >= 50:
            action   = f"Restrict COD + route via {best_cour}"
            severity = "HIGH"
        else:
            action   = f"Monitor + activate WhatsApp NDR for COD shipments"
            severity = "MEDIUM"

        results.append({
            "pincode":   str(row["pincode"]),
            "state":     str(row["state"]) if "state" in df.columns else "",
            "shipments": int(row["total"]),
            "rto_pct":   round(row["rr"], 1),
            "cod_pct":   round(row["cod_pct"], 1),
            "action":    action,
            "severity":  severity,
        })

    return results


# ── master recommendation list (Velocity-first) ───────────────────────────────
def build_velocity_recommendations(df, m, cour_df, conc):
    """
    Returns ordered list of recommendations — Velocity services first.
    ATS appears only if all Velocity options already triggered.
    """
    recs = []

    # 1. AI Calling
    if m.get("ndr_pct", 0) > 10:
        rec_cnt = int(m["ndr_count"] * 0.38)
        recs.append({
            "priority": 1,
            "name":     "AI Calling",
            "badge":    "Velocity · AI Calling",
            "color":    "#818CF8",
            "trigger":  f"NDR rate {m['ndr_pct']:.1f}% — {m['ndr_count']:,} active NDRs",
            "impact":   f"Recover ~{rec_cnt:,} NDR shipments via AI-powered outbound IVR",
            "metric":   f"{rec_cnt:,} recoveries expected at 38% rate",
        })

    # 2. WhatsApp NDR
    if m.get("cod_pct", 0) > 50 and m.get("ndr_pct", 0) > 8:
        saved = int(m["rto_count"] * 0.08)
        recs.append({
            "priority": 2,
            "name":     "WhatsApp NDR",
            "badge":    "Velocity · WhatsApp",
            "color":    "#25D366",
            "trigger":  f"COD {m['cod_pct']:.0f}% + NDR {m['ndr_pct']:.1f}% — {m['ndr_count']:,} COD NDRs",
            "impact":   f"Re-engage COD buyers via WhatsApp — {saved:,} RTOs preventable",
            "metric":   f"{saved:,} RTOs prevented at 8% recovery rate",
        })

    # 3. Order Confirmation Via AI
    if m.get("rto_pct", 0) > 12 or m.get("cod_pct", 0) > 55:
        saved = int(m["rto_count"] * 0.12)
        recs.append({
            "priority": 3,
            "name":     "Order Confirmation Via AI",
            "badge":    "Velocity · Pre-Dispatch",
            "color":    "#34D399",
            "trigger":  f"RTO {m['rto_pct']:.1f}% with {m['cod_pct']:.0f}% COD share",
            "impact":   f"AI call confirms COD intent before dispatch — blocks ~{saved:,} fake orders",
            "metric":   f"{saved:,} RTOs avoided pre-dispatch at 12% reduction",
        })

    # 4. NDR Automation
    if m.get("ndr_pct", 0) > 20:
        recs.append({
            "priority": 4,
            "name":     "NDR Automation",
            "badge":    "Velocity · Automation",
            "color":    "#60A5FA",
            "trigger":  f"NDR rate {m['ndr_pct']:.1f}% — exceeds 20% threshold for automation",
            "impact":   "Auto-route NDRs to AI Calling or WhatsApp based on reason, COD flag, and attempt count",
            "metric":   f"Eliminates manual NDR triage for {m['ndr_count']:,} shipments",
        })

    # 5. Courier Optimization
    if len(cour_df) > 1:
        variance = cour_df["delivery_rate"].std()
        if variance > 10:
            best  = cour_df.sort_values("delivery_rate", ascending=False).iloc[0]
            worst = cour_df.sort_values("delivery_rate").iloc[0]
            recs.append({
                "priority": 5,
                "name":     "Courier Optimization",
                "badge":    "Velocity · Routing",
                "color":    "#FBBF24",
                "trigger":  f"{worst['courier']} at {worst['delivery_rate']:.0f}% vs {best['courier']} at {best['delivery_rate']:.0f}%",
                "impact":   f"Shift volume from {worst['courier']} to {best['courier']} — {(best['delivery_rate']-worst['delivery_rate']):.0f}% delivery gap",
                "metric":   f"~{int(worst['total']*(best['delivery_rate']-worst['delivery_rate'])/100):,} additional deliveries",
            })

    # 6. Shipping Rule Optimization (state-level COD restriction)
    if "state" in df.columns and "payment_type" in df.columns:
        st_cod = df[df["payment_type"]=="COD"].groupby("state").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        st_cod["rr"] = st_cod["rto"] / st_cod["total"].clip(lower=1) * 100
        bad_states = st_cod[st_cod["rr"] > 40]
        if len(bad_states) > 0:
            recs.append({
                "priority": 6,
                "name":     "Shipping Rule Optimization",
                "badge":    "Velocity · Rules Engine",
                "color":    "#F87171",
                "trigger":  f"{len(bad_states)} states with COD-RTO > 40%",
                "impact":   f"Block COD for high-risk state + product combinations via Velocity Rules Engine",
                "metric":   f"Targets {int(bad_states['rto'].sum()):,} avoidable RTOs in {', '.join(bad_states.nlargest(3,'rr')['state'].tolist())}",
            })

    # 7. Pincode Optimization
    if "pincode" in df.columns:
        pg = df.groupby("pincode").agg(
            total=("delivery_status","count"),
            rto  =("delivery_status", lambda x:(x=="RTO").sum()),
        ).reset_index()
        pg["rr"] = pg["rto"] / pg["total"].clip(lower=1) * 100
        bad_pins = pg[(pg["rr"] > 50) & (pg["total"] >= 2)]
        if len(bad_pins) > 0:
            recs.append({
                "priority": 7,
                "name":     "Pincode Optimization",
                "badge":    "Velocity · Pincode Block",
                "color":    "#C084FC",
                "trigger":  f"{len(bad_pins)} pincodes with >50% RTO",
                "impact":   f"Blacklist {len(bad_pins)} pincodes for COD via Velocity seller portal — zero cost intervention",
                "metric":   f"{int(bad_pins['rto'].sum()):,} RTOs preventable by COD blacklisting",
            })

    # 8. Multi-Courier Allocation (concentration risk)
    if conc.get("is_concentrated"):
        recs.append({
            "priority": 8,
            "name":     "Multi-Courier Allocation",
            "badge":    "Velocity · Allocation",
            "color":    "#EF4444",
            "trigger":  f"Courier Concentration Risk — {conc['dominant_pct']:.0f}% volume on {conc['dominant_courier']}",
            "impact":   f"Add {', '.join(conc['recommended_add'][:2])} to reduce single-courier dependency",
            "metric":   f"Distributing across 3+ couriers reduces single-point delivery failure risk",
        })

    # 9. NDD Activation
    zone_col = next((c for c in df.columns if c in ["zone","standard_zone","Zone"]), None)
    if zone_col:
        zone_ab = df[df[zone_col].astype(str).str.upper().isin(["A","B"])]
        if len(zone_ab) > 0:
            pct = len(zone_ab)/max(len(df),1)*100
            recs.append({
                "priority": 9,
                "name":     "NDD Courier Activation",
                "badge":    "Velocity · NDD",
                "color":    "#10B981",
                "trigger":  f"{pct:.0f}% of volume ({len(zone_ab):,} shipments) in Zone A/B",
                "impact":   "Activate ElasticRun / PiknDel / Blitz for next-day delivery — reduces NDR by 15–20%",
                "metric":   f"{len(zone_ab):,} shipments eligible for NDD upgrade",
            })

    # 10. ATS Address Verification — LAST, only when RTO very high
    if m.get("rto_pct", 0) > 28 and len(recs) >= 3:
        recs.append({
            "priority": 10,
            "name":     "ATS Address Verification",
            "badge":    "ATS Partner Feature",
            "color":    "#6B7280",
            "trigger":  f"RTO {m['rto_pct']:.1f}% — address quality contributing factor",
            "impact":   "AI address correction at checkout (ATS integration) — reduces address-driven RTOs 4–6%",
            "metric":   f"Secondary to Velocity actions — activate after AI Calling + WhatsApp NDR",
        })

    return sorted(recs, key=lambda x: x["priority"])


# ── KAM system prompt for Claude ──────────────────────────────────────────────
KAM_SYSTEM_PROMPT = """You are GDI — Velocity Shipping's Growth & Delivery Intelligence Consultant.

You behave like an experienced Key Account Manager (KAM) and Operations Manager combined.
Your goal: help sellers improve delivery performance and adopt Velocity services.

PERSONA RULES:
- Always address the seller by their situation, not generically
- Lead with data: "Based on your X shipments in this period..."
- Be direct about problems: "Your {courier} is underperforming at {rate}% — here's exactly why"
- Prioritise Velocity-controlled actions, never ATS first
- If only 1 courier: always flag "Courier Concentration Risk"

RECOMMENDATION PRIORITY (strictly in this order):
1. AI Calling              — whenever NDR > 10%
2. WhatsApp NDR            — whenever COD > 50% AND NDR > 8%
3. Order Confirmation       — whenever RTO > 12% or COD > 55%
4. NDR Automation           — whenever NDR > 20%
5. Courier Optimization     — whenever delivery variance > 10%
6. Shipping Rule Optimization — whenever any state has COD-RTO > 40%
7. Pincode Optimization     — whenever any pincode has RTO > 50%
8. Multi-Courier Allocation — whenever 1 courier has > 80% volume share
9. NDD Activation           — whenever Zone A/B > 15% of shipments
10. ATS Address Verification — LAST RESORT ONLY (after all above)

COURIER CONCENTRATION RULE:
If seller uses only 1 courier OR 1 courier has > 80% share:
→ ALWAYS say: "Courier Concentration Risk Detected"
→ Recommend adding: ElasticRun (Zone A/B NDD), PiknDel (Zone B/C), Blitz (Tier-1 NDD)
→ Back with their actual state-wise data

FOR EVERY STATE / PRODUCT / COURIER / PINCODE RECOMMENDATION:
→ State current performance (real number from data)
→ State recommended courier (from Velocity network)
→ State expected improvement (realistic, not inflated)

NEVER:
- Say "ATS Address Verification" as a first recommendation
- Give generic advice without citing seller's own numbers
- Recommend ATS Smart Routing without first covering Velocity services
- Sound like a product catalogue — sound like their ops consultant

ALWAYS END WITH:
One specific action the seller can take TODAY, with a number attached."""
