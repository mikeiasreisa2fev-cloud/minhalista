from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# URL base do serviço Ycine
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
        url = f"{BASE_URL}/channels"
        # Headers mais completos para simular um navegador real e evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7'
        }
        r = requests.get(url, headers=headers, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Usar um set para evitar canais duplicados na lista
        links_vistos = set()
        m3u_content = "#EXTM3U\n"

        # Procurar links em várias tags comuns (a, div, li) e atributos (href, data-href)
        items = soup.find_all(['a', 'div', 'li'])

        for item in items:
            href = item.get('href') or item.get('data-href') or item.get('data-link')

            if href and ('/play/' in href or '/channel/' in href):
                if href in links_vistos:
                    continue

                # Extrai o nome do canal (texto do elemento)
                nome = item.get_text(strip=True)
                
                # Se o texto estiver vazio, tenta buscar o nome em atributos de imagem (alt/title)
                if not nome:
                    img = item.find('img')
                    nome = img.get('alt') or img.get('title') if img else "Canal sem nome"

                if nome and nome != "Canal sem nome":
                    links_vistos.add(href)
                    # Formata a URL completa
                    full_url = f"{BASE_URL}{href}" if href.startswith('/') else href
                    # Estrutura M3U com categoria
                    m3u_content += f'#EXTINF:-1 group-title="Ycine TV",{nome}\n{full_url}\n'

        # Fallback: Se a busca específica falhar, tenta capturar links gerais com texto
        if len(links_vistos) == 0:
            for a in soup.find_all('a', href=True):
                nome = a.get_text(strip=True)
                if nome and len(nome) > 2:
                    href = a['href']
                    full_url = f"{BASE_URL}{href}" if href.startswith('/') else href
                    m3u_content += f'#EXTINF:-1 group-title="Ycine TV",{nome}\n{full_url}\n'

        # Retorna a lista como texto puro (text/plain) para ser lida corretamente por players
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # O Railway fornece a porta via variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
