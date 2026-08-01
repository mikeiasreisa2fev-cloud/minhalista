from flask import Flask, jsonify, Response, redirect, request
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs

app = Flask(__name__)

# Configurações globais
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Referer': 'https://app.pobreflix2.site/'
}

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Master - Versão 19 Final Estável"})

# ROTA INTELIGENTE PARA REPRODUÇÃO
@app.route('/stream')
def get_stream():
    url_base_canal = request.args.get('url')
    if not url_base_canal:
        return "URL ausente", 400

    try:
        # 1. TENTATIVA POR LÓGICA PREDITIVA (Rápida)
        parsed = urlparse(url_base_canal)
        path_parts = parsed.path.strip('/').split('/')
        qs = parse_qs(parsed.query)

        server_id = qs.get('server', [''])[0]
        channel_id = path_parts[-1] if path_parts else ''

        if server_id and channel_id.isdigit():
            link_direto = f"https://speed.megafilmeshd9.com/midia/{server_id}/{channel_id}.m3u8"
            return redirect(link_direto)

        # 2. FALLBACK POR SCRAPER
        r = requests.get(url_base_canal, headers=HEADERS, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        link_final = None
        play_div = soup.find(id='iptv-play-button')
        if play_div and play_div.get('data-url'):
            link_final = play_div['data-url']

        if not link_final:
            botao = soup.find('a', class_='iptv-player-gratis')
            if botao and botao.get('href'):
                link_final = botao['href']

        if link_final:
            if link_final.startswith('/'):
                link_final = f"https://app.pobreflix2.site{link_final}"
            return redirect(link_final)

        return "Não foi possível extrair o link deste canal", 404
    except Exception as e:
        return f"Erro no servidor: {str(e)}", 500

def fetch_page(session, url, serv_label, serv_id, host, category_name="Geral"):
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        items = soup.find_all('a', class_='iptv-cat-item')
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta']

        for a in items:
            href = a['href']
            h4 = a.find('h4')
            nome = h4.get_text(strip=True) if h4 else ""
            logo = ""
            img = a.find('img')
            if img: logo = img.get('src') or img.get('data-src') or ""

            if not nome or any(menu == nome.lower() for menu in menu_items):
                continue

            full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"
            if 'server=' not in full_url:
                sep = '&' if '?' in full_url else '?'
                full_url = f"{full_url}{sep}server={serv_id}&thema=1"

            link_proxy = f"https://{host}/stream?url={full_url}"

            canais_da_pagina.append({
                "nome": f"{nome} ({serv_label})",
                "url": link_proxy,
                "logo": logo,
                "category": category_name,
                "chave": f"{serv_id}-{href.split('?')[0]}"
            })
    except:
        pass
    return canais_da_pagina

def get_real_categories(session, server_id):
    found_categories = []
    try:
        url = f"https://app.pobreflix2.site/canais/categorias/?thema=1&server={server_id}"
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/canais/categorias/' in a['href']:
                name = a.get_text(strip=True)
                href = a['href']
                # Correção da URL absoluta para a categoria
                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"
                if name: found_categories.append({"name": name, "url": full_url})
    except:
        pass
    return found_categories

@app.route('/canais')
def get_canais():
    try:
        current_host = request.host
        session = requests.Session()
        session.headers.update(HEADERS)

        servidores = [
            {"id": "speed-1", "label": "S1", "max_p": 59},
            {"id": "speed-2", "label": "S2", "max_p": 67},
            {"id": "speed-3", "label": "S3", "max_p": 44}
        ]

        all_tasks = []
        # Reduzi workers para 15 para evitar bloqueios por excesso de requisições
        with ThreadPoolExecutor(max_workers=15) as executor:
            for serv in servidores:
                # Páginas Gerais
                for page in range(1, serv['max_p'] + 1):
                    url = f"https://app.pobreflix2.site/canais/?thema=1&server={serv['id']}&pagina={page}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], current_host, "Geral"))

                # Páginas de Categorias
                cats = get_real_categories(session, serv['id'])
                for cat in cats:
                    base_cat = cat['url'].split('?')[0]
                    url_cat = f"{base_cat}?thema=1&server={serv['id']}&pagina=1"
                    all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], current_host, cat['name']))

        results = []
        for task in all_tasks:
            try:
                res = task.result()
                if res: results.extend(res)
            except: continue

        results.sort(key=lambda x: (x['category'], x['nome']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        count = 0
        for canal in results:
            if canal['chave'] not in links_vistos:
                links_vistos.add(canal['chave'])
                logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                m3u_content += f'#EXTINF:-1{logo_attr} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        m3u_content += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u_content, mimetype='text/plain')
    except Exception as e:
        return f"Erro fatal: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
