from flask import Flask, jsonify
import os
import requests
from bs4 import BeautifulSoup
import logging

# Configuração de logs
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
BASE_URL = "https://ycineflix.tudo30.shop"

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine funcionando!"})

@app.route('/canais')
def get_canais():
    try:
        url_canais = f"{BASE_URL}/channels"
        headers = {'User-Agent': 'Mozilla/5.0...'}
        response = requests.get(url_canais, headers=headers, timeout=10)
        
        soup = BeautifulSoup(response.text, 'html.parser')
        canais = []
        for item in soup.find_all('a'):
            href = item.get('href', '')
            text = item.get_text(strip=True)
            if '/play/' in href or '/channel/' in href:
                canais.append({
                    "nome": text,
                    "url": f"{BASE_URL}{href}" if href.startswith('/') else href
                })
        return jsonify({"total": len(canais), "canais": canais})
    except Exception as e:
        logger.error(f"Erro: {str(e)}")
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
