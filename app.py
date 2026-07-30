from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time

app = Flask(__name__)

# URL base original do serviço
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

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/'
        }

        # Session para acelerar a captura de múltiplas páginas
        session = requests.Session()
        session.headers.update(headers)

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        # Rótulos de menu para serem ignorados
        menu_labels = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos', 'política', 'dmca']

        for serv in servidores:
            # Varre até 12 páginas por servidor (suficiente para capturar todos os canais)
            for page in range(1, 13):
                url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                try:
                    time.sleep(0.1) # Pequeno delay para estabilidade
                    r = session.get(url, timeout=12)
                    if r.status_code != 200: 
                        break

                    soup = BeautifulSoup(r.text, 'html.parser')
                    links_na_pagina = soup.find_all('a', href=True)
                    
                    if not links_na_pagina: 
                        break

                    encontrou_canal_novo = False
                    for a in links_na_pagina:
                        href = a['href']
                        nome = a.get_text(strip=True)

                        # Captura links de player, ignorando categorias e buscas
                        if '/play/' in href or '/canais/' in href:
                            if '/categorias' in href or '/categoria' in href or '?s=' in href:
                                continue

                            # Captura imagem do logo e nome alternativo
                            img = a.find('img')
                            logo = ""
                            if img:
                                logo = img.get('src') or img.get('data-src') or ""
                                if not nome:
                                    nome = img.get('alt') or img.get('title') or ""

                            if not nome: 
                                continue
                            
                            nome_lower = nome.lower()

                            # Ignora se for link de navegação (ex: "Início")
                            if nome_lower in menu_labels:
                                continue

                            # Chave única por servidor para permitir redundância
                            chave = f"{nome}-{href}-{serv['id']}"
                            if chave not in links_vistos:
                                links_vistos.add(chave)
                                encontrou_canal_novo = True

                                full_url = href
                                if href.startswith('/'):
                                    full_url = f"https://app.pobreflix2.site{href}"

                                # Garante que o servidor esteja na URL para o player
                                if 'server=' not in full_url:
                                    sep = '&' if '?' in full_url else '?'
                                    full_url = f"{full_url}{sep}server={serv['id']}"

                                # Formatação M3U compatível com IPTV
                                logo_attr = f' tvg-logo="{logo}"' if logo else ""
                                m3u_content += f'#EXTINF:-1{logo_attr} group-title="Ycine TV LIVE",{nome} ({serv["label"]})\n{full_url}\n'

                    # Se a página atual não trouxe nada novo, passamos para o próximo servidor
                    if not encontrou_canal_novo:
                        pass
                except:
                    continue

        # Entrega a lista como texto puro
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Porta dinâmica para deploy no Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
