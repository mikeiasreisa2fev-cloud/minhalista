from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

# URL base original
BASE_URL = "https://ycineflix.tudo30.shop"

@app.route('/')
def home():
    return jsonify({
        "status": "online",
        "message": "API Ycine Ativa"
    })

@app.route('/canais')
def get_canais():
    try:
        # Configuração dos servidores para captura
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        # Headers para simular navegador e evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/'
        }

        # Session para acelerar as requisições
        session = requests.Session()
        session.headers.update(headers)

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        # Filtros para ignorar menus e navegação
        menu_items = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos', 'política']

        for serv in servidores:
            # Varre 20 páginas por servidor para garantir a captura total
            for page in range(1, 21):
                url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                try:
                    # Delay para estabilidade
                    time.sleep(0.2)
                    r = session.get(url, timeout=15)

                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, 'html.parser')
                    links_na_pagina = soup.find_all('a', href=True)
                    
                    if not links_na_pagina:
                        break

                    encontrou_util = False
                    for a in links_na_pagina:
                        href = a['href']

                        # Captura apenas links de reprodução de canais
                        if '/play/' in href or '/canais/' in href:
                            # Ignora categorias e filtros
                            if any(x in href for x in ['/categorias', '/categoria', '?s=', 'thema=']):
                                continue

                            nome = a.get_text(strip=True)
                            logo = ""

                            # Tenta extrair logo e nome alternativo
                            img = a.find('img')
                            if img:
                                logo = img.get('src') or img.get('data-src') or ""
                                if not nome:
                                    nome = img.get('alt') or img.get('title') or ""

                            if not nome or any(menu in nome.lower() for menu in menu_items):
                                continue

                            # Chave única para evitar duplicados
                            chave = f"{nome}-{href}-{serv['id']}"
                            if chave not in links_vistos:
                                links_vistos.add(chave)
                                encontrou_util = True

                                full_url = href
                                if href.startswith('/'):
                                    full_url = f"https://app.pobreflix2.site{href}"

                                # Garante que o parâmetro de servidor esteja na URL
                                if 'server=' not in full_url:
                                    sep = '&' if '?' in full_url else '?'
                                    full_url = f"{full_url}{sep}server={serv['id']}"

                                # Formatação M3U com tvg-logo
                                logo_attr = f' tvg-logo="{logo}"' if logo else ""
                                m3u_content += f'#EXTINF:-1{logo_attr} group-title="Ycine TV LIVE",{nome} ({serv["label"]})\n{full_url}\n'

                    # Se a página for vazia ou sem canais novos, pula para o próximo servidor
                    if not encontrou_util and page > 1:
                        pass 

                except Exception as e:
                    continue

        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Porta dinâmica para o Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
