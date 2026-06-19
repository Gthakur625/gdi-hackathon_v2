import streamlit as st
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from utils.styles  import apply_styles
from utils.sidebar import render_sidebar_and_get_data
from utils.metrics import compute_kpis, compute_vas_adoption_score, get_recommendations, VAS_CATALOG

st.set_page_config(page_title="ATS Recommendations · GDI", page_icon="🚀", layout="wide")
apply_styles()
df = render_sidebar_and_get_data()

m = compute_kpis(df)
m["vas_adoption_score"] = compute_vas_adoption_score(df)
recs = get_recommendations(m)

# Which VAS already active
active_vas = set()
if "vas_active" in df.columns:
    for row in df["vas_active"].dropna():
        active_vas.update(str(row).split(", "))

all_vas_names = [v["name"] for v in VAS_CATALOG]
not_recommended = [v for v in all_vas_names if v not in [r["name"] for r in recs] and v not in active_vas]

st.markdown("""
<div class="header-card">
  <h1 class="header-title">🚀 ATS Recommendation Engine</h1>
  <p class="header-subtitle">GDI maps your exact delivery problems to the Velocity VAS products that fix them — ranked by impact.</p>
</div>""", unsafe_allow_html=True)

# Summary
total_rev = sum(r["revenue"] for r in recs)
st.markdown(f"""
<div class="saas-card" style="background:linear-gradient(180deg,#161F30 0%,#111827 100%);border-left:4px solid #4F46E5;">
  <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;gap:16px;">
    <div>
      <div style="color:#9CA3AF;font-size:0.8rem;text-transform:uppercase;letter-spacing:0.05em;">GDI Verdict</div>
      <h2 style="color:#FFFFFF;font-size:1.5rem;font-weight:700;margin:6px 0;">
        {len(recs)} VAS Products Will Solve 80% of Your Issues
      </h2>
      <p style="color:#D1D5DB;font-size:0.93rem;margin:0;">
        Based on your delivery rate of <strong>{m['delivery_pct']:.1f}%</strong>, RTO of
        <strong>{m['rto_pct']:.1f}%</strong>, and NDR of <strong>{m['ndr_pct']:.1f}%</strong>.
        Activating recommended VAS unlocks an estimated <strong>₹{total_rev:,}</strong> in additional revenue.
      </p>
    </div>
    <div style="text-align:right;">
      <div class="metric-label">Revenue Unlock</div>
      <div style="font-size:2rem;font-weight:800;color:#34D399;">₹{total_rev:,}</div>
    </div>
  </div>
</div>""", unsafe_allow_html=True)

if not recs:
    st.success("🎉 All recommended VAS products are already active or not triggered by current metrics.")
else:
    st.markdown("<div class='section-title'>🎯 Your Personalised VAS Adoption Plan</div>", unsafe_allow_html=True)
    for i, rec in enumerate(recs):
        rank_label = ["#1 HIGHEST IMPACT","#2 HIGH IMPACT","#3 MEDIUM IMPACT","#4","#5"][min(i,4)]
        st.markdown(f"""
        <div class="saas-card" style="border:1px solid {rec['color']}40;position:relative;">
          <div style="display:flex;justify-content:space-between;align-items:flex-start;flex-wrap:wrap;gap:12px;">
            <div style="flex:1;">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px;">
                <span style="background:{rec['color']}20;color:{rec['color']};border:1px solid {rec['color']}50;
                             padding:3px 10px;border-radius:99px;font-size:0.72rem;font-weight:700;">{rank_label}</span>
                <span class="badge-recommend">{rec['badge']}</span>
              </div>
              <h3 style="color:#FFFFFF;font-size:1.25rem;font-weight:700;margin:0 0 6px 0;">{rec['name']}</h3>
              <p style="color:#D1D5DB;font-size:0.92rem;margin:0;">{rec['impact']}</p>
            </div>
            <div style="text-align:right;min-width:160px;">
              <div class="metric-label">Est. Revenue Unlock</div>
              <div style="font-size:1.6rem;font-weight:800;color:{rec['color']};">₹{rec['revenue']:,}</div>
              <div style="margin-top:10px;">
                <span style="background:{rec['color']}20;color:{rec['color']};border:1px solid {rec['color']}50;
                             padding:6px 18px;border-radius:8px;font-size:0.85rem;font-weight:700;cursor:pointer;">
                  Activate Now ▶
                </span>
              </div>
            </div>
          </div>
        </div>""", unsafe_allow_html=True)

# Already active
if active_vas:
    st.markdown("<div class='section-title'>✅ Already Active VAS</div>", unsafe_allow_html=True)
    cols = st.columns(min(len(active_vas), 4))
    for i, vas in enumerate(sorted(active_vas)):
        if vas.strip():
            cols[i % 4].markdown(f"""
            <div class="saas-card" style="border:1px solid rgba(16,185,129,0.3);text-align:center;">
              <div style="font-size:1.5rem;">✅</div>
              <div style="color:#34D399;font-weight:700;margin-top:6px;">{vas}</div>
              <div style="color:#9CA3AF;font-size:0.78rem;margin-top:4px;">Active</div>
            </div>""", unsafe_allow_html=True)

# Full VAS catalogue
with st.expander("📚 Full Velocity VAS Catalogue"):
    vas_info = [
        ("ATS Core Routing",         "Pincode-level smart courier allocation",             "Included",      "#818CF8"),
        ("ATS Address Verification", "AI address correction at checkout — reduces RTO 4–6%","Triggered by RTO > 20%","#34D399"),
        ("ATS AI Calling Suite",     "Automated IVR calling for NDR resolution — 38% recovery","Triggered by NDR > 15%","#60A5FA"),
        ("ATS WhatsApp NDR",         "WhatsApp buyer nudges for COD non-delivery — reduces COD RTO 8%","Triggered by COD > 60%","#FBBF24"),
        ("ATS Secure (Prepaid Push)","Checkout incentive to convert COD to Prepaid",       "Triggered by COD > 70%","#C084FC"),
    ]
    for name, desc, trigger, color in vas_info:
        is_active = name in active_vas
        border    = "rgba(16,185,129,0.4)" if is_active else f"{color}30"
        st.markdown(f"""
        <div style="background:#111827;border:1px solid {border};border-radius:10px;
                    padding:14px 18px;margin-bottom:10px;display:flex;justify-content:space-between;align-items:center;">
          <div>
            <span style="color:{color};font-weight:700;">{name}</span>
            {'<span style="color:#34D399;font-size:0.75rem;margin-left:8px;background:rgba(16,185,129,0.1);'
             'border:1px solid rgba(16,185,129,0.3);padding:2px 8px;border-radius:99px;">✓ Active</span>' if is_active else ""}
            <p style="color:#9CA3AF;font-size:0.85rem;margin:4px 0 0 0;">{desc}</p>
          </div>
          <div style="text-align:right;min-width:160px;">
            <span style="color:#6B7280;font-size:0.78rem;">{trigger}</span>
          </div>
        </div>""", unsafe_allow_html=True)
