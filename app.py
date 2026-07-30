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
        return jsonify({"error": str(e)}), 500
