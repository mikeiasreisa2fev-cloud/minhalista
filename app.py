from flask import Flask, jsonify, Response, redirect, request
import os
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs, quote

app = Flask(__name__)

# Configurações de Identidade Real
REAL_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
BASE_URL = 'https://app.pobreflix2.site'

# VARIÁVEIS DE CACHE
cache_data = {"m3u": "", "timestamp": 0}
CACHE_TIMEOUT = 3600

# --- CONFIGURAÇÃO DE ALTA PERFORMANCE DE REDE ---
session_speed = requests.Session()
retry_strategy = Retry(total=3, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
# Aumenta o pool para 100 conexões abertas simultâneas para sugar o máximo de banda
adapter = HTTPAdapter(pool_connections=100, pool_maxsize=100, max_retries=retry_strategy)
session_speed.mount("https://", adapter)
session_speed.mount("http://", adapter)
session_speed.headers.update({'User-Agent': REAL_UA, 'Connection': 'keep-alive'})

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Master - Versão 39 Ultra Bandwidth"})

# ROTA DE REPRODUÇÃO - TURBO PROXY
@app.route('/stream/<server_id>/<channel_id>.m3u8')
def get_stream(server_id, channel_id):
    try:
        url_referencia = f"{BASE_URL}/canais/{channel_id}?thema=1&server={server_id}"
        target_m3u8 = f"https://speed.megafilmeshd9.com/midia/{server_id}/{channel_id}.m3u8"

        # Requisição usando o Pool de Alta Velocidade
        r = session_speed.get(target_m3u8, headers={'Referer': url_referencia, 'Origin': BASE_URL}, timeout=5)

        if r.status_code != 200:
            return f"Erro: {r.status_code}", 404

        # Processamento em bloco de memória para ser instantâneo
        video_base_url = target_m3u8.rsplit('/', 1)[0] + "/"
        lines = r.text.splitlines()

        # Otimização: Reescrita de links em uma única passada
        new_playlist = [
            (video_base_url + line if (line and not line.startswith(('#', 'http'))) else line)
            for line in lines
        ]

        response = Response('\n'.join(new_playlist), mimetype='application/x-mpegURL')
        # Headers para forçar o player a ler o máximo de dados possível
        response.headers.add('Access-Control-Allow-Origin', '*')
        response.headers.add('Cache-Control', 'no-cache, no-store, must-revalidate')
        return response
    except Exception as e:
        return f"Erro: {str(e)}", 500

def fetch_page(session, url, serv_label, serv_id, host, category_name="Geral"):
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200: return []
        soup = BeautifulSoup(r.text, 'html.parser')
        items = soup.find_all('a', class_='iptv-cat-item')
        infantil_keywords = ["ADULT SWIM", "CARTOON", "KIDS", "GLOOB", "NICK", "RATIM", "TOONCAST", "ZOOMOO", "PREDIO AZUL", "RETRÔ"]

        for a in items:
            href = a['href']
            h4 = a.find('h4')
            nome = h4.get_text(strip=True) if h4 else ""
            img = a.find('img')
            logo = img.get('src') or img.get('data-src') or "" if img else ""

            if not nome or any(m in nome.lower() for m in ['sair', 'minha conta']): continue

            canal_id = href.split('?')[0].rstrip('/').split('/')[-1]
            link_proxy = f"https://{host}/stream/{serv_id}/{canal_id}.m3u8"

            final_category = category_name
            nome_up = nome.upper()
            if any(k in nome_up for k in infantil_keywords): final_category = f"{serv_label} - Infantil"
            elif "HBO" in nome_up or "MAX " in nome_up: final_category = f"{serv_label} - HBO Max"

            canais_da_pagina.append({
                "nome": nome, "url": link_proxy, "logo": logo,
                "category": final_category, "chave": f"{serv_id}-{canal_id}"
            })
    except: pass
    return canais_da_pagina

def get_real_categories(session, server_id):
    found = []
    try:
        r = session.get(f"{BASE_URL}/canais/categorias/?thema=1&server={server_id}", timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/canais/categorias/' in a['href']:
                name = a.get_text(strip=True)
                full_url = a['href'] if a['href'].startswith('http') else f"{BASE_URL}{a['href']}"
                if name: found.append({"name": name, "url": full_url})
    except: pass
    return found

@app.route('/canais')
def get_canais():
    global cache_data
    if cache_data["m3u"] and (time.time() - cache_data["timestamp"] < CACHE_TIMEOUT):
        return Response(cache_data["m3u"], mimetype='text/plain')

    try:
        current_host = request.host
        session = requests.Session()
        session.headers.update({'User-Agent': REAL_UA})
        servidores = [{"id": "speed-1", "label": "S1", "max_p": 59}, {"id": "speed-2", "label": "S2", "max_p": 67}, {"id": "speed-3", "label": "S3", "max_p": 44}]

        all_tasks = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            for serv in servidores:
                # Busca Categorias
                for cat in get_real_categories(session, serv['id']):
                    url_cat = f"{cat['url'].split('?')[0]}?thema=1&server={serv['id']}&pagina=1"
                    all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], current_host, f"{serv['label']} - {cat['name']}"))
                # Busca Geral
                for page in range(1, serv['max_p'] + 1):
                    url = f"{BASE_URL}/canais/?thema=1&server={serv['id']}&pagina={page}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], current_host, f"{serv['label']} - Geral"))

        results = []
        for task in all_tasks:
            try:
                res = task.result()
                if res: results.extend(res)
            except: continue

        results.sort(key=lambda x: (x['category'].replace('Geral', 'ZZZ'), x['nome']))
        vistos = set()
        m3u = "#EXTM3U\n"
        for c in results:
            if c['chave'] not in vistos:
                vistos.add(c['chave'])
                m3u += f'#EXTINF:-1 tvg-logo="{c["logo"]}" group-title="{c["category"]}",{c["nome"]}\n{c["url"]}\n'

        cache_data["m3u"] = m3u
        cache_data["timestamp"] = time.time()
        return Response(m3u, mimetype='text/plain')
    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
