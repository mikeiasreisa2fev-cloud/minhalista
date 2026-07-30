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
        # Servidores para varredura
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }

        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        
        # Filtros de menu para ignorar links de navegação
        menu_items = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos']

        for serv in servidores:
            # Varre até 5 páginas de cada servidor para garantir a captura total
            for page in range(1, 6):
                url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                try:
                    r = requests.get(url, headers=headers, timeout=12)
                    if r.status_code != 200:
                        break

                    soup = BeautifulSoup(r.text, 'html.parser')
                    encontrou_novo = False

                    # Varre todos os links da página atual
                    for a in soup.find_all('a', href=True):
                        href = a['href']
                        nome = a.get_text(strip=True)

                        # Tenta capturar o nome de imagens se o texto estiver vazio
                        if not nome:
                            img = a.find('img')
                            nome = (img.get('alt') or img.get('title') or "") if img else ""

                        if nome is None: 
                            nome = ""
                        
                        nome_lower = nome.lower()

                        # Verifica se o link é um canal válido e não um menu ou categoria
                        is_menu = any(menu in nome_lower for menu in menu_items)
                        is_category = '/categorias' in href or '/categoria' in href

                        if nome and len(nome) > 1 and not is_menu and not is_category:
                            chave = f"{nome}-{href}"
                            if chave not in links_vistos:
                                links_vistos.add(chave)
                                encontrou_novo = True

                                # Garante a URL completa
                                full_url = href
                                if href.startswith('/'):
                                    full_url = f"https://app.pobreflix2.site{href}"

                                # Adiciona à lista M3U
                                m3u_content += f'#EXTINF:-1 group-title="Ycine TV LIVE",{nome} ({serv["label"]})\n{full_url}\n'

                    # Se a página atual não trouxe nada novo, pula para o próximo servidor
                    if not encontrou_novo:
                        break 
                except:
                    continue

        # Retorna o arquivo M3U para players de IPTV
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Porta dinâmica para o Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
