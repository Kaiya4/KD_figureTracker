import json
import requests
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# GitHub Secrets will fill this in automatically later
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DB_FILE = "products.json"

def send_discord(message):
    if not WEBHOOK_URL: return
    requests.post(WEBHOOK_URL, json={"content": message})

def check_goodsmile(url):
    ua = UserAgent()
    headers = {'User-Agent': ua.random, 'Referer': 'https://www.google.com/'}
    
    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code != 200: return 0, "Error"
        
        soup = BeautifulSoup(res.text, 'html.parser')
        
        # 1. CHECK STOCK (Look for 'Cart' button text)
        cart_btn = soup.find("button", {"id": "button-cart"})
        status = "In Stock"
        
        if cart_btn:
            btn_text = cart_btn.get_text().lower()
            if "sold out" in btn_text:
                status = "Out of Stock"
        else:
            status = "Unknown"

        # 2. CHECK PRICE
        price = 0.0
        price_div = soup.find("div", class_="product-price")
        if not price_div: price_div = soup.find("span", class_="price")
        
        if price_div:
            clean_text = re.sub(r'[^\d.]', '', price_div.get_text())
            if clean_text:
                price = float(clean_text)
                
        return price, status
    except:
        return 0, "Error"

def main():
    # Load the database created by your importer
    with open(DB_FILE, "r") as f:
        products = json.load(f)
    
    updated = False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"Checking {len(products)} products...")

    for p in products:
        price, status = check_goodsmile(p['url'])
        
        if status == "Error": continue

        # Init history if missing
        if "history" not in p: p["history"] = {}

        # LOGIC 1: RESTOCK ALERT
        # If it was "Out of Stock" before, and now is "In Stock"
        if p.get('notify_restock') and p.get('last_status') == "Out of Stock" and status == "In Stock":
            msg = f"🚨 **RESTOCK ALERT!**\n**{p['name']}** is back in stock!\nPrice: ${price}\n[Buy Now]({p['url']})"
            send_discord(msg)
            updated = True

        # LOGIC 2: PRICE DROP ALERT
        if price > 0 and price < p.get('last_price', 999999) and price <= p['target_price']:
            msg = f"📉 **PRICE DROP!**\n**{p['name']}** dropped to **${price}**!\n[Link]({p['url']})"
            send_discord(msg)
            updated = True

        # LOGIC 3: UPDATE HISTORY (Only if changed to save space)
        if price != p.get('last_price') or status != p.get('last_status'):
            p['last_price'] = price
            p['last_status'] = status
            p['history'][timestamp] = price
            updated = True

    if updated:
        with open(DB_FILE, "w") as f:
            json.dump(products, f, indent=4)
        print("Database updated.")
    else:
        print("No changes found.")

if __name__ == "__main__":
    main()