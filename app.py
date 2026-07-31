from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# URL base do serviço
BASE_URL = "https://app.pobreflix2.site"

# Cabeçalhos para simular um navegador real
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': BASE_URL,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
}

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Master Scraper v6"})

def get_real_categories(session, server_id):
    """Busca as categorias reais para um servidor específico."""
    found_categories = []
    try:
        cat_page_url = f"{BASE_URL}/canais/categorias/?thema=1&server={server_id}"
        r = session.get(cat_page_url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        for a in soup.find_all('a', href=True):
            href = a['href']
            # Extrai o ID da categoria limpando a query string
            clean_href = href.split('?')[0]
            if '/canais/categorias/' in clean_href:
                category_id = clean_href.strip('/').split('/')[-1]
                if category_id.isdigit():
                    name = a.get_text(strip=True)
                    if name:
                        found_categories.append({"name": name, "url": clean_href})
    except:
        pass
    return found_categories

def fetch_page(session, url, serv_label, serv_id, category_name):
    """Extrai canais de uma página específica."""
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta', 'categorias', 'buscar']

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Captura canais (/canais/ID ou /play/ID)
            if '/canais/' in href or '/play/' in href:
                # Evita links de navegação
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

                # Normaliza a URL final do player
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
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
                    "key": f"{serv_id}-{full_url.split('?')[0]}"
                })
    except:
        pass
    return canais_da_pagina

@app.route('/canais')
def get_canais():
    try:
        session = requests.Session()
        session.headers.update(HEADERS)

        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            for serv in servidores:
                # 1. Obtém as categorias específicas para ESTE servidor
                categories = get_real_categories(session, serv['id'])

                # 2. Varredura Geral (Páginas 1 a 10)
                for page in range(1, 11):
                    url = f"{BASE_URL}/canais?page={page}&thema=1&server={serv['id']}"
                    tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], "Geral"))

                # 3. Varredura por Categorias (Páginas 1 a 3 para garantir captura total)
                for cat in categories:
                    for page in range(1, 4):
                        url_cat = f"{cat['url']}?page={page}&thema=1&server={serv['id']}"
                        tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], cat['name']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        all_results = []

        for task in tasks:
            all_results.extend(task.result())

        # Ordenação organizada para o player
        all_results.sort(key=lambda x: (x['category'], x['nome']))

        count = 0
        for canal in all_results:
            if canal['key'] not in links_vistos:
                links_vistos.add(canal['key'])
                logo = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                m3u_content += f'#EXTINF:-1{logo} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        m3u_content += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
