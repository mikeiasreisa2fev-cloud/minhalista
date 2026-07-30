from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)

# URL base do serviço
BASE_URL = "https://app.pobreflix2.site"

# Cabeçalhos para simular um navegador real e evitar bloqueios
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Referer': BASE_URL,
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
}

def get_real_categories():
    """Busca as categorias reais clicáveis na página de categorias oficial."""
    found_categories = []
    try:
        # Acessa o link oficial de categorias fornecido
        cat_page_url = f"{BASE_URL}/canais/categorias/?thema=1&server=speed-1"
        r = requests.get(cat_page_url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')

        # Procura por links de categorias (ex: /canais/categoria/esportes)
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/categoria/' in href:
                name = a.get_text(strip=True)
                if name and len(name) > 2:
                    # Normaliza a URL removendo parâmetros existentes
                    full_cat_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                    full_cat_url = full_cat_url.split('?')[0]
                    found_categories.append({"name": name, "url": full_cat_url})
    except:
        pass
    return found_categories

def scrape_channels_from_url(url, serv_id, serv_label, category_name):
    """Extrai canais de qualquer URL específica (Geral ou Categoria)."""
    channels = []
    try:
        # Pequeno delay para evitar bloqueio por excesso de requisições
        time.sleep(0.1)
        r = requests.get(url, headers=HEADERS, timeout=20)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Varre todos os links em busca de reprodutores de canais
        for a in soup.find_all('a', href=True):
            href = a['href']

            # Verifica se o link é de reprodução (play ou canais)
            if '/canais/' in href or '/play/' in href:
                # Pula links que são apenas botões de navegação ou categorias
                if any(x in href for x in ['/categoria', 'page=', 'thema=']): 
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    # Captura o ícone do canal
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        # Se não houver texto, tenta usar o atributo 'alt' da imagem
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or len(nome) < 2: 
                    continue
                
                # Ignora itens comuns de menu que não são canais
                if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'contato', 'buscar']): 
                    continue

                # Limpa a URL e anexa os parâmetros de servidor e tema para o player
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
    return jsonify({"status": "online", "message": "Ycine Scraper PRO Master Ativo"})

@app.route('/canais')
def generate_m3u():
    try:
        # 1. Mapeia automaticamente as pastas de canais reais do site
        real_cats = get_real_categories()

        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        # 2. Prepara a varredura profunda (Lista Geral + Todas as Categorias)
        for serv in servidores:
            # Varre 15 páginas da listagem geral por servidor
            for p in range(1, 16):
                url = f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}"
                tasks.append((url, serv['id'], serv['label'], "Geral"))

            # Varre as 3 primeiras páginas de cada categoria específica encontrada
            for cat in real_cats:
                for p in range(1, 4):
                    sep = '&' if '?' in cat['url'] else '?'
                    url = f"{cat['url']}{sep}page={p}&thema=1&server={serv['id']}"
                    tasks.append((url, serv['id'], serv['label'], cat['name']))

        # 3. Executa as requisições em paralelo com velocidade controlada (10 conexões por vez)
        all_channels = []
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(scrape_channels_from_url, *t) for t in tasks]
            for f in futures:
                all_channels.extend(f.result())

        # 4. Remove duplicatas e gera a lista M3U formatada
        seen = set()
        m3u = "#EXTM3U\n"
        count = 0
        
        # Ordena a lista por Categoria e Nome para ficar organizado no seu player
        all_channels.sort(key=lambda x: (x['category'], x['nome']))

        for c in all_channels:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                # group-title cria as seções (pastas) no player de IPTV
                m3u += f'#EXTINF:-1{logo} group-title="{c["category"]}",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Comentário de verificação final
        m3u += f"\n# TOTAL CAPTURADO: {count}\n"
        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro Crítico: {str(e)}", 500

if __name__ == "__main__":
    # O Railway fornece a porta automaticamente
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
