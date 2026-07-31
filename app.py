from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time

app = Flask(__name__)

# URL base do serviço
BASE_URL = "https://app.pobreflix2.site"

# Cabeçalhos otimizados para simular um acesso humano e evitar firewall
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Referer': 'https://app.pobreflix2.site/canais/categorias/?thema=1&server=speed-1'
}

def get_categories():
    """Descobre as categorias reais do site para organizar a lista."""
    cats = []
    try:
        url = f"{BASE_URL}/canais/categorias/?thema=1&server=speed-1"
        r = requests.get(url, headers=HEADERS, timeout=15)
        soup = BeautifulSoup(r.text, 'html.parser')
        for a in soup.find_all('a', href=True):
            href = a['href']
            if '/categoria/' in href:
                name = a.get_text(strip=True)
                full_url = href if href.startswith('http') else f"{BASE_URL}{href}"
                # Remove parâmetros para limpar a URL base da categoria
                cats.append({"name": name, "url": full_url.split('?')[0]})
    except:
        pass
    return cats

def scrape_worker(url, serv_id, serv_label, category):
    """Realiza a extração profunda de cada página individualmente."""
    found = []
    try:
        # Delay de segurança para não ser bloqueado (0.2 segundos)
        time.sleep(0.2)
        r = requests.get(url, headers=HEADERS, timeout=25)
        if r.status_code != 200: return []

        soup = BeautifulSoup(r.text, 'html.parser')
        
        # Procura por cards de canais em links, divs ou itens de lista
        elements = soup.find_all(['a', 'div', 'li'], recursive=True)

        for el in elements:
            href = el.get('href') or el.get('data-href') or el.get('data-link')
            if not href: continue

            # Filtra links que são efetivamente reprodutores de canais
            if '/canais/' in href or '/play/' in href:
                # Ignora botões de menu ou de categorias
                if '/canais/categorias' in href: continue

                nome = el.get_text(strip=True)
                logo = ""
                img = el.find('img')
                if img:
                    # Captura o ícone do canal para exibir no player
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        nome = img.get('alt') or img.get('title') or ""

                # Filtra nomes inválidos ou itens de menu
                if not nome or len(nome) < 2: continue
                if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'buscar', 'contato']): 
                    continue

                # Reconstrói a URL final com o ID do servidor injetado
                path = href.split('?')[0].split('#')[0]
                final_url = f"{BASE_URL}{path}" if path.startswith('/') else path
                final_url += f"?thema=1&server={serv_id}"

                found.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": final_url,
                    "logo": logo,
                    "cat": category,
                    "key": f"{serv_id}-{path}"
                })
    except:
        pass
    return found

@app.route('/')
def home():
    return "API YCINE MASTER V3 ONLINE"

@app.route('/canais')
def generate_m3u():
    try:
        # 1. Obtém as pastas reais do site
        cats = get_categories()
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        # 2. Cria a malha de varredura (15 páginas gerais + 5 páginas por categoria)
        for serv in servidores:
            # Lista Geral
            for p in range(1, 15):
                tasks.append((f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}", serv['id'], serv['label'], "Geral"))

            # Categorias Específicas
            for c in cats:
                for p in range(1, 5):
                    tasks.append((f"{c['url']}?page={p}&thema=1&server={serv['id']}", serv['id'], serv['label'], c['name']))

        # 3. Execução Multi-Thread controlada (5 workers para evitar banimento de IP)
        all_data = []
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(scrape_worker, *t) for t in tasks]
            for f in futures:
                all_data.extend(f.result())

        seen = set()
        m3u = "#EXTM3U\n"
        count = 0
        
        # Ordenação por grupo para organizar o player de IPTV
        all_data.sort(key=lambda x: (x['cat'], x['nome']))

        for c in all_data:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                # Formato padrão: group-title cria pastas no player
                m3u += f'#EXTINF:-1{logo} group-title="{c["cat"]}",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Contador de conferência final
        if count == 0:
            m3u += "# ERRO: Nenhum canal encontrado. O site pode estar bloqueando o servidor.\n"
        else:
            m3u += f"\n# TOTAL CAPTURADO: {count}\n"

        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro: {str(e)}", 500

if __name__ == "__main__":
    # O Railway utiliza a variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
