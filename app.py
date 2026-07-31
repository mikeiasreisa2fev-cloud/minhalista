from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

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
        # Nova URL detectada que parece conter os canais reais
        url = "https://app.pobreflix2.site/canais?thema=1&server=speed-1"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        links_vistos = set()
        m3u_content = "#EXTM3U\n"

        # Palavras que indicam que o link é um menu e não um canal
        menu_items = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'editar conta', 'sair', 'contato', 'termos']

        # O site geralmente coloca os canais em cards/links
        for a in soup.find_all('a', href=True):
            href = a['href']
            nome = a.get_text(strip=True)

            # Tenta pegar o nome de um title ou alt se o texto for vazio
            if not nome:
                img = a.find('img')
                if img:
                    nome = img.get('alt') or img.get('title') or ""
                else:
                    nome = ""

            # Garante que 'nome' seja uma string válida antes de processar
            if nome is None:
                nome = ""

            nome_lower = nome.lower()

            # Filtros para capturar apenas canais de TV
            is_menu = any(menu in nome_lower for menu in menu_items)
            is_category = '/categorias' in href or '/categoria' in href

            if nome and len(nome) > 1 and not is_menu and not is_category:
                if href not in links_vistos:
                    links_vistos.add(href)

                    # Ajusta a URL base se necessário
                    full_url = href
                    if href.startswith('/'):
                        full_url = f"https://app.pobreflix2.site{href}"

                    m3u_content += f'#EXTINF:-1 group-title="Ycine TV LIVE",{nome}\n{full_url}\n'

        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
