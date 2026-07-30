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
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Início do conteúdo da lista M3U
        m3u_content = "#EXTM3U\n"

        for a in soup.find_all('a'):
            href = a.get('href', '')
            # Filtra links que parecem ser de canais ou players
            if '/play/' in href or '/channel/' in href:
                nome = a.get_text(strip=True)
                # Monta a URL completa se for um link relativo
                full_url = f"{BASE_URL}{href}" if href.startswith('/') else href

                # Formato padrão M3U para IPTV
                m3u_content += f"#EXTINF:-1,{nome}\n{full_url}\n"

        # Retorna a resposta como texto simples (text/plain)
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # O Railway usa a variável de ambiente PORT para definir a porta
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
