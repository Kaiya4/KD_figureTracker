import requests
from bs4 import BeautifulSoup
from fake_useragent import UserAgent
import json
import time
import re

# --- CONFIGURATION ---
TASKS = [
    {
        "name": "In Stock Items",
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=Available+Now&filter.p.product_type=Scale+Figure&filter.v.availability=1&sort_by=price-ascending",
        "pages": 4,
        "default_status": "In Stock"
    },
    {
        "name": "Out of Stock Items",
        "base_url": "https://www.goodsmileus.com/collections/scale-figures?filter.p.m.seed.status=On+Sale&filter.p.product_type=Scale+Figure&filter.v.availability=0&sort_by=price-ascending",
        "pages": 3,
        "default_status": "Out of Stock"
    }
]

def scrape_page(url, default_status):
    ua = UserAgent()
    headers = {'User-Agent': ua.random, 'Referer': 'https://www.goodsmileus.com/'}
    
    print(f"  📖 Reading: {url} ...")
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        if res.status_code != 200:
            print(f"  ❌ Error: HTTP {res.status_code}")
            return []

        soup = BeautifulSoup(res.text, 'html.parser')
        
        # --- NEW STRATEGY: TARGET <product-card> TAGS ---
        # The site uses a custom tag <product-card> for each item.
        items = soup.find_all("product-card")
        
        page_products = []
        
        for item in items:
            try:
                # 1. Link & Name
                # Look for the title link inside the product card
                title_link = item.find("a", class_="product-card__title-link")
                if not title_link: continue

                name = title_link.text.strip()
                # The href is relative (e.g. /products/...), so add the domain
                link = "https://www.goodsmileus.com" + title_link['href']
                
                # 2. Image
                # Images are inside <picture> tags. We want the <img> inside.
                img_tag = item.find("img")
                # Sometimes the src is lazy-loaded, so check both src and srcset
                if img_tag:
                    img_url = img_tag.get('src')
                    # If the src starts with //, add https:
                    if img_url and img_url.startswith("//"):
                        img_url = "https:" + img_url
                else:
                    img_url = None
                
                # 3. Price
                # Look for the specific price span
                current_price = 0.0
                price_span = item.find("span", class_="product__price--current")
                
                if price_span:
                    # Clean up: Remove '$', commas, and extra text
                    price_text = price_span.get_text().strip()
                    clean_price = re.sub(r'[^\d.]', '', price_text)
                    try:
                        current_price = float(clean_price)
                    except:
                        current_price = 0.0

                page_products.append({
                    "name": name,
                    "url": link,
                    "image": img_url,
                    "target_price": current_price,
                    "notify_restock": True,
                    "last_price": current_price,
                    "last_status": default_status,
                    "history": {}
                })
            except Exception as e:
                # Silently skip bad items to keep the script running
                continue
                
        return page_products

    except Exception as e:
        print(f"  ❌ Critical Error: {e}")
        return []

def main():
    all_data = []
    seen_urls = set()

    print("🚀 Starting 2.0 Import (New HTML Logic)...")

    for task in TASKS:
        print(f"\n📂 Processing: {task['name']}")
        
        for page_num in range(1, task['pages'] + 1):
            target_url = f"{task['base_url']}&page={page_num}"
            items = scrape_page(target_url, task['default_status'])
            
            new_count = 0
            for item in items:
                if item['url'] not in seen_urls:
                    all_data.append(item)
                    seen_urls.add(item['url'])
                    new_count += 1
            
            print(f"    Found {len(items)} items. ({new_count} new)")
            time.sleep(1) 

    # Save to JSON
    with open("products.json", "w") as f:
        json.dump(all_data, f, indent=4)
        
    print(f"\n🎉 SUCCESS! Database created with {len(all_data)} products.")

if __name__ == "__main__":
    main()