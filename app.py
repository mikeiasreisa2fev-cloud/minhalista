from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Função que extrai os canais de cada página individualmente
def fetch_page(session, url, serv_label, serv_id):
    canais_da_pagina = []
    try:
        r = session.get(url, timeout=15)
        if r.status_code != 200:
            return []
        
        soup = BeautifulSoup(r.text, 'html.parser')
        menu_labels = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair']
        
        for a in soup.find_all('a', href=True):
            href = a['href']
            # Filtra apenas links que são canais (evita categorias)
            if '/canais/' in href or '/play/' in href:
                if any(x in href for x in ['/categorias', '/categoria', '?s=']):
                    continue
                
                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""
                
                if not nome or nome.lower() in menu_labels:
                    continue
                
                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"
                
                # Garante que o servidor correto seja passado na URL
                if 'server=' not in full_url:
                    sep = '&' if '?' in full_url else '?'
                    full_url = f"{full_url}{sep}server={serv_id}"
                
                canais_da_pagina.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": full_url,
                    "logo": logo,
                    "chave": f"{nome}-{full_url}"
                })
    except:
        pass
    return canais_da_pagina

@app.route('/canais')
def get_canais():
    try:
        # Configuração para cobrir todos os canais informados
        servidores = [
            {"id": "speed-1", "label": "S1", "pages": 25},
            {"id": "speed-2", "label": "S2", "pages": 30},
            {"id": "speed-3", "label": "S3", "pages": 20}
        ]
        
        session = requests.Session()
        session.headers.update({'User-Agent': 'Mozilla/5.0...'})
        
        tasks = []
        with ThreadPoolExecutor(max_workers=15) as executor:
            for serv in servidores:
                for page in range(1, serv['pages'] + 1):
                    url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                    tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id']))
        
        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        for task in tasks:
            for canal in task.result():
                if canal['chave'] not in links_vistos:
                    links_vistos.add(canal['chave'])
                    logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                    m3u_content += f'#EXTINF:-1{logo_attr} group-title="Ycine TV LIVE",{canal["nome"]}\n{canal["url"]}\n'

        return Response(m3u_content, mimetype='text/plain')
    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
