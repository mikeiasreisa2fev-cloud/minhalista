from flask import Flask, jsonify
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
        url = f"{BASE_URL}/channels"
        headers = {'User-Agent': 'Mozilla/5.0'}
        r = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(r.text, 'html.parser')
        canais = []
        for a in soup.find_all('a'):
            href = a.get('href', '')
            if '/play/' in href or '/channel/' in href:
                canais.append({
                    "nome": a.get_text(strip=True),
                    "url": f"{BASE_URL}{href}" if href.startswith('/') else href
                })
        return jsonify(canais)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
