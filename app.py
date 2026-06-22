import streamlit as st

st.set_page_config(
    page_title="JAGGU AI · Velocity GDI",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/0_GDI_Dashboard.py",   title="JAGGU Briefing",   icon="🤖", default=True),
    st.Page("pages/7_GDI_Consultant.py",  title="JaGau AI",          icon="💬"),
    st.Page("pages/8_VAS_Engine.py",      title="VAS Engine",         icon="⚙️"),
]
pg = st.navigation(pages)
pg.run()
