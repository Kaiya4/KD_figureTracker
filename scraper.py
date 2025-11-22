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

# Re-using the exact same tasks that worked for your importer
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

def send_discord(message):
    if not WEBHOOK_URL: return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        time.sleep(1) # Anti-spam pause
    except:
        pass

def scrape_collection_page(url, default_status):
    """Scrapes a collection page looking for <product-card> tags"""
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
                # 1. Link (Used as ID)
                title_link = item.find("a", class_="product-card__title-link")
                if not title_link: continue
                link = "https://www.goodsmileus.com" + title_link['href']
                
                # 2. Price
                price_span = item.find("span", class_="product__price--current")
                current_price = 0.0
                if price_span:
                    clean_price = re.sub(r'[^\d.]', '', price_span.get_text().strip())
                    current_price = float(clean_price) if clean_price else 0.0

                found_items.append({
                    "url": link,
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
    
    # Create a lookup map for speed: { "https://url.com": product_object }
    product_map = {p['url']: p for p in products}
    
    changes_detected = False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("🚀 Starting Collection Scan...")

    # 2. Scan all Collection Pages
    for task in TASKS:
        for page_num in range(1, task['pages'] + 1):
            target_url = f"{task['base_url']}&page={page_num}"
            print(f"  Reading: {task['status_label']} Page {page_num}...")
            
            scraped_items = scrape_collection_page(target_url, task['status_label'])
            
            # 3. Update Database Items
            for item in scraped_items:
                url = item['url']
                
                # Only update if we are already tracking this item
                if url in product_map:
                    p = product_map[url]
                    
                    old_price = p.get('last_price', 0.0)
                    old_status = p.get('last_status', 'Unknown')
                    new_price = item['price']
                    new_status = item['status']
                    
                    # --- ALERT LOGIC ---
                    
                    # A. RESTOCK ALERT (Was "Out of Stock", Now "In Stock")
                    if old_status == "Out of Stock" and new_status == "In Stock":
                        msg = f"🚨 **RESTOCK ALERT!**\n**{p['name']}** is back in stock!\nPrice: ${new_price}\n[Buy Now]({url})"
                        send_discord(msg)
                    
                    # B. 5% PRICE CHANGE ALERT
                    # Calculate percentage difference if old_price is valid
                    if old_price > 0:
                        diff = abs(new_price - old_price)
                        percent_change = diff / old_price
                        
                        if percent_change >= 0.05: # 0.05 = 5%
                            direction = "dropped" if new_price < old_price else "rose"
                            emoji = "📉" if new_price < old_price else "📈"
                            msg = f"{emoji} **Price Alert!**\n**{p['name']}** {direction} by {int(percent_change*100)}%\n${old_price} -> **${new_price}**\n[Link]({url})"
                            send_discord(msg)

                    # --- SAVE DATA ---
                    # Update if anything changed
                    if old_price != new_price or old_status != new_status:
                        p['last_price'] = new_price
                        p['last_status'] = new_status
                        
                        if 'history' not in p: p['history'] = {}
                        p['history'][timestamp] = new_price
                        
                        changes_detected = True

            time.sleep(2) # Be polite to the server

    # 4. Save Changes
    if changes_detected:
        # Convert map values back to list
        updated_list = list(product_map.values())
        with open(DB_FILE, "w") as f:
            json.dump(updated_list, f, indent=4)
        print("✅ Database updated.")
    else:
        print("💤 No changes found.")

if __name__ == "__main__":
    main()
