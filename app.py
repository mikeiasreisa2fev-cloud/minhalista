from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

# Configurações de Conexão para simular um navegador real e evitar bloqueios
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Referer': 'https://app.pobreflix2.site/'
}

def get_session():
    s = requests.Session()
    s.headers.update(HEADERS)
    return s

# Função principal de extração de dados do HTML
def extract_from_html(html, serv_id, serv_label):
    found = []
    soup = BeautifulSoup(html, 'html.parser')
    menu_blacklist = ['início', 'filmes', 'séries', 'canais', 'buscar', 'minha conta', 'sair', 'contato', 'termos', 'editar']

    # Busca em qualquer tag que possa conter links (Deep Crawl)
    for el in soup.find_all(['a', 'div', 'li', 'span']):
        href = el.get('href') or el.get('data-href') or el.get('data-link') or el.get('data-url')
        if not href: continue

        # Identifica links de reprodução de canais
        if '/canais/' in href or '/play/' in href:
            if any(x in href for x in ['/categorias', '?s=', 'page=']): continue

            nome = el.get_text(strip=True)
            logo = ""
            img = el.find('img')
            if img:
                logo = img.get('src') or img.get('data-src') or ""
                if not nome:
                    nome = img.get('alt') or img.get('title') or ""

            if not nome or any(m == nome.lower() for m in menu_blacklist): continue

            # Limpa e normaliza a URL do canal
            clean_href = href.split('?')[0].split('#')[0]
            full_url = clean_href if clean_href.startswith('http') else f"https://app.pobreflix2.site{clean_href}"
            
            # Adiciona os parâmetros necessários para o player funcionar no servidor correto
            full_url += f"?thema=1&server={serv_id}"

            found.append({
                "nome": f"{nome} ({serv_label})",
                "url": full_url,
                "logo": logo,
                "chave": f"{serv_id}-{clean_href}"
            })
    return found

# Worker para processamento paralelo das URLs
def fetch_worker(url, serv_id, serv_label):
    try:
        s = get_session()
        r = s.get(url, timeout=20)
        if r.status_code == 200:
            return extract_from_html(r.text, serv_id, serv_label)
    except:
        pass
    return []

@app.route('/')
def index():
    return jsonify({"status": "ready", "module": "Ycine Scraper Ultra"})

@app.route('/canais')
def canais_m3u():
    try:
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        urls_to_scan = []
        # 1. Varredura por Páginas (Aumentado para 50 páginas por servidor)
        for serv in servidores:
            for p in range(1, 51):
                urls_to_scan.append((f"https://app.pobreflix2.site/canais?page={p}&thema=1&server={serv['id']}", serv['id'], serv['label']))

        # 2. Varredura por Categorias Comuns (Deep Scan)
        cats = ['abertos', 'esportes', 'filmes-e-series', 'documentarios', 'infantil', 'variedades', 'noticias', 'religiosos']
        for serv in servidores:
            for cat in cats:
                for p in range(1, 10):
                    urls_to_scan.append((f"https://app.pobreflix2.site/canais/categoria/{cat}?page={p}&thema=1&server={serv['id']}", serv['id'], serv['label']))

        # Execução Multi-Thread de alta velocidade (30 workers)
        all_channels = []
        with ThreadPoolExecutor(max_workers=30) as executor:
            futures = [executor.submit(fetch_worker, u, sid, sl) for u, sid, sl in urls_to_scan]
            for f in futures:
                all_channels.extend(f.result())

        # Consolidação e geração da Lista M3U
        links_vistos = set()
        m3u = "#EXTM3U\n"
        count = 0
        
        # Ordenação alfabética
        all_channels.sort(key=lambda x: x['nome'])

        for c in all_channels:
            if c['chave'] not in links_vistos:
                links_vistos.add(c['chave'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                m3u += f'#EXTINF:-1{logo} group-title="Ycine TV LIVE",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Contador de verificação no final da lista
        m3u += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro Crítico: {str(e)}", 500

if __name__ == "__main__":
    # O Railway usa a porta fornecida pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
