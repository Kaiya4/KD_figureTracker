import json
import requests
import os
import re
from datetime import datetime
from bs4 import BeautifulSoup
from fake_useragent import UserAgent

# Secrets from GitHub
WEBHOOK_URL = os.environ.get("DISCORD_WEBHOOK_URL")
DB_FILE = "products.json"

def send_discord(message):
    if not WEBHOOK_URL: return
    try:
        requests.post(WEBHOOK_URL, json={"content": message}, timeout=10)
    except:
        pass

def check_product_status(url):
    ua = UserAgent()
    headers = {
        'User-Agent': ua.random, 
        'Referer': 'https://www.goodsmileus.com/',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
    }

    try:
        res = requests.get(url, headers=headers, timeout=20)
        if res.status_code != 200: return 0.0, "Error"

        soup = BeautifulSoup(res.text, 'html.parser')

        # 1. CHECK STOCK (Search for the "Add to Cart" button)
        # If the button says "Sold Out" or is disabled, it's out of stock.
        cart_btn = soup.find("button", {"id": "button-cart"})
        status = "Unknown"

        if cart_btn:
            btn_text = cart_btn.get_text().lower()
            if "sold out" in btn_text or cart_btn.has_attr('disabled'):
                status = "Out of Stock"
            else:
                status = "In Stock"
        else:
            # Sometimes if pre-orders close, the button disappears
            status = "Out of Stock"

        # 2. CHECK PRICE
        price = 0.0
        # Try specific "current price" id first
        price_tags = [
            soup.find("span", class_="product__price--current"),
            soup.find("ul", class_="list-unstyled price").find("li").find("h2") if soup.find("ul", class_="list-unstyled price") else None,
            soup.find("span", class_="price-new")
        ]

        for tag in price_tags:
            if tag:
                text = tag.get_text().strip()
                # Remove $ and commas
                clean = re.sub(r'[^\d.]', '', text)
                if clean:
                    price = float(clean)
                    break

        return price, status
    except Exception as e:
        print(f"Error checking {url}: {e}")
        return 0.0, "Error"

def main():
    if not os.path.exists(DB_FILE):
        print("No database found.")
        return

    with open(DB_FILE, "r") as f:
        products = json.load(f)

    updated = False
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    print(f"Checking {len(products)} items...")

    for p in products:
        current_price, current_status = check_product_status(p['url'])

        if current_status == "Error": continue

        old_status = p.get('last_status', 'Unknown')
        old_price = p.get('last_price', 0.0)

        # --- LOGIC 1: RESTOCK ALERT ---
        # If it WAS "Out of Stock" and IS NOW "In Stock"
        if p.get('notify_restock') and old_status == "Out of Stock" and current_status == "In Stock":
            msg = f"🚨 **RESTOCK ALERT!**\n**{p['name']}** is back in stock!\nPrice: ${current_price}\n[Buy Now]({p['url']})"
            send_discord(msg)
            print(f"  🔔 Restock detected: {p['name']}")
            updated = True

        # --- LOGIC 2: PRICE DROP ---
        if current_price > 0 and current_price < old_price and current_price <= p['target_price']:
            msg = f"📉 **PRICE DROP!**\n**{p['name']}**\n${old_price} -> **${current_price}**\n[Link]({p['url']})"
            send_discord(msg)
            updated = True

        # --- LOGIC 3: SAVE HISTORY ---
        if current_price != old_price or current_status != old_status:
            p['last_price'] = current_price
            p['last_status'] = current_status

            if 'history' not in p: p['history'] = {}
            p['history'][timestamp] = current_price
            updated = True

    if updated:
        with open(DB_FILE, "w") as f:
            json.dump(products, f, indent=4)
        print("Database updated with changes.")
    else:
        print("No changes detected.")

if __name__ == "__main__":
    main()
