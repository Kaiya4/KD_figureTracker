import streamlit as st
import pandas as pd
import json
import plotly.express as px

st.set_page_config(layout="wide", page_title="GoodSmile Tracker")

# --- 1. LOAD DATA ---
try:
    with open("products.json", "r") as f:
        products = json.load(f)
except FileNotFoundError:
    st.error("Database not found! (Wait for the scraper to run first)")
    st.stop()

# --- 2. METRICS SECTION ---
# Calculate counts dynamically
total_items = len(products)
in_stock_count = sum(1 for p in products if p.get("last_status") == "In Stock")
out_stock_count = sum(1 for p in products if p.get("last_status") == "Out of Stock")

st.title("🧸 Figure Tracker Dashboard")

# Display big numbers at the top
m1, m2, m3 = st.columns(3)
m1.metric("Total Tracked", total_items)
m2.metric("In Stock", in_stock_count, delta="Available Now")
m3.metric("Out of Stock", out_stock_count, delta_color="inverse")

st.divider()

# --- 3. CONTROLS (Search, Filter, Sort) ---
c1, c2, c3 = st.columns([2, 1, 1])

with c1:
    search = st.text_input("🔍 Search Figures", placeholder="Type a name...")

with c2:
    filter_status = st.selectbox("Filter Status", ["All", "In Stock", "Out of Stock"])

with c3:
    sort_option = st.selectbox("Sort By", ["Price: Low to High", "Price: High to Low", "Name (A-Z)"])

# --- 4. FILTER & SORT LOGIC ---
filtered_list = []

# A. Filter First
for p in products:
    # Status Filter
    if filter_status == "In Stock" and p.get("last_status") != "In Stock": continue
    if filter_status == "Out of Stock" and p.get("last_status") != "Out of Stock": continue
    
    # Search Filter
    if search.lower() and search.lower() not in p['name'].lower(): continue
    
    filtered_list.append(p)

# B. Sort Second
if sort_option == "Price: Low to High":
    filtered_list.sort(key=lambda x: x.get("last_price", 0))
elif sort_option == "Price: High to Low":
    filtered_list.sort(key=lambda x: x.get("last_price", 0), reverse=True)
elif sort_option == "Name (A-Z)":
    filtered_list.sort(key=lambda x: x.get("name", "").lower())

# --- 5. DISPLAY GRID ---
st.subheader(f"Showing {len(filtered_list)} Items")

# Grid Layout (4 items per row)
cols = st.columns(4)

for i, p in enumerate(filtered_list):
    with cols[i % 4]:
        with st.container(border=True):
            # Image (Handle lazy loading logic visually)
            img_url = p.get("image")
            if img_url:
                # If the URL starts with //, add https:
                if img_url.startswith("//"):
                    img_url = "https:" + img_url
                st.image(img_url, use_container_width=True)
            
            # Title
            st.markdown(f"**[{p['name']}]({p['url']})**")
            
            # Status Badge
            status = p.get('last_status', 'Unknown')
            if status == "In Stock":
                st.markdown(f":green-background[In Stock]")
            else:
                st.markdown(f":red-background[Out of Stock]")
            
            # Price Display
            price = p.get('last_price', 0)
            target = p.get('target_price', 0)
            
            # Show Price (Highlight if below target)
            if price > 0 and price <= target:
                st.metric("Price", f"${price}", delta="Target Met!", delta_color="normal")
            else:
                st.metric("Price", f"${price}")

            # Price History Chart (Mini)
            if p.get("history") and len(p["history"]) > 1:
                df = pd.DataFrame(list(p["history"].items()), columns=["Date", "Price"])
                st.line_chart(df.set_index("Date"), height=100)
