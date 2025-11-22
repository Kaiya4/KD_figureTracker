import streamlit as st
import pandas as pd
import json

st.set_page_config(layout="wide", page_title="GoodSmile Tracker")

# Load Data
try:
    with open("products.json", "r") as f:
        products = json.load(f)
except FileNotFoundError:
    st.error("products.json not found! Run import_products.py first.")
    st.stop()

st.title(f"🧸 Figure Tracker ({len(products)} Items)")

# Filters
filter_status = st.radio("Show:", ["All", "In Stock Only", "Out of Stock Only"], horizontal=True)
search = st.text_input("Search figures...", "")

cols = st.columns(4)

for i, p in enumerate(products):
    # Filter Logic
    if filter_status == "In Stock Only" and p.get("last_status") != "In Stock": continue
    if filter_status == "Out of Stock Only" and p.get("last_status") != "Out of Stock": continue
    if search.lower() and search.lower() not in p['name'].lower(): continue
        
    with cols[i % 4]:
        with st.container(border=True):
            # Image
            if p.get("image"):
                st.image(p["image"], use_column_width=True)
            
            st.caption(p["name"])
            
            # Status
            status = p.get('last_status', 'Unknown')
            color = "green" if status == "In Stock" else "red"
            st.markdown(f":{color}[**{status}**]")
            
            # Price
            price = p.get('last_price', 0)
            st.metric("Price", f"${price}")
            
            # Chart
            if p.get("history"):
                df = pd.DataFrame(list(p["history"].items()), columns=["Date", "Price"])
                st.line_chart(df.set_index("Date"), height=100)
            
            st.markdown(f"[View on Site]({p['url']})")