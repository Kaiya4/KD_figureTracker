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

# The scraper scans these pages to update your database
TASKS = [
    {
        "name": "In Stock Scan",
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=Available+Now&filter.p.product_type=Scale+Figure&filter.v.availability=1&sort_by=price-ascending",
        "pages": 4
    },
    {
        "name": "Out of Stock Scan",
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=On+Sale&filter.p.product_type=Scale+Figure&filter.v.availability=0&sort_by=price-ascending",
        "pages": 3
    }
]

def send_discord(message):
    if not WEBHOOK_URL: return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
        time.sleep(1)
    except:
        pass

def scrape_collection_page(url):
    """Scrapes a collection page looking for <product-card> tags"""
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random, 
        'Referer': 'https://www.goodsmileus.com/',
        'Accept-Language': 'en-US,en;q=0.9'
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200: 
            print(f"❌ Error loading {url}")
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        items = soup.find_all("product-card")
        
        found_items = []
        
        for item in items:
            try:
                # 1. Link & Name
                title_link = item.find("a", class_="product-card__title-link")
                if not title_link: continue
                
                # Ensure full URL
                raw_link = title_link['href']
                link = "https://www.goodsmileus.com" + raw_link if not raw_link.startswith("http") else raw_link
                name = title_link.text.strip()
                
                # 2. Price
                price_span = item.find("span", class_="product__price--current")
                current_price = 0.0
                if price_span:
                    clean_price = re.sub(r'[^\d.]', '', price_span.get_text().strip())
                    current_price = float(clean_price) if clean_price else 0.0

                # 3. CRITICAL FIX: Check Stock Status via Button
                # We look for the 'Quick Add' button inside the card
                status = "In Stock"
                button = item.find("button", class_="product-card__quickadd-atc")
                
                if button:
                    btn_text = button.get_text().strip().lower()
                    # Check if button is disabled OR text says "Sold Out"
                    if button.has_attr("disabled") or "sold out" in btn_text:
                        status = "Out of Stock"
                else:
                    # If no buy button exists at all, assume unavailable
                    status = "Out of Stock"

                found_items.append({
                    "url": link,
                    "name": name,
                    "price": current_price,
                    "status": status
                })
            except Exception as e:
                print(f"Skipping item error: {e}")
                continue
                
        return found_items
    except Exception as e:
        print(f"Critical Page Error: {e}")
        return []

def main():
    if not os.path.exists(DB_FILE):
        print("No database found.")
        return

    # 1. Load Database
    with open(DB_FILE, "r") as f:
        products = json.load(f)
    
    # Map for quick lookup
    product_map = {p['url']: p for p in products}
    
    changes_detected = False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print("🚀 Starting Collection Scan...")

    # 2. Scan all Collection Pages
    for task in TASKS:
        print(f"📂 Task: {task['name']}")
        for page_num in range(1, task['pages'] + 1):
            target_url = f"{task['base_url']}&page={page_num}"
            
            scraped_items = scrape_collection_page(target_url)
            print(f"   - Page {page_num}: Found {len(scraped_items)} items")
            
            # 3. Update Database
            for item in scraped_items:
                url = item['url']
                
                # Only update if we track this item
                if url in product_map:
                    p = product_map[url]
                    
                    old_price = p.get('last_price', 0.0)
                    old_status = p.get('last_status', 'Unknown')
                    new_price = item['price']
                    new_status = item['status']
                    
                    # --- ALERT LOGIC ---
                    
                    # A. RESTOCK ALERT (Was Out -> Now In)
                    if p.get('notify_restock') and old_status == "Out of Stock" and new_status == "In Stock":
                        msg = f"🚨 **RESTOCK ALERT!**\n**{p['name']}** is back in stock!\nPrice: ${new_price}\n[Buy Now]({url})"
                        send_discord(msg)
                        print(f"  🔔 Restock: {p['name']}")
                    
                    # B. 5% PRICE DROP ALERT
                    if old_price > 0 and new_price > 0:
                        diff = abs(new_price - old_price)
                        percent_change = diff / old_price
                        
                        # Logic: Only alert if price DROPPED by 5% or more
                        if percent_change >= 0.05 and new_price < old_price:
                            msg = f"📉 **Price Drop Alert!**\n**{p['name']}** dropped {int(percent_change*100)}%\n${old_price} -> **${new_price}**\n[Link]({url})"
                            send_discord(msg)
                            print(f"  📉 Price Drop: {p['name']}")

                    # --- SAVE DATA ---
                    if old_price != new_price or old_status != new_status:
                        p['last_price'] = new_price
                        p['last_status'] = new_status
                        
                        if 'history' not in p: p['history'] = {}
                        p['history'][timestamp] = new_price
                        
                        changes_detected = True

            time.sleep(2) # Be polite

    # 4. Save Changes
    if changes_detected:
        # Convert map back to list
        updated_list = list(product_map.values())
        with open(DB_FILE, "w") as f:
            json.dump(updated_list, f, indent=4)
        print("✅ Database updated successfully.")
    else:
        print("💤 No changes found.")

if __name__ == "__main__":
    main()
