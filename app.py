from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup

app = Flask(__name__)

# URL base do serviço
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
        # User-Agent completo para evitar bloqueios
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Início do arquivo M3U
        m3u_content = "#EXTM3U\n"

        for a in soup.find_all('a'):
            href = a.get('href', '')
            # Filtro para identificar links de canais
            if '/play/' in href or '/channel/' in href:
                nome = a.get_text(strip=True)
                if not nome: 
                    continue
                
                # Garante que a URL seja completa
                full_url = f"{BASE_URL}{href}" if href.startswith('/') else href
                
                # Formato M3U com Categoria (group-title)
                m3u_content += f'#EXTINF:-1 group-title="Ycine TV",{nome}\n{full_url}\n'

        # Retorna a lista com o MimeType correto para IPTV
        return Response(m3u_content, mimetype='application/x-mpegurl')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # Configuração de porta para o Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
