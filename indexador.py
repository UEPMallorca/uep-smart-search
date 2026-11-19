import os
import re
import html
import json
import requests
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import OpenAI

# 1. Carregar clau d'OpenAI
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def netejar_html(text_brut):
    sense_etiquetes = re.sub(r'<[^>]+>', '', text_brut)
    return html.unescape(sense_etiquetes).strip()

# Capçalera de navegador per evitar bloquejos tant a WordPress com a la taquilla
headers_chrome = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept-Language": "ca-ES,ca;q=0.9,es;q=0.8",
    "Accept": "application/json, text/html, */*"
}

tots_els_items = []

# ==========================================
# BLOC A: NOTÍCIES D'UEP! MALLORCA (WP)
# ==========================================
PAGINES_A_DESCARREGAR = 3
print(f"1/3. Descarregant {PAGINES_A_DESCARREGAR} pàgines de notícies d'UEP! Mallorca...")

for pagina in range(1, PAGINES_A_DESCARREGAR + 1):
    url = f"https://uepmallorca.app/wp-json/wp/v2/posts?per_page=100&page={pagina}"
    resposta = requests.get(url, headers=headers_chrome, timeout=20)
    if resposta.status_code != 200:
        print(f"   Avís: error en descarregar pàgina {pagina} de WP (codi {resposta.status_code})")
        break
        
    for article in resposta.json():
        enllac = article['link']
        if "/es/" in enllac:
            continue
            
        tots_els_items.append({
            "tipus": "noticia",
            "categoria": "Notícia",
            "titol": netejar_html(article['title']['rendered']),
            "resum": netejar_html(article['excerpt']['rendered']),
            "data": article['date'][:10],
            "enllac": enllac
        })

noticies_trobades = len(tots_els_items)
print(f"   -> {noticies_trobades} notícies en català recollides.")

# ASSEGURANÇA ANTI-ESBORRAT: Si no entren notícies, aturam el procés per no esborrar les que ja tenim
if noticies_trobades == 0:
    raise RuntimeError("ERROR: No s'ha pogut descarregar cap notícia de WordPress. Procés aturat per seguretat.")

# ==========================================
# BLOC B: TAQUILLA (entradas.uepmallorca.app/ca)
# ==========================================
print("2/3. Descarregant tota la cartellera de entradas.uepmallorca.app/ca...")

fonts_entrades = [
    ("Teatre", "https://entradas.uepmallorca.app/ca/tag/teatro"),
    ("Concerts", "https://entradas.uepmallorca.app/ca/tag/conciertos"),
    ("Cinema", "https://entradas.uepmallorca.app/ca/tag/cine"),
    ("Festivals", "https://entradas.uepmallorca.app/ca/tag/festivales"),
    ("Restauració", "https://entradas.uepmallorca.app/ca/tag/restauracion"),
    ("Fira", "https://entradas.uepmallorca.app/ca/tag/feria"),
    ("General", "https://entradas.uepmallorca.app/ca")
]

enllacos_vistos = set()
entrades_trobades = 0

for categoria, url_cat in fonts_entrades:
    r = requests.get(url_cat, headers=headers_chrome, timeout=20)
    if r.status_code != 200:
        print(f"   Avís: no s'ha pogut llegir {categoria} (codi {r.status_code})")
        continue
        
    soup = BeautifulSoup(r.text, "html.parser")
    noves_cat = 0
    
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "/events/" in href:
            url_completa = href if href.startswith("http") else f"https://entradas.uepmallorca.app{href}"
            if url_completa in enllacos_vistos:
                continue
            enllacos_vistos.add(url_completa)
            
            text_event = " ".join(a.get_text(" ", strip=True).split())
            text_event = re.sub(r'(Des de|Desde)(\d)', r'\1 \2', text_event)
            
            tots_els_items.append({
                "tipus": "entrada",
                "categoria": categoria,
                "titol": text_event,
                "resum": f"Categoria: {categoria}. Esdeveniment amb venda d'entrades disponible a la taquilla oficial d'UEP! Mallorca.",
                "data": "Pròxim esdeveniment",
                "enllac": url_completa
            })
            entrades_trobades += 1
            noves_cat += 1
            
    print(f"   -> {categoria}: {noves_cat} esdeveniments nous.")

print(f"   Total d'esdeveniments amb entrades recollits: {entrades_trobades}")

# ==========================================
# BLOC C: GENERAR EMBEDDINGS (VECTORS)
# ==========================================
print(f"3/3. Generant vectors per a {len(tots_els_items)} elements en total...")

textos_per_vectoritzar = [
    f"Tipus: {item['tipus']}. Categoria: {item['categoria']}. Data: {item['data']}. Títol: {item['titol']}. Resum: {item['resum']}"
    for item in tots_els_items
]

resposta_embeddings = client.embeddings.create(
    model="text-embedding-3-small",
    input=textos_per_vectoritzar
)

for i, emb in enumerate(resposta_embeddings.data):
    tots_els_items[i]["vector"] = emb.embedding

with open("hemeroteca_vectors.json", "w", encoding="utf-8") as arxiu:
    json.dump(tots_els_items, arxiu, ensure_ascii=False)

print("\n✅ ¡ÈXIT TOTAL! Base de dades actualitzada amb notícies + tota la cartellera d'entrades.")