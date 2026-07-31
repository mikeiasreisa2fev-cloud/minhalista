from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Ativa - Varredura Maxima v5"})

def fetch_page(session, url, serv_label, serv_id, category_name="Geral"):
    """Extrai os canais de uma página específica de forma detalhada."""
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=20)
        if r.status_code != 200:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        # Lista de palavras para ignorar botões de menu e navegação
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta', 'categorias']

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Filtro de canais: ignora menus e páginas de categorias
            if '/canais/' in href or '/play/' in href:
                if '/categoria/' in href or 'page=' in href or '/categorias' in href:
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    # Captura o logotipo e o nome (via alt/title se o texto estiver vazio)
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or any(menu == nome.lower() for menu in menu_items):
                    continue

                # Garante que a URL seja completa para o player
                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"

                # Força os parâmetros de servidor e tema na URL final
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
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/'
        }

        session = requests.Session()
        session.headers.update(headers)

        # 1. BUSCA CATEGORIAS (Mapeamento automático das pastas de canais)
        categorias = []
        try:
            r_cat = session.get("https://app.pobreflix2.site/canais/categorias/?thema=1&server=speed-1", timeout=15)
            soup_cat = BeautifulSoup(r_cat.text, 'html.parser')
            for a in soup_cat.find_all('a', href=True):
                if '/categoria/' in a['href']:
                    name = a.get_text(strip=True)
                    path = a['href'].split('?')[0]
                    if name and len(name) > 2:
                        categorias.append({"name": name, "path": path})
        except:
            pass

        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        # 2. VARREDURA EXTENSIVA USANDO THREADING (Processamento em paralelo)
        with ThreadPoolExecutor(max_workers=25) as executor:
            for serv in servidores:
                # Geral: Escaneia as 10 primeiras páginas de cada servidor
                for page in range(1, 11):
                    url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                    tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], "Geral"))

                # Por Categoria: Escaneia as 2 primeiras páginas de cada uma das 50+ categorias
                for cat in categorias:
                    for page in range(1, 3):
                        url_cat = f"https://app.pobreflix2.site{cat['path']}?page={page}&thema=1&server={serv['id']}"
                        tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], cat['name']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"

        results = []
        for task in tasks:
            results.extend(task.result())

        # Ordenar a lista final por Categoria e Nome para organizar o player
        results.sort(key=lambda x: (x['category'], x['nome']))

        count = 0
        for canal in results:
            if canal['key'] not in links_vistos:
                links_vistos.add(canal['key'])
                logo = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                # Monta a linha padrão M3U com pasta (group-title)
                m3u_content += f'#EXTINF:-1{logo} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        # Comentário de rodapé para auditoria dos canais capturados
        m3u_content += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    # O Railway gerencia a porta automaticamente pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
