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
        # Lista de servidores para varredura
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
        
        # Palavras para filtrar links indesejados (menus)
        menu_items = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos']

        # Percorre cada servidor buscando os canais
        for serv in servidores:
            url = f"https://app.pobreflix2.site/canais?thema=1&server={serv['id']}"
            try:
                r = requests.get(url, headers=headers, timeout=10)
                if r.status_code != 200:
                    continue

                soup = BeautifulSoup(r.text, 'html.parser')

                for a in soup.find_all('a', href=True):
                    href = a['href']
                    nome = a.get_text(strip=True)

                    # Tenta capturar o nome do canal se o texto estiver vazio (usando alt/title de imagens)
                    if not nome:
                        img = a.find('img')
                        if img:
                            nome = img.get('alt') or img.get('title') or ""
                        else:
                            nome = ""

                    if nome is None: 
                        nome = ""
                    
                    nome_lower = nome.lower()

                    # Filtros de segurança
                    is_menu = any(menu in nome_lower for menu in menu_items)
                    is_category = '/categorias' in href or '/categoria' in href

                    if nome and len(nome) > 1 and not is_menu and not is_category:
                        # Chave única para evitar links duplicados no mesmo servidor
                        chave = f"{nome}-{href}"

                        if chave not in links_vistos:
                            links_vistos.add(chave)

                            # Monta a URL completa do player
                            full_url = href
                            if href.startswith('/'):
                                full_url = f"https://app.pobreflix2.site{href}"

                            # Adiciona à lista M3U com a etiqueta do servidor (S1, S2, S3)
                            m3u_content += f'#EXTINF:-1 group-title="Ycine TV LIVE",{nome} ({serv["label"]})\n{full_url}\n'
            except:
                # Se um servidor falhar, continua para o próximo
                continue

        # Retorna o arquivo M3U para players de IPTV
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Define a porta dinamicamente para o Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
