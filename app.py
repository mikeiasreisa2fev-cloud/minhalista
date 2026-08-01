from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Master - Versão 12 Turbo"})

def fetch_page(session, url, serv_label, serv_id, category_name="Geral"):
    """Extrai canais de uma página específica de forma detalhada."""
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=25)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        # Busca a classe de item de canal confirmada no HTML
        items = soup.find_all('a', class_='iptv-cat-item')

        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta']

        for a in items:
            href = a['href']
            # Captura o nome no <h4> conforme estrutura do site
            h4 = a.find('h4')
            nome = h4.get_text(strip=True) if h4 else ""

            logo = ""
            img = a.find('img')
            if img:
                # Pega o logotipo (suporta lazy load)
                logo = img.get('src') or img.get('data-src') or ""
                if not nome:
                    nome = img.get('alt') or img.get('title') or ""

            # Filtra itens vazios ou de menu
            if not nome or any(menu == nome.lower() for menu in menu_items):
                continue

            # Monta a URL completa do player
            full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"

            # Injeta parâmetros de servidor para garantir o player correto
            if 'server=' not in full_url:
                sep = '&' if '?' in full_url else '?'
                full_url = f"{full_url}{sep}server={serv_id}&thema=1"

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
    """Mapeia as pastas de categorias para varredura completa."""
    found_categories = []
    try:
        url = f"https://app.pobreflix2.site/canais/categorias/?thema=1&server={server_id}"
        r = session.get(url, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            if '/canais/categorias/' in a['href']:
                href_clean = a['href'].split('?')[0].rstrip('/')
                cat_id = href_clean.split('/')[-1]
                if cat_id.isdigit():
                    name = a.get_text(strip=True)
                    if name:
                        found_categories.append({"name": name, "url": a['href']})
    except:
        pass
    return found_categories

@app.route('/canais')
def get_canais():
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/'
        }

        session = requests.Session()
        session.headers.update(headers)

        # Configuração baseada no número real de páginas por servidor
        servidores = [
            {"id": "speed-1", "label": "S1", "max_p": 59},
            {"id": "speed-2", "label": "S2", "max_p": 67},
            {"id": "speed-3", "label": "S3", "max_p": 44}
        ]

        all_tasks = []
        # Usa 25 trabalhadores para processar as 170+ páginas em paralelo
        with ThreadPoolExecutor(max_workers=25) as executor:
            for serv in servidores:
                # 1. Varredura de todas as páginas da lista GERAL
                for page in range(1, serv['max_p'] + 1):
                    url = f"https://app.pobreflix2.site/canais/?thema=1&server={serv['id']}&pagina={page}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], "Geral"))

                # 2. Varredura das pastas de Categorias (Página 1)
                cats = get_real_categories(session, serv['id'])
                for cat in cats:
                    url_cat = f"{cat['url']}&server={serv['id']}&pagina=1"
                    all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], cat['name']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        count = 0
        results = []

        # Coleta os resultados das threads
        for task in all_tasks:
            try:
                results.extend(task.result())
            except:
                continue

        # Ordenação por Categoria e Nome para o player
        results.sort(key=lambda x: (x['category'], x['nome']))

        for canal in results:
            if canal['chave'] not in links_vistos:
                links_vistos.add(canal['chave'])
                logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                # Formato M3U compatível com IPTV Smarters, VLC, etc.
                m3u_content += f'#EXTINF:-1{logo_attr} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        m3u_content += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro fatal: {str(e)}", 500

if __name__ == "__main__":
    # O Railway fornece a porta dinamicamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
