from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        # Usamos Session para reaproveitar a conexão e acelerar a captura
        session = requests.Session()
        session.headers.update(headers)

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        # Filtros para ignorar links de navegação do site
        menu_items = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos']

        for serv in servidores:
            # Escaneia até 15 páginas por servidor para garantir a captura total dos canais
            for page in range(1, 16):
                url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                try:
                    r = session.get(url, timeout=12)
                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, 'html.parser')
                    encontrou_novo = False

                    # Busca todos os links na página atual
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        nome = a.get_text(strip=True)
                        logo = ""

                        # Extrai o Logotipo e o Nome (caso o texto esteja em branco)
                        img = a.find('img')
                        if img:
                            logo = img.get('src') or img.get('data-src') or ""
                            if not nome:
                                nome = img.get('alt') or img.get('title') or ""

                        if nome is None: 
                            nome = ""
                        
                        nome_lower = nome.lower()

                        # Aplica filtros para capturar apenas canais válidos
                        is_menu = any(menu in nome_lower for menu in menu_items)
                        is_category = '/categorias' in href or '/categoria' in href

                        if nome and len(nome) > 1 and not is_menu and not is_category:
                            # Chave única por servidor para permitir o mesmo canal em fontes diferentes
                            chave = f"{nome}-{href}-{serv['id']}"
                            if chave not in links_vistos:
                                links_vistos.add(chave)
                                encontrou_novo = True

                                # Garante que a URL esteja completa
                                full_url = href
                                if href.startswith('/'):
                                    full_url = f"https://app.pobreflix2.site{href}"

                                # Adiciona o parâmetro de servidor à URL final do player
                                if 'server=' not in full_url:
                                    sep = '&' if '?' in full_url else '?'
                                    full_url = f"{full_url}{sep}server={serv['id']}"

                                # Formata a entrada M3U com logo e categoria
                                logo_attr = f' tvg-logo="{logo}"' if logo else ""
                                m3u_content += f'#EXTINF:-1{logo_attr} group-title="Ycine TV LIVE",{nome} ({serv["label"]})\n{full_url}\n'

                    # Se a página não retornou nada novo, encerra a busca neste servidor
                    if not encontrou_novo:
                        break
                except:
                    continue

        # Retorna a lista em formato de texto puro para players de IPTV
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Define a porta dinamicamente para deploy no Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
