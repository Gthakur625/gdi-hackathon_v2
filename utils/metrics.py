import pandas as pd
import numpy as np

VAS_CATALOG = [
    {
        "name":    "AI Calling",
        "trigger": lambda m: m["ndr_pct"] > 15,
        "impact":  lambda m: f"Recover ~{int(m['ndr_count']*0.38)} NDR shipments via AI-powered outbound calling",
        "revenue": lambda m: int(m["ndr_count"] * 0.38 * m["avg_order_value"]),
        "badge":   "AI Calling",
        "color":   "#818CF8",
    },
    {
        "name":    "Order Confirmation Via AI",
        "trigger": lambda m: m["rto_pct"] > 15 or m["cod_pct"] > 50,
        "impact":  lambda m: f"Confirm intent before dispatch — save ~{int(m['rto_count']*0.12)} fake/RTO orders",
        "revenue": lambda m: int(m["rto_count"] * 0.12 * m["avg_order_value"]),
        "badge":   "Order Confirmation",
        "color":   "#34D399",
    },
    {
        "name":    "WhatsApp AI NDR",
        "trigger": lambda m: m["cod_pct"] > 60 and m["ndr_pct"] > 10,
        "impact":  lambda m: f"Reduce COD RTO by ~8% (~{int(m['rto_count']*0.08)} saved) via WhatsApp nudges",
        "revenue": lambda m: int(m["rto_count"] * 0.08 * m["avg_order_value"]),
        "badge":   "WhatsApp AI NDR",
        "color":   "#FBBF24",
    },
    {
        "name":    "ATS Address Verification",
        "trigger": lambda m: m["rto_pct"] > 20,
        "impact":  lambda m: f"Reduce RTO by ~4–6% (~{int(m['total']*0.05)} shipments) via AI address correction at checkout",
        "revenue": lambda m: int(m["total"] * 0.05 * m["avg_order_value"]),
        "badge":   "ATS Recommended",
        "color":   "#60A5FA",
    },
    {
        "name":    "ATS Smart Routing",
        "trigger": lambda m: m["courier_score_variance"] > 15,
        "impact":  lambda m: "Improve delivery by 3–5% via pincode-level courier routing intelligence",
        "revenue": lambda m: int(m["total"] * 0.04 * m["avg_order_value"]),
        "badge":   "Smart Routing",
        "color":   "#C084FC",
    },
]


def compute_kpis(df):
    total = len(df)

    # Attempted = shipments that had a delivery attempt (Delivered / RTO / NDR)
    # Pending Pickup / In Transit / Cancelled = NOT yet attempted → excluded from delivery %
    # The agent will show pending count separately so users know they're excluded.
    attempted_mask = df["delivery_status"].isin(["Delivered", "RTO", "NDR"])
    attempted      = df[attempted_mask]
    attempted_total= len(attempted)

    pending_mask   = df["delivery_status"].isin(["In Transit", "Pending Pickup",
                                                   "Cancelled", "In Transit"])
    pending_count  = int(pending_mask.sum())

    delivered = int((attempted["delivery_status"] == "Delivered").sum())
    rto       = int((attempted["delivery_status"] == "RTO").sum())
    ndr       = int((df["ndr_status"] == "Raised").sum()) if "ndr_status" in df.columns else 0
    cod       = int((df["payment_type"] == "COD").sum())
    avg_ov    = df["order_value"].mean() if total > 0 else 0

    # Rates calculated on attempted shipments only (honest delivery %)
    delivery_pct = delivered / attempted_total * 100 if attempted_total else 0
    rto_pct      = rto      / attempted_total * 100 if attempted_total else 0
    ndr_pct      = ndr      / total           * 100 if total else 0
    cod_pct      = cod      / total           * 100 if total else 0

    courier_perf = compute_courier_perf(df)
    c_var = courier_perf["delivery_rate"].std() if len(courier_perf) > 1 else 0

    return {
        "total":                  total,
        "attempted_total":        attempted_total,
        "pending_count":          pending_count,
        "delivered":              delivered,
        "rto_count":              rto,
        "ndr_count":              ndr,
        "cod_count":              cod,
        "delivery_pct":           delivery_pct,
        "rto_pct":                rto_pct,
        "ndr_pct":                ndr_pct,
        "cod_pct":                cod_pct,
        "avg_order_value":        avg_ov,
        "courier_score_variance": c_var,
    }


def compute_health_score(m):
    vas_active = m.get("vas_adoption_score", 20)
    score = (
        m["delivery_pct"]            * 0.40 +
        (100 - m["rto_pct"])         * 0.25 +
        (100 - m["ndr_pct"])         * 0.20 +
        (100 - m["cod_pct"])         * 0.10 +
        vas_active                   * 0.05
    )
    return max(0.0, min(100.0, score))


def compute_vas_adoption_score(df):
    if "vas_active" not in df.columns:
        return 20
    all_vas = ["AI Calling","Order Confirmation Via AI","WhatsApp AI NDR","ATS Address Verification"]
    active_sets = df["vas_active"].dropna().str.split(", ")
    unique_active = set()
    for s in active_sets:
        unique_active.update(s)
    count = sum(1 for v in all_vas if v in unique_active)
    return (count / len(all_vas)) * 100


def compute_courier_perf(df):
    if len(df) == 0:
        return pd.DataFrame()
    # Use only attempted shipments for delivery/RTO rates
    t = df[df["delivery_status"].isin(["Delivered","RTO","NDR"])]
    if len(t) == 0:
        return pd.DataFrame()
    g = t.groupby("courier").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
        rto      =("delivery_status", lambda x: (x=="RTO").sum()),
    ).reset_index()
    g["delivery_rate"] = g["delivered"] / g["total"] * 100
    g["rto_rate"]      = g["rto"]       / g["total"] * 100
    return g


def compute_state_perf(df):
    if len(df) == 0:
        return pd.DataFrame()
    t = df[df["delivery_status"].isin(["Delivered","RTO","NDR"])]
    if len(t) == 0:
        return pd.DataFrame()
    g = t.groupby("state").agg(
        total    =("delivery_status","count"),
        delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
        rto      =("delivery_status", lambda x: (x=="RTO").sum()),
    ).reset_index()
    g["delivery_rate"] = g["delivered"] / g["total"] * 100
    g["rto_rate"]      = g["rto"]       / g["total"] * 100
    return g


def compute_sku_perf(df):
    if len(df) == 0:
        return pd.DataFrame()
    g = df.groupby(["sku","product_name","sku_category"] if "sku_category" in df.columns else ["sku","product_name"]).agg(
        total=("delivery_status","count"),
        delivered=("delivery_status", lambda x: (x=="Delivered").sum()),
        rto=("delivery_status", lambda x: (x=="RTO").sum()),
        ndr=("delivery_status", lambda x: (x=="NDR").sum()),
        revenue=("order_value","sum"),
        avg_value=("order_value","mean"),
    ).reset_index()
    g["delivery_rate"] = g["delivered"] / g["total"] * 100
    g["rto_rate"]      = g["rto"]       / g["total"] * 100
    g["revenue_at_risk"] = g["rto"] * g["avg_value"]
    return g.sort_values("rto_rate", ascending=False)


def get_recommendations(m):
    recs = []
    for vas in VAS_CATALOG:
        if vas["trigger"](m):
            recs.append({
                "name":    vas["name"],
                "impact":  vas["impact"](m),
                "revenue": vas["revenue"](m),
                "badge":   vas["badge"],
                "color":   vas["color"],
            })
    return recs


def get_anomalies(df, m, state_perf, courier_perf):
    anomalies = []

    # Geographic cluster
    if len(state_perf) > 0:
        worst = state_perf.sort_values("rto_rate", ascending=False).iloc[0]
        if worst["rto_rate"] > 30:
            share = worst["rto"] / m["rto_count"] * 100 if m["rto_count"] > 0 else 0
            anomalies.append({
                "level":  "critical",
                "title":  f"Geographic RTO Cluster — {worst['state']}",
                "detail": f"{worst['state']} accounts for {share:.0f}% of all RTOs ({int(worst['rto'])} shipments). "
                          f"Root cause: address quality + COD non-acceptance.",
                "fix":    f"Enable ATS Address Verification for {worst['state']} orders.",
                "icon":   "🔴",
            })

    # Courier misallocation
    if len(courier_perf) > 1:
        worst_c = courier_perf.sort_values("delivery_rate").iloc[0]
        worst_share = worst_c["total"] / m["total"] * 100 if m["total"] > 0 else 0
        if worst_c["delivery_rate"] < 70 and worst_share > 10:
            anomalies.append({
                "level":  "warning",
                "title":  f"Courier Misallocation — {worst_c['courier']}",
                "detail": f"{worst_c['courier']} holds {worst_share:.0f}% of volume but delivers only "
                          f"{worst_c['delivery_rate']:.1f}%. No smart routing rules in place.",
                "fix":    f"Shift {worst_c['courier']} share to ATS (Velocity) for standard pincodes.",
                "icon":   "🟡",
            })

    # COD concentration
    if m["cod_pct"] > 70:
        cod_rto = df[(df["payment_type"]=="COD") & (df["delivery_status"]=="RTO")]
        cod_rto_pct = len(cod_rto) / max(len(df[df["payment_type"]=="COD"]),1) * 100
        if cod_rto_pct > 20:
            anomalies.append({
                "level":  "warning",
                "title":  "COD Concentration Risk",
                "detail": f"{m['cod_pct']:.0f}% COD share with {cod_rto_pct:.0f}% COD-RTO rate. "
                          f"No prepaid incentive nudge detected at checkout.",
                "fix":    "Add 5% prepaid discount via Velocity Checkout. Activate WhatsApp NDR.",
                "icon":   "🟡",
            })

    # NDR aging queue
    if "ndr_age_hours" in df.columns:
        stale = df[(df["ndr_status"]=="Raised") & (df["ndr_age_hours"] > 48)]
        if len(stale) > 10:
            anomalies.append({
                "level":  "info",
                "title":  f"NDR Queue Aging — {len(stale)} Shipments Unresolved > 48h",
                "detail": f"{len(stale)} NDR shipments unresolved beyond 48 hours. Escalation risk to RTO.",
                "fix":    "Activate AI Calling for these shipments immediately. Expected 38% recovery.",
                "icon":   "🔵",
            })

    # SKU category spike
    if "sku_category" in df.columns:
        cat_perf = df.groupby("sku_category").agg(
            total=("delivery_status","count"),
            rto=("delivery_status", lambda x: (x=="RTO").sum()),
        )
        cat_perf["rto_rate"] = cat_perf["rto"] / cat_perf["total"] * 100
        avg_rto = m["rto_pct"]
        spikes = cat_perf[cat_perf["rto_rate"] > avg_rto * 1.5]
        if len(spikes) > 0:
            worst_cat = spikes.sort_values("rto_rate", ascending=False).index[0]
            worst_rate = spikes.loc[worst_cat, "rto_rate"]
            anomalies.append({
                "level":  "info",
                "title":  f"Category Spike — {worst_cat} RTO {worst_rate:.0f}%",
                "detail": f"{worst_cat} products have {worst_rate:.0f}% RTO — {(worst_rate/max(avg_rto,1)):.1f}x the seller average. "
                          f"High-value + COD combination is the primary driver.",
                "fix":    f"Restrict COD for {worst_cat} in high-risk states. Enable ATS Smart Routing.",
                "icon":   "🔵",
            })

    return anomalies
