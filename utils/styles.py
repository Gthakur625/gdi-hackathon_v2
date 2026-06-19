import streamlit as st

def apply_styles():
    st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800&display=swap');
    .stApp { background-color: #0B0F19; }
    [data-testid="stSidebar"] { background-color: #0F1626 !important; border-right: 1px solid #1E293B; }
    [data-testid="stSidebar"] label,[data-testid="stSidebar"] p,[data-testid="stSidebar"] span { color: #D1D5DB !important; }
    .main .block-container { padding-top: 1rem; }
    .header-card,.saas-card,.section-title,.metric-value,.metric-label,
    .badge-recommend,.badge-impact,.badge-risk-low,.badge-risk-medium,.badge-risk-high,
    .chat-bubble-user,.chat-bubble-bot,.anomaly-card { font-family: 'Outfit', sans-serif; }
    .header-card {
        background: linear-gradient(135deg,#4F46E5 0%,#7C3AED 50%,#C084FC 100%);
        padding: 28px 32px; border-radius: 16px; margin-bottom: 24px;
        box-shadow: 0 10px 25px -5px rgba(124,58,237,0.3);
        border: 1px solid rgba(255,255,255,0.1);
    }
    .header-title { color:#FFFFFF; font-size:2rem; font-weight:800; margin:0; letter-spacing:-0.02em; }
    .header-subtitle { color:#E0E7FF; font-size:1rem; font-weight:400; margin-top:4px; margin-bottom:0; opacity:0.9; }
    .saas-card {
        background-color:#111827; border:1px solid #1F2937; border-radius:14px;
        padding:22px; margin-bottom:18px; transition:border-color 0.2s ease,box-shadow 0.2s ease;
        box-shadow:0 2px 8px rgba(0,0,0,0.15);
    }
    .saas-card:hover { border-color:#4F46E5; box-shadow:0 8px 20px -8px rgba(79,70,229,0.25); }
    .section-title {
        font-size:1.2rem; font-weight:700; color:#FFFFFF; margin-top:8px; margin-bottom:14px;
        padding-bottom:8px; border-bottom:1px solid #1F2937;
    }
    .metric-value { font-size:2rem; font-weight:700; line-height:1.1; margin-top:8px; margin-bottom:4px; }
    .metric-label { font-size:0.78rem; text-transform:uppercase; letter-spacing:0.06em; color:#9CA3AF; font-weight:500; }
    .badge-recommend { background:rgba(79,70,229,0.15); color:#818CF8; border:1px solid rgba(79,70,229,0.35); padding:3px 10px; border-radius:99px; font-size:0.73rem; font-weight:600; display:inline-block; }
    .badge-risk-low  { background:rgba(16,185,129,0.12); color:#34D399; border:1px solid rgba(16,185,129,0.3); padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }
    .badge-risk-medium { background:rgba(245,158,11,0.12); color:#FBBF24; border:1px solid rgba(245,158,11,0.3); padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }
    .badge-risk-high   { background:rgba(239,68,68,0.12); color:#FCA5A5; border:1px solid rgba(239,68,68,0.3); padding:4px 12px; border-radius:6px; font-size:0.82rem; font-weight:700; }
    .anomaly-critical { background:#1F2937; padding:16px; border-radius:10px; border-left:4px solid #EF4444; margin-bottom:12px; }
    .anomaly-warning  { background:#1F2937; padding:16px; border-radius:10px; border-left:4px solid #F59E0B; margin-bottom:12px; }
    .anomaly-info     { background:#1F2937; padding:16px; border-radius:10px; border-left:4px solid #3B82F6; margin-bottom:12px; }
    .chat-bubble-user { background-color:#2D3748; color:#F3F4F6; padding:10px 15px; border-radius:16px 16px 4px 16px; margin-bottom:10px; max-width:78%; margin-left:auto; border:1px solid #4A5568; font-size:0.92rem; font-family:'Outfit',sans-serif; }
    .chat-bubble-bot  { background-color:#1F2937; color:#F3F4F6; padding:10px 15px; border-radius:16px 16px 16px 4px; margin-bottom:10px; max-width:78%; margin-right:auto; border:1px solid #374151; font-size:0.92rem; font-family:'Outfit',sans-serif; }
    .chip-btn { display:inline-block; background:rgba(79,70,229,0.12); color:#818CF8; border:1px solid rgba(79,70,229,0.3); padding:5px 14px; border-radius:99px; font-size:0.8rem; font-weight:600; margin:3px; cursor:pointer; }
    hr { border:0; height:1px; background:#1F2937; margin:18px 0; }
    </style>
    """, unsafe_allow_html=True)
