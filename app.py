import os
import re
import html
import json
from datetime import datetime
import numpy as np
import requests
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# 1. Configuració de la pàgina
st.set_page_config(page_title="UEP! Smart Search", page_icon="🕷️")

st.title("🕷️ UEP! Smart Search")
st.write("El cercador cultural intel·ligent de Mallorca (Hemeroteca completa i Taquilla).")

# Paraules buides per netejar preguntes llargues abans de consultar WordPress
STOPWORDS = {
    "el", "la", "els", "les", "un", "una", "uns", "unes", "de", "del", "dels",
    "a", "al", "als", "en", "amb", "per", "però", "que", "què", "qui", "quin",
    "quins", "quina", "quines", "com", "quan", "on", "hi", "ha", "és", "són",
    "aquest", "aquesta", "aquests", "aquestes", "avui", "demà", "setmana",
    "los", "las", "con", "por", "para", "del", "qué", "quién", "cuál", "cuándo",
    "dónde", "hay", "este", "esta", "estos", "estas", "hoy", "mañana", "semana",
    "sobre", "vols", "vull", "saber", "notícies", "noticias", "articles", "artículos"
}

# 2. Client d'OpenAI en memòria cau
@st.cache_resource
def obtenir_client():
    load_dotenv()
    clau = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=clau)

client = obtenir_client()

# 3. Carregar i pre-normalitzar la base de dades vectorial
@st.cache_data
def carregar_hemeroteca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as arxiu:
        dades = json.load(arxiu)
    matriu = np.array([a["vector"] for a in dades], dtype=np.float32)
    normes = np.linalg.norm(matriu, axis=1, keepdims=True)
    matriu_normalitzada = matriu / np.maximum(normes, 1e-10)
    return dades, matriu_normalitzada

articles, matriu_normalitzada = carregar_hemeroteca()

# 4. Memòria cau d'embeddings (1 hora)
@st.cache_data(ttl=3600, show_spinner=False)
def obtenir_embedding_pregunta(text):
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=text.strip().lower()
    )
    v = np.array(resposta_emb.data[0].embedding, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v), 1e-10)

# 5. Utilitats per a la cerca en directe a l'hemeroteca de WordPress (15.000+ notícies)
def netejar_html(text):
    sense_etiquetes = re.sub(r"<[^>]+>", " ", text or "")
    return re.sub(r"\s+", " ", html.unescape(sense_etiquetes)).strip()

def extreure_paraules_clau(pregunta):
    paraules = re.findall(r"[\wÀ-ÿ'-]+", pregunta.lower())
    filtrades = [p for p in paraules if len(p) > 2 and p not in STOPWORDS]
    return " ".join(filtrades[:5])

def _consultar_api_wp(terme, max_resultats):
    url = "https://uepmallorca.app/wp-json/wp/v2/posts"
    params = {
        "search": terme,
        "per_page": max_resultats,
        "status": "publish",
        "_fields": "title,excerpt,link,date"
    }
    headers = {"User-Agent": "Mozilla/5.0 (compatible; UEPSmartSearch/1.0)"}
    r = requests.get(url, params=params, headers=headers, timeout=10)
    if r.status_code != 200:
        return []
    return r.json()

@st.cache_data(ttl=600, show_spinner=False)
def cercar_hemeroteca_wp(pregunta, max_resultats=10):
    try:
        terme = pregunta.strip()
        posts = _consultar_api_wp(terme, max_resultats)

        # Si la pregunta és una frase llarga i WP no troba coincidència exacta, reintentam amb paraules clau
        if not posts:
            claus = extreure_paraules_clau(terme)
            if claus and claus != terme.lower():
                posts = _consultar_api_wp(claus, max_resultats)

        resultats = []
        for p in posts:
            data_iso = p.get("date", "")[:10]
            try:
                data_fmt = datetime.strptime(data_iso, "%Y-%m-%d").strftime("%d/%m/%Y")
            except ValueError:
                data_fmt = data_iso

            resultats.append((
                {
                    "titol": netejar_html(p.get("title", {}).get("rendered", "")),
                    "resum": netejar_html(p.get("excerpt", {}).get("rendered", ""))[:400],
                    "enllac": p.get("link", ""),
                    "data": data_fmt,
                    "tipus": "noticia_wp"
                },
                None  # Sense puntuació vectorial (resultat directe de l'hemeroteca WP)
            ))
        return resultats
    except Exception:
        return []

# 6. Cerca híbrida: WordPress en directe + Vectors semàntics + Taquilla
def cercar_hibrid(pregunta, max_wp=10, max_noticies_vec=6, max_entrades=6, llindar_minim=0.18, nomes_entrades=False):
    vector_pregunta = obtenir_embedding_pregunta(pregunta)
    similituds = np.dot(matriu_normalitzada, vector_pregunta)
    indexs_ordenats = np.argsort(similituds)[::-1]

    if nomes_entrades:
        max_wp = 0
        max_noticies_vec = 0
        max_entrades = 10

    # A) Resultats en directe de tota l'hemeroteca de WordPress
    resultats_wp = cercar_hemeroteca_wp(pregunta, max_resultats=max_wp) if max_wp > 0 else []

    # B) Resultats semàntics i entrades de taquilla
    noticies_vec = []
    entrades_sel = []

    for idx in indexs_ordenats:
        puntuacio = float(similituds[idx])
        if puntuacio < llindar_minim:
            break

        art = articles[idx]
        if art.get("tipus") == "entrada":
            if len(entrades_sel) < max_entrades:
                entrades_sel.append((art, puntuacio))
        else:
            if len(noticies_vec) < max_noticies_vec:
                noticies_vec.append((art, puntuacio))

        if len(noticies_vec) >= max_noticies_vec and len(entrades_sel) >= max_entrades:
            break

    # C) Fusió sense duplicats per URL (prioritzant WP i taquilla)
    combinats = []
    urls_vistes = set()

    for art, punt in resultats_wp + noticies_vec + entrades_sel:
        url_neta = art.get("enllac", "").rstrip("/").lower()
        if url_neta and url_neta in urls_vistes:
            continue
        if url_neta:
            urls_vistes.add(url_neta)
        combinats.append((art, punt))

    return combinats

# 7. Estat inicial (suport per a ?q= des d'uepmallorca.app i botons ràpids)
pregunta_url = st.query_params.get("q", "")

if "pregunta_input" not in st.session_state:
    st.session_state.pregunta_input = pregunta_url
if "nomes_entrades" not in st.session_state:
    st.session_state.nomes_entrades = False
if "llancar_cerca" not in st.session_state:
    st.session_state.llancar_cerca = bool(pregunta_url)

def seleccionar_xip