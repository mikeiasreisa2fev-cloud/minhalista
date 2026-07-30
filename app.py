from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)

# URL base do serviço
BASE_URL = "https://app.pobreflix2.site"

# Cabeçalhos para simular um navegador real e evitar bloqueios de segurança
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': BASE_URL,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
}

def get_real_categories():
    """Busca as categorias reais (Esportes, Infantil, etc.) existentes no site."""
    found_categories = []
    try:
        r = requests.get(f"{BASE_URL}/canais", headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Filtra links que apontam para páginas de categorias
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/canais/categoria/' in href or '/categoria/' in href:
                name = a.get_text(strip=True)
                if name and len(name) > 2:
                    # Normaliza a URL para ser usada depois
                    full_cat_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                    found_categories.append({"name": name, "url": full_cat_url})
    except:
        pass
    return found_categories

def scrape_channels_from_url(url, serv_id, serv_label, category_name):
    """Extrai canais de uma URL específica (página de categoria ou geral)."""
    channels = []
    try:
        # Pequeno intervalo para não sobrecarregar o site original
        time.sleep(0.1)
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Analisa todos os links da página
        for a in soup.find_all('a', href=True):
            href = a['href']

            # Verifica se é um link de reprodução de canal
            if '/canais/' in href or '/play/' in href:
                # Ignora links que são apenas de navegação
                if any(x in href for x in ['/categoria', 'page=', 'thema=']): 
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    # Captura o link da imagem (Logotipo)
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        # Fallback para o nome do canal usando o 'alt' da imagem
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or len(nome) < 2: 
                    continue
                
                # Blacklist de termos que aparecem em menus mas não são canais
                if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'contato', 'buscar']): 
                    continue

                # Formata a URL final injetando o ID do servidor
                clean_path = href.split('?')[0].split('#')[0]
                final_url = f"{BASE_URL}{clean_path}" if clean_path.startswith('/') else clean_path
                final_url += f"?thema=1&server={serv_id}"

                channels.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": final_url,
                    "logo": logo,
                    "category": category_name,
                    "key": f"{serv_id}-{clean_path}"
                })
    except:
        pass
    return channels

@app.route('/')
def welcome():
    return jsonify({"status": "online", "message": "Ycine Scraper PRO Ativo"})

@app.route('/canais')
def generate_m3u():
    try:
        # 1. Mapeia as categorias reais do site
        real_cats = get_real_categories()

        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        # 2. Cria uma lista de tarefas para varrer a lista GERAL e as CATEGORIAS
        for serv in servidores:
            # Varre 15 páginas da lista geral
            for p in range(1, 16):
                url = f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}"
                tasks.append((url, serv['id'], serv['label'], "Geral"))

            # Varre as 3 primeiras páginas de cada categoria específica
            for cat in real_cats:
                for p in range(1, 4):
                    sep = '&' if '?' in cat['url'] else '?'
                    url = f"{cat['url']}{sep}page={p}&thema=1&server={serv['id']}"
                    tasks.append((url, serv['id'], serv['label'], cat['name']))

        # 3. Executa as requisições em paralelo (10 conexões por vez)
        all_channels = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scrape_channels_from_url, *t) for t in tasks]
            for f in futures:
                all_channels.extend(f.result())

        # 4. Remove duplicatas e gera a lista M3U
        seen = set()
        m3u = "#EXTM3U\n"
        count = 0
        
        # Ordena a lista para o player (Categoria > Nome)
        all_channels.sort(key=lambda x: (x['category'], x['nome']))

        for c in all_channels:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                # Monta a linha M3U padrão IPTV
                m3u += f'#EXTINF:-1{logo} group-title="{c["category"]}",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Contador de debug no final
        m3u += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    # O Railway fornece a porta automaticamente pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
