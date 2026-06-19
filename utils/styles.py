import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    .stApp { background-color: #0B0F19; }

    /* ── Sidebar ── */
    [data-testid="stSidebar"] {
        background-color: #0F1626 !important;
        border-right: 1px solid #1E293B;
    }
    [data-testid="stSidebar"] label,
    [data-testid="stSidebar"] p,
    [data-testid="stSidebar"] span,
    [data-testid="stSidebar"] div { color: #D1D5DB !important; }
    [data-testid="collapsedControl"] {
        color: #FFFFFF !important;
        background: #111827 !important;
        border: 1px solid #1F2937 !important;
        border-radius: 6px !important;
    }
    .main .block-container { padding-top: 1rem; }

    /* ── Fonts ── */
    .header-card, .saas-card, .section-title, .metric-value, .metric-label,
    .badge-recommend, .badge-risk-low, .badge-risk-medium, .badge-risk-high,
    .chat-bubble-user, .chat-bubble-bot { font-family: 'Outfit', sans-serif; }

    /* ── Header ── */
    .header-card {
        background: linear-gradient(135deg, #4F46E5 0%, #7C3AED 50%, #C084FC 100%);
        padding: 26px 30px; border-radius: 16px; margin-bottom: 22px;
        box-shadow: 0 10px 25px -5px rgba(124,58,237,0.3);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .header-title { color:#FFFFFF; font-size:1.9rem; font-weight:800; margin:0; letter-spacing:-0.02em; }
    .header-subtitle { color:#E0E7FF; font-size:0.95rem; margin-top:4px; margin-bottom:0; opacity:0.9; }

    /* ── Cards ── */
    .saas-card {
        background-color: #111827; border: 1px solid #1F2937; border-radius: 14px;
        padding: 20px; margin-bottom: 16px;
        transition: border-color 0.2s ease, box-shadow 0.2s ease;
        box-shadow: 0 2px 8px rgba(0,0,0,0.15);
    }
    .saas-card:hover { border-color:#4F46E5; box-shadow:0 8px 20px -8px rgba(79,70,229,0.25); }

    /* ── Section title ── */
    .section-title {
        font-size: 1.15rem; font-weight: 700; color: #FFFFFF;
        margin-top: 8px; margin-bottom: 12px;
        padding-bottom: 8px; border-bottom: 1px solid #1F2937;
    }

    /* ── Metrics ── */
    .metric-value { font-size:2rem; font-weight:700; line-height:1.1; margin-top:6px; margin-bottom:4px; }
    .metric-label { font-size:0.76rem; text-transform:uppercase; letter-spacing:0.06em; color:#9CA3AF; font-weight:500; }

    /* ── Badges ── */
    .badge-recommend {
        background: rgba(79,70,229,0.15); color: #818CF8;
        border: 1px solid rgba(79,70,229,0.35);
        padding: 3px 10px; border-radius: 99px; font-size: 0.72rem; font-weight: 600;
        display: inline-block;
    }
    .badge-risk-low    { background:rgba(16,185,129,0.12); color:#34D399; border:1px solid rgba(16,185,129,0.3); padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }
    .badge-risk-medium { background:rgba(245,158,11,0.12); color:#FBBF24; border:1px solid rgba(245,158,11,0.3); padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }
    .badge-risk-high   { background:rgba(239,68,68,0.12);  color:#FCA5A5; border:1px solid rgba(239,68,68,0.3);  padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }

    /* ── Anomaly cards ── */
    .anomaly-critical { background:#1F2937; padding:14px; border-radius:10px; border-left:4px solid #EF4444; margin-bottom:10px; }
    .anomaly-warning  { background:#1F2937; padding:14px; border-radius:10px; border-left:4px solid #F59E0B; margin-bottom:10px; }
    .anomaly-info     { background:#1F2937; padding:14px; border-radius:10px; border-left:4px solid #3B82F6; margin-bottom:10px; }

    /* ── Chat bubbles ── */
    .chat-bubble-user {
        background-color: #2D3748; color: #F3F4F6;
        padding: 10px 15px; border-radius: 16px 16px 4px 16px;
        margin-bottom: 10px; max-width: 78%; margin-left: auto;
        border: 1px solid #4A5568; font-size: 0.9rem;
    }
    .chat-bubble-bot {
        background-color: #1F2937; color: #F3F4F6;
        padding: 10px 15px; border-radius: 16px 16px 16px 4px;
        margin-bottom: 10px; max-width: 80%;
        border: 1px solid #374151; font-size: 0.9rem;
    }

    /* ── Divider ── */
    hr { border:0; height:1px; background:#1F2937; margin:16px 0; }

    /* ── Simulation card ── */
    .sim-card{background:#0B0F19;border:1px solid rgba(79,70,229,0.5);border-radius:12px;
              padding:16px 20px;margin:8px 0 12px;}
    .sim-row{display:flex;justify-content:space-between;padding:7px 0;
             border-bottom:1px solid #1F2937;font-size:0.84rem;}
    .sim-row:last-child{border-bottom:none;}
    .qchip{display:inline-block;background:rgba(79,70,229,0.10);color:#818CF8;
           border:1px solid rgba(79,70,229,0.25);padding:4px 12px;border-radius:99px;
           font-size:0.77rem;font-weight:600;margin:3px 3px 0 0;}
    </style>
    """, unsafe_allow_html=True)
