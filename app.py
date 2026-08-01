from flask import Flask, jsonify, Response, redirect, request
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse, parse_qs, quote

app = Flask(__name__)

# Configurações de Identidade Real
REAL_UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36'
BASE_URL = 'https://app.pobreflix2.site'

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Master - Versão 34 XCIPTV Special"})

# ROTA DE REPRODUÇÃO FORMATADA PARA XCIPTV (.m3u8 no final)
@app.route('/stream/<server_id>/<channel_id>.m3u8')
def get_stream(server_id, channel_id):
    try:
        # Monta a URL de referência para o servidor aceitar a conexão
        url_referencia = f"{BASE_URL}/canais/{channel_id}?thema=1&server={server_id}"
        target_m3u8 = f"https://speed.megafilmeshd9.com/midia/{server_id}/{channel_id}.m3u8"

        headers = {
            'User-Agent': REAL_UA,
            'Referer': url_referencia,
            'Origin': BASE_URL
        }

        # O servidor Railway baixa a playlist e entrega "limpa" para o XCIPTV
        r = requests.get(target_m3u8, headers=headers, timeout=12)
        if r.status_code != 200:
            return f"Erro no sinal original: {r.status_code}", 404

        playlist_lines = r.text.splitlines()
        new_playlist = []
        video_base_url = target_m3u8.rsplit('/', 1)[0] + "/"

        for line in playlist_lines:
            if line and not line.startswith('#'):
                if not line.startswith('http'):
                    new_playlist.append(video_base_url + line)
                else:
                    new_playlist.append(line)
            else:
                new_playlist.append(line)

        # Resposta com Mimetype compatível com XCIPTV e CORS liberado
        response = Response('\n'.join(new_playlist), mimetype='application/x-mpegURL')
        response.headers.add('Access-Control-Allow-Origin', '*')
        return response

    except Exception as e:
        return f"Erro fatal: {str(e)}", 500

def fetch_page(session, url, serv_label, serv_id, host, category_name="Geral"):
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        items = soup.find_all('a', class_='iptv-cat-item')

        for a in items:
            href = a['href']
            h4 = a.find('h4')
            nome = h4.get_text(strip=True) if h4 else ""
            logo = ""
            img = a.find('img')
            if img: logo = img.get('src') or img.get('data-src') or ""

            if not nome or any(menu in nome.lower() for menu in ['sair', 'minha conta', 'editar']):
                continue

            canal_id = href.split('?')[0].rstrip('/').split('/')[-1]

            # NOVO FORMATO DE LINK PARA XCIPTV: /stream/servidor/id.m3u8
            link_proxy = f"https://{host}/stream/{serv_id}/{canal_id}.m3u8"

            # LÓGICA DE ORGANIZAÇÃO MANUAL
            final_category = category_name
            nome_up = nome.upper()
            infantil_keywords = ["ADULT SWIM", "CARTOON", "KIDS", "GLOOB", "NICK", "RATIM", "TOONCAST", "ZOOMOO", "PREDIO AZUL", "RETRÔ"]

            if serv_id in ["speed-1", "speed-2", "speed-3"]:
                if any(k in nome_up for k in infantil_keywords):
                    final_category = f"{serv_label} - Infantil"
                elif serv_id == "speed-2" and "HBO MAX" in nome_up:
                    final_category = f"{serv_label} - HBO Max"

            canais_da_pagina.append({
                "nome": nome,
                "url": link_proxy,
                "logo": logo,
                "category": final_category,
                "chave": f"{serv_id}-{canal_id}"
            })
    except:
        pass
    return canais_da_pagina

def get_real_categories(session, server_id):
    found_categories = []
    try:
        url = f"{BASE_URL}/canais/categorias/?thema=1&server={server_id}"
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/canais/categorias/' in a['href']:
                name = a.get_text(strip=True)
                href = a['href']
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                if name: found_categories.append({"name": name, "url": full_url})
    except:
        pass
    return found_categories

@app.route('/canais')
def get_canais():
    try:
        current_host = request.host
        session = requests.Session()
        session.headers.update({'User-Agent': REAL_UA})

        servidores = [
            {"id": "speed-1", "label": "S1", "max_p": 59},
            {"id": "speed-2", "label": "S2", "max_p": 67},
            {"id": "speed-3", "label": "S3", "max_p": 44}
        ]

        all_tasks = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            for serv in servidores:
                cats = get_real_categories(session, serv['id'])
                for cat in cats:
                    base_cat = cat['url'].split('?')[0]
                    url_cat = f"{base_cat}?thema=1&server={serv['id']}&pagina=1"
                    all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], current_host, f"{serv['label']} - {cat['name']}"))

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
