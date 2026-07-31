from flask import Flask, jsonify, Response
import os
import requests
from bs4 import BeautifulSoup
import time
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"status": "online", "message": "API Ycine Ativa - Versão Categorias"})

# Função principal que extrai canais de cada página individual
def fetch_page(session, url, serv_label, serv_id, category_name="Ycine TV LIVE"):
    canais_da_pagina = []
    try:
        # Tenta a requisição até 2 vezes para garantir estabilidade
        for _ in range(2):
            try:
                r = session.get(url, timeout=20)
                if r.status_code == 200:
                    break
                time.sleep(1)
            except:
                time.sleep(1)
                continue
        else:
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        # Termos a serem ignorados (menus e botões sociais)
        menu_items = ['início', 'filmes', 'séries', 'minha conta', 'sair', 'contato', 'termos', 'editar conta']

        for a in soup.find_all('a', href=True):
            href = a['href']

            # Captura apenas links que levam a reprodutores de canais
            if '/canais/' in href or '/play/' in href:
                # Ignora botões de navegação pura
                if any(x in href for x in ['/canais/categorias', 'page=']) and '/categoria/' not in href:
                    continue

                nome = a.get_text(strip=True)
                logo = ""
                img = a.find('img')
                if img:
                    # Captura o ícone/logotipo do canal
                    logo = img.get('src') or img.get('data-src') or ""
                    if not nome:
                        # Fallback: se não houver texto, tenta pegar o nome do atributo alt da imagem
                        nome = img.get('alt') or img.get('title') or ""

                if not nome or any(menu == nome.lower() for menu in menu_items):
                    continue

                # Garante que a URL seja completa
                full_url = href if href.startswith('http') else f"https://app.pobreflix2.site{href}"

                # Injeta os parâmetros de servidor e tema na URL do canal
                if 'server=' not in full_url:
                    sep = '&' if '?' in full_url else '?'
                    full_url = f"{full_url}{sep}server={serv_id}&thema=1"
                elif 'thema=' not in full_url:
                    full_url = f"{full_url}&thema=1"

                canais_da_pagina.append({
                    "nome": f"{nome} ({serv_label})",
                    "url": full_url,
                    "logo": logo,
                    "category": category_name,
                    "chave": f"{serv_id}-{href.split('?')[0]}"
                })
    except:
        pass
    return canais_da_pagina

@app.route('/canais')
def get_canais():
    try:
        # Cabeçalhos para simular acesso real
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://app.pobreflix2.site/',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8'
        }

        session = requests.Session()
        session.headers.update(headers)

        # 1. DESCOBRIR CATEGORIAS REAIS DO SITE (Esportes, Infantil, etc.)
        categorias_reais = []
        try:
            r_cat = session.get("https://app.pobreflix2.site/canais/categorias/?thema=1&server=speed-1", timeout=15)
            soup_cat = BeautifulSoup(r_cat.text, 'html.parser')
            for a_cat in soup_cat.find_all('a', href=True):
                if '/categoria/' in a_cat['href']:
                    cat_name = a_cat.get_text(strip=True)
                    cat_url = a_cat['href'].split('?')[0]
                    if cat_name and len(cat_name) > 2:
                        categorias_reais.append({"name": cat_name, "path": cat_url})
        except:
            pass

        servidores = [
            {"id": "speed-1", "label": "S1"},
            {"id": "speed-2", "label": "S2"},
            {"id": "speed-3", "label": "S3"}
        ]

        # 2. ESCANEAMENTO EM MASSA (Lista Geral + Todas as Categorias)
        all_tasks = []
        with ThreadPoolExecutor(max_workers=20) as executor:
            for serv in servidores:
                # Varre a Lista Geral (10 primeiras páginas)
                for page in range(1, 11):
                    url = f"https://app.pobreflix2.site/canais?page={page}&thema=1&server={serv['id']}"
                    all_tasks.append(executor.submit(fetch_page, session, url, serv['label'], serv['id'], "Geral"))

                # Varre cada Categoria Real encontrada (5 páginas por categoria)
                for cat in categorias_reais:
                    for page in range(1, 6):
                        url_cat = f"https://app.pobreflix2.site{cat['path']}?page={page}&thema=1&server={serv['id']}"
                        all_tasks.append(executor.submit(fetch_page, session, url_cat, serv['label'], serv['id'], cat['name']))

        # 3. GERAÇÃO DO ARQUIVO M3U
        links_vistos = set()
        m3u_content = "#EXTM3U\n"
        count = 0
        
        results = []
        for task in all_tasks:
            results.extend(task.result())

        # Ordena a lista por categoria para organizar o player de IPTV
        results.sort(key=lambda x: x['category'])

        for canal in results:
            if canal['chave'] not in links_vistos:
                links_vistos.add(canal['chave'])
                logo_attr = f' tvg-logo="{canal["logo"]}"' if canal["logo"] else ""
                # group-title cria as pastas de categorias no seu player
                m3u_content += f'#EXTINF:-1{logo_attr} group-title="{canal["category"]}",{canal["nome"]}\n{canal["url"]}\n'
                count += 1

        # Comentário de verificação no final da lista
        m3u_content += f"\n# TOTAL DE CANAIS CAPTURADOS: {count}\n"
        return Response(m3u_content, mimetype='text/plain')

    except Exception as e:
        return f"Erro ao gerar lista: {str(e)}", 500

if __name__ == "__main__":
    # O Railway fornece a porta via variável de ambiente PORT
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
