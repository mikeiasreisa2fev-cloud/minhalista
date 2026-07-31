from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)

BASE_URL = "https://app.pobreflix2.site"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': BASE_URL
}

def get_real_categories():
    found_categories = []
    try:
        cat_page_url = f"{BASE_URL}/canais/categorias/?thema=1&server=speed-1"
        r = requests.get(cat_page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/categoria/' in href:
                name = a.get_text(strip=True)
                if name and len(name) > 2:
                    full_cat_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                    full_cat_url = full_cat_url.split('?')[0]
                    found_categories.append({"name": name, "url": full_cat_url})
    except:
        pass

    if not found_categories:
        found_categories = [{"name": "Canais", "url": f"{BASE_URL}/canais"}]
    return found_categories

def scrape_channels_from_url(url, serv_id, serv_label, category_name):
    channels = []
    try:
        time.sleep(0.1)
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        
        for a in soup.find_all('a', href=True):
            href = a['href']

            if '/canais/' in href or '/play/' in href:
                if '/categoria/' in href and 'page=' not in href: continue
                if '/canais/categorias' in href: continue
                
                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or len(nome) < 2: continue
                if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'contato', 'buscar']): 
                    continue

                clean_path = href.split('?')[0].split('#')[0]
                final_url = f"{BASE_URL}{clean_path}" if clean_path.startswith('/') else clean_path
                final_url += f"?thema=1&server={serv_id}"

                channels.append({
                    "name": f"{nome} ({serv_label})",
                    "url": final_url,
                    "logo": logo,
                    "category": category_name,
                    "key": f"{serv_id}-{clean_path}"
                })
    except:
        pass
    return channels

@app.route('/')
def welcome():
    return jsonify({"status": "online", "message": "Ycine Scraper MASTER V2"})

@app.route('/canais')
def generate_m3u():
    try:
        real_cats = get_real_categories()
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        for serv in servidores:
            for p in range(1, 16):
                url = f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}"
                tasks.append((url, serv['id'], serv['label'], "Geral"))

            for cat in real_cats:
                for p in range(1, 4):
                    sep = '&' if '?' in cat['url'] else '?'
                    url = f"{cat['url']}{sep}page={p}&thema=1&server={serv['id']}"
                    tasks.append((url, serv['id'], serv['label'], cat['name']))

        all_channels = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scrape_channels_from_url, *t) for t in tasks]
            for f in futures:
                all_channels.extend(f.result())

        seen = set()
        m3u = "#EXTM3U\n"
        count = 0
        all_channels.sort(key=lambda x: (x['category'], x['name']))

        for c in all_channels:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                m3u += f'#EXTINF:-1{logo} group-title="{c["category"]}",{c["name"]}\n{c["url"]}\n'
                count += 1

        m3u += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
