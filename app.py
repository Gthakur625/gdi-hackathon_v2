import streamlit as st

st.set_page_config(
    page_title="Velocity GDI",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("pages/0_GDI_Dashboard.py",    title="GDI Dashboard",  icon="⚡", default=True),
    st.Page("pages/7_AI_Chat_Assistant.py", title="Ask GDI Agent",  icon="🤖"),
]
pg = st.navigation(pages)
pg.run()
