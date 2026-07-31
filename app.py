from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor
import time
import re

app = Flask(__name__)

# URL e Headers para simular um celular Android real
BASE_URL = "https://app.pobreflix2.site"
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Mobile Safari/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
    'Accept-Language': 'pt-BR,pt;q=0.9,en-US;q=0.8,en;q=0.7',
    'Connection': 'keep-alive',
    'Referer': BASE_URL
}

def get_session():
    session = requests.Session()
    session.headers.update(HEADERS)
    # Visita a home primeiro para obter cookies de sessão e parecer um acesso humano
    try:
        session.get(BASE_URL, timeout=10)
    except:
        pass
    return session

def scrape_worker(url, serv_id, serv_label, category):
    found = []
    try:
        session = get_session()
        r = session.get(url, timeout=25)
        if r.status_code != 200: return []

        # Busca por IDs de canais via Regex (mais robusto que depender apenas do BeautifulSoup)
        # Procura o padrão: /canais/12345 ou /play/12345
        html = r.text
        links = re.findall(r'href=["\'](/?canais/\d+|/?play/\d+)["\']', html)

        # Para cada link encontrado, extraímos o nome e o logotipo de forma cirúrgica
        soup = BeautifulSoup(html, 'html.parser')

        for link in set(links):
            # Procura o elemento <a> exato que contém esse link
            a = soup.find('a', href=re.compile(re.escape(link)))
            if not a: continue

            nome = a.get_text(strip=True)
            logo = ""
            img = a.find('img')
            if img:
                logo = img.get('src') or img.get('data-src') or ""
                if not nome:
                    nome = img.get('alt') or img.get('title') or ""

            # Filtros de validação
            if not nome or len(nome) < 2: continue
            if any(m in nome.lower() for m in ['início', 'minha conta', 'sair', 'contato', 'buscar', 'filtros']):
                continue

            # Formata o caminho e a URL final
            clean_path = link if link.startswith('/') else f"/{link}"
            final_url = f"{BASE_URL}{clean_path}?thema=1&server={serv_id}"

            found.append({
                "nome": f"{nome} ({serv_label})",
                "url": final_url,
                "logo": logo,
                "cat": category,
                "key": f"{serv_id}-{clean_path}"
            })
    except:
        pass
    return found

@app.route('/')
def home():
    return "API YCINE MASTER V4 - ONLINE"

@app.route('/canais')
def generate_m3u():
    try:
        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        tasks = []
        for serv in servidores:
            # Escaneia 15 páginas da lista geral por servidor
            for p in range(1, 16):
                url = f"{BASE_URL}/canais?page={p}&thema=1&server={serv['id']}"
                tasks.append((url, serv['id'], serv['label'], "Canais TV"))

        # Execução multi-tarefa com apenas 4 workers (velocidade segura contra bloqueio de IP)
        all_data = []
        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(scrape_worker, *t) for t in tasks]
            for f in futures:
                all_data.extend(f.result())

        seen = set()
        m3u = "#EXTM3U\n"
        count = 0

        # Ordenação alfabética dos canais
        all_data.sort(key=lambda x: x['nome'])

        for c in all_data:
            if c['key'] not in seen:
                seen.add(c['key'])
                logo = f' tvg-logo="{c["logo"]}"' if c["logo"] else ""
                # group-title cria categorias no player de IPTV
                m3u += f'#EXTINF:-1{logo} group-title="{c["cat"]}",{c["nome"]}\n{c["url"]}\n'
                count += 1

        # Contador no final para auditoria
        if count == 0:
            m3u += "# ERRO: Site bloqueando acesso. Tente novamente em alguns minutos.\n"
        else:
            m3u += f"\n# TOTAL CAPTURADO: {count}\n"

        return Response(m3u, mimetype='text/plain')

    except Exception as e:
        return f"Erro Crítico: {str(e)}", 500

if __name__ == "__main__":
    # O Railway gerencia a porta automaticamente pela variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
