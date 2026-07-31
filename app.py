from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Ativa - Versão 8 Blindada"})

def fetch_page(session, url, serv_label, serv_id, category_name="Geral"):
    canais_da_pagina = []
    try:
        # Lógica de re-tentativa (Retry) para evitar o erro 0
        for _ in range(2):
            try:
                r = session.get(url, timeout=25)
                if r.status_code == 200:
                    break
                time.sleep(1)
            except:
                time.sleep(1)
                continue
        else:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta']

        for a in soup.find_all('a', href=True):
            href = a['href']

            if '/canais/' in href or '/play/' in href:
                if '/canais/categorias' in href or 'page=' in href:
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or any(menu == nome.lower() for menu in menu_items):
                    continue

                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"

                if 'server=' not in full_url:
                    sep = '&' if '?' in full_url else '?'
                    full_url = f"{full_url}{sep}server={serv_id}&thema=1"
                elif 'thema=' not in full_url:
                    full_url = f"{full_url}&thema=1"

                canais_da_pagina.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": full_url,
                    "logo": logo,
                    "category": category_name,
                    "chave": f"{serv_id}-{href.split('?')[0]}"
                })
    except:
        pass
    return canais_da_pagina

def get_real_categories(session, server_id):
    """Mapeia as categorias usando a estrutura do HTML que você enviou."""
    found_categories = []
    try:
        url = f"https://app.pobreflix2.site/canais/categorias/?thema=1&server={server_id}"
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/canais/categorias/' in a['href']:
                cat_id = a['href'].strip('/').split('/')[-1].split('?')[0]
                if cat_id.isdigit():
                    name = a.get_text(strip=True)
                    if name:
                        found_categories.append({"name": name, "url": a['href'].split('?')[0]})
    except:
        pass
    return found_categories

@app.route('/canais')
def get_canais():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        }

        session = requests.Session()
        session.headers.update(headers)

        servidores = [
            {"id": "speed-1", "label": "S1", "pages": 25},
            {"id": "speed-2", "label": "S2", "pages": 30},
            {"id": "speed-3", "label": "S3", "pages": 20}
        ]

        all_tasks = []
        # Usamos 15 workers para não sobrecarregar e ser banido
        with ThreadPoolExecutor(max_workers=15) as executor:
            for serv in servidores:
                # 1. Varredura Geral
                for page in range(1, serv['pages'] + 1):
                    url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], "Geral"))

                # 2. Varredura por Categorias
                cats = get_real_categories(session, serv['id'])
                for cat in cats:
                    url_cat = f"https://app.pobreflix2.site{cat['url']}?thema=1&server={serv['id']}"
                    all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], cat['name']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        count = 0
        results = []

        for task in all_tasks:
            try:
                results.extend(task.result())
            except:
                continue

        # Ordena para ficar organizado no player
        results.sort(key=lambda x: (x['category'], x['nome']))

        for canal in results:
            if canal['chave'] not in links_vistos:
                links_vistos.add(canal['chave'])
                logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                m3u_content += f'#EXTINF:-1{logo_attr} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        m3u_content += f"\n# TOTAL DE CANAIS CAPTURADOS: {count}\n"
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro fatal: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
