from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import re

app = Flask(__name__)

# URL base e cabeçalhos para simular um navegador real
BASE_URL = "https://app.pobreflix2.site"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': BASE_URL
}

def get_categories():
    """Tenta descobrir as categorias reais do site para uma varredura completa."""
    categories = []
    try:
        r = requests.get(f"{BASE_URL}/canais/categorias", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/canais/categoria/' in href:
                slug = href.split('/categoria/')[-1].split('?')[0]
                name = a.get_text(strip=True)
                if slug and name:
                    categories.append({"slug": slug, "name": name})
    except:
        pass

    # Caso a busca automática falhe, usa estas categorias como padrão
    if not categories:
        categories = [
            {"slug": "abertos", "name": "Canais Abertos"},
            {"slug": "esportes", "name": "Esportes"},
            {"slug": "filmes-e-series", "name": "Filmes e Séries"},
            {"slug": "infantil", "name": "Infantil"},
            {"slug": "variedades", "name": "Variedades"},
            {"slug": "documentarios", "name": "Documentários"},
            {"slug": "noticias", "name": "Notícias"},
            {"slug": "religiosos", "name": "Religiosos"}
        ]
    return categories

def scrape_page(url, serv_id, serv_label, category_name):
    """Extrai os canais de uma página específica de forma detalhada."""
    channels = []
    try:
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        # Procura por links em qualquer elemento (cards de canais)
        items = soup.find_all(['a', 'div', 'li'], recursive=True)

        for item in items:
            href = item.get('href') or item.get('data-href') or item.get('data-link')
            if not href or ('/canais/' not in href and '/play/' not in href): continue
            
            # Pula links que são apenas de navegação
            if '/categoria' in href or 'page=' in href: continue

            nome = item.get_text(strip=True)
            logo = ""
            img = item.find('img')
            if img:
                logo = img.get('src') or img.get('data-src') or ""
                if not nome: nome = img.get('alt') or img.get('title') or ""

            if not nome or len(nome) < 2: continue
            
            # Filtra itens de menu indesejados
            if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'contato']): continue

            # Formata a URL final com os parâmetros do servidor
            path = href.split('?')[0]
            full_url = path if path.startswith('http') else f"{BASE_URL}{path}"
            full_url += f"?thema=1&server={serv_id}"

            channels.append({
                "nome": f"{nome} ({serv_label})",
                "url": full_url,
                "logo": logo,
                "category": category_name,
                "key": f"{serv_id}-{path}"
            })
    except:
        pass
    return channels

@app.route('/')
def home():
    return jsonify({"status": "active", "service": "Ycine Scraper PRO"})

@app.route('/canais')
def generate_m3u():
    try:
        # 1. Descobre as pastas/categorias do site
        categories = get_categories()
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        scan_tasks = []
        # 2. Prepara a varredura em massa
        for serv in servidores:
            # Varre as páginas de cada categoria encontrada
            for cat in categories:
                for p in range(1, 6):
                    url = f"{BASE_URL}/canais/categoria/{cat['slug']}?page={p}&thema=1&server={serv['id']}"
                    scan_tasks.append((url, serv['id'], serv['label'], cat['name']))

            # Também varre as páginas da lista geral (até 15 páginas)
            for p in range(1, 16):
                url = f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}"
                scan_tasks.append((url, serv['id'], serv['label'], "Geral"))

        # 3. Executa a extração em paralelo (mais rápido)
        all_results = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            futures = [executor.submit(scrape_page, *task) for task in scan_tasks]
            for f in futures:
                all_results.extend(f.result())

        # 4. Remove duplicatas e gera o arquivo M3U formatado
        seen = set()
        m3u = "#EXTM3U\n"
        count = 0
        
        # Ordena a lista por categoria para ficar organizado no player
        all_results.sort(key=lambda x: (x['category'], x['nome']))

        for c in all_results:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                # group-title cria as "pastas" no seu aplicativo de IPTV
                m3u += f'#EXTINF:-1{logo} group-title="{c["category"]}",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Comentário de verificação no final
        m3u += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    # Configuração de porta padrão para o Railway
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
