from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Ativa"})

def fetch_page(session, url, serv_label, serv_id):
    canais_da_pagina = []
    try:
        # Tenta até 2 vezes se falhar a requisição
        for _ in range(2):
            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200:
                    break
                time.sleep(1)
            except:
                time.sleep(1)
                continue
        else:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        # Itens que não são canais e devem ser ignorados
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta']

        for a in soup.find_all('a', href=True):
            href = a['href']
            
            # Captura canais e ignora categorias/paginação no link
            if '/canais/' in href or '/play/' in href:
                if any(x in href for x in ['/categorias', '/categoria', '?s=', 'page=']):
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""

                # Valida se o nome é útil
                if not nome or any(menu == nome.lower() for menu in menu_items):
                    continue

                # Normaliza a URL para o player
                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"
                
                # Garante parâmetros de servidor e tema na URL
                if 'server=' not in full_url:
                    sep = '&' if '?' in full_url else '?'
                    full_url = f"{full_url}{sep}server={serv_id}&thema=1"
                elif 'thema=' not in full_url:
                    full_url = f"{full_url}&thema=1"

                canais_da_pagina.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": full_url,
                    "logo": logo,
                    "chave": f"{serv_id}-{href.split('?')[0]}" # Chave única para evitar duplicados
                })
    except:
        pass
    return canais_da_pagina

@app.route('/canais')
def get_canais():
    try:
        # Limites aumentados para capturar centenas de canais
        servidores = [
            {"id": "speed-1", "label": "S1", "pages": 35},
            {"id": "speed-2", "label": "S2", "pages": 40},
            {"id": "speed-3", "label": "S3", "pages": 30}
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        }

        session = requests.Session()
        session.headers.update(headers)

        all_tasks = []
        # Processamento paralelo com 20 threads para carregar todas as páginas rapidamente
        with ThreadPoolExecutor(max_workers=20) as executor:
            for serv in servidores:
                for page in range(1, serv['pages'] + 1):
                    url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id']))

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        count = 0
        for task in all_tasks:
            result = task.result()
            for canal in result:
                if canal['chave'] not in links_vistos:
                    links_vistos.add(canal['chave'])
                    logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                    m3u_content += f'#EXTINF:-1{logo_attr} group-title="Ycine TV LIVE",{canal["nome"]}\n{canal["url"]}\n'
                    count += 1

        # Contador no final para conferência
        m3u_content += f"\n# TOTAL DE CANAIS CAPTURADOS: {count}\n"

        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
