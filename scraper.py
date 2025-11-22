import json
import requests
import os
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# --- CONFIGURATION ---
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DB_FILE = "products.json"

TASKS = [
    {
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=Available+Now&filter.p.product_type=Scale+Figure&filter.v.availability=1&sort_by=price-ascending",
        "pages": 4,
        "status_label": "In Stock"
    },
    {
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=On+Sale&filter.p.product_type=Scale+Figure&filter.v.availability=0&sort_by=price-ascending",
        "pages": 3,
        "status_label": "Out of Stock"
    }
]

def clean_url(url):
    """Removes query parameters to ensure URL matching works"""
    if not url: return ""
    return url.split('?')[0]

def send_discord(message):
    if not WEBHOOK_URL: return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        time.sleep(1)
    except:
        pass

def scrape_collection_page(url, default_status):
    ua = UserAgent()
    headers = {'User-Agent': ua.random, 'Referer': 'https://www.goodsmileus.com/'}
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: return []

        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all("product-card")
        
        found_items = []
        
        for item in items:
            try:
                # 1. Link
                title_link = item.find("a", class_="product-card__title-link")
                if not title_link: continue
                
                raw_link = title_link['href']
                full_link = "https://www.goodsmileus.com" + raw_link if not raw_link.startswith("http") else raw_link
                
                # 2. Price
                price_span = item.find("span", class_="product__price--current")
                current_price = 0.0
                if price_span:
                    clean_price = re.sub(r'[^\d.]', '', price_span.get_text().strip())
                    current_price = float(clean_price) if clean_price else 0.0

                found_items.append({
                    "url": clean_url(full_link), # CLEAN THE URL
                    "price": current_price,
                    "status": default_status
                })
            except:
                continue
                
        return found_items
    except:
        return []

def main():
    if not os.path.exists(DB_FILE):
        print("No database found.")
        return

    # 1. Load Database
    with open(DB_FILE, "r") as f:
        products = json.load(f)
    
    # Create a smart map using CLEAN URLs as keys
    # This ensures matches even if the ?pos=... changes
    product_map = {clean_url(p['url']): p for p in products}
    
    changes_made = False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("🚀 Starting Collection Scan...")

    for task in TASKS:
        for page_num in range(1, task['pages'] + 1):
            target_url = f"{task['base_url']}&page={page_num}"
            print(f"  Reading: {task['status_label']} Page {page_num}...")
            
            scraped_items = scrape_collection_page(target_url, task['status_label'])
            
            for item in scraped_items:
                # Look up using the CLEAN URL
                url_key = item['url']
                
                if url_key in product_map:
                    p = product_map[url_key]
                    
                    old_price = p.get('last_price', 0.0)
                    old_status = p.get('last_status', 'Unknown')
                    new_price = item['price']
                    new_status = item['status']
                    
                    # --- ALERT LOGIC (Discord) ---
                    if old_status == "Out of Stock" and new_status == "In Stock":
                        msg = f"🚨 **RESTOCK ALERT!**\n**{p['name']}** is back in stock!\nPrice: ${new_price}\n[Buy Now]({p['url']})"
                        send_discord(msg)
                    
                    if old_price > 0 and new_price > 0:
                        diff = abs(new_price - old_price)
                        percent_change = diff / old_price
                        if percent_change >= 0.05 and new_price < old_price:
                            msg = f"📉 **Price Drop!**\n**{p['name']}**\n${old_price} -> **${new_price}**\n[Link]({p['url']})"
                            send_discord(msg)

                    # --- UPDATE DATA ---
                    p['last_price'] = new_price
                    p['last_status'] = new_status
                    
                    # --- HISTORY LOGIC (Always Save) ---
                    if 'history' not in p: p['history'] = {}
                    p['history'][timestamp] = new_price
                    
                    # Mark as changed so we force a git commit
                    changes_made = True

            time.sleep(1) 

    # 4. Save Changes
    if changes_made:
        with open(DB_FILE, "w") as f:
            json.dump(products, f, indent=4)
        print("✅ Database updated.")
    else:
        print("💤 No items matched (Check URL logic).")

if __name__ == "__main__":
    main()
