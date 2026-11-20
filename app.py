import os
import json
from datetime import datetime
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# 1. Configuració de la pàgina
st.set_page_config(page_title="UEP! Smart Search", page_icon="🕷️")

st.title("🕷️ UEP! Smart Search")
st.write("El cercador cultural intel·ligent de Mallorca (Hemeroteca i Taquilla).")

# 2. Client d'OpenAI en memòria cau (reutilitza la connexió)
@st.cache_resource
def obtenir_client():
    load_dotenv()
    clau = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
    return OpenAI(api_key=clau)

client = obtenir_client()

# 3. Carregar i pre-normalitzar la base de dades vectorial un sol cop
@st.cache_data
def carregar_hemeroteca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as arxiu:
        dades = json.load(arxiu)
    matriu = np.array([a["vector"] for a in dades], dtype=np.float32)
    normes = np.linalg.norm(matriu, axis=1, keepdims=True)
    matriu_normalitzada = matriu / np.maximum(normes, 1e-10)
    return dades, matriu_normalitzada

articles, matriu_normalitzada = carregar_hemeroteca()

# 4. Memòria cau d'embeddings (1 hora) per a cerques repetides
@st.cache_data(ttl=3600, show_spinner=False)
def obtenir_embedding_pregunta(text):
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=text.strip().lower()
    )
    v = np.array(resposta_emb.data[0].embedding, dtype=np.float32)
    return v / np.maximum(np.linalg.norm(v), 1e-10)

# 5. Cerca equilibrada (8 notícies + 6 entrades)
def cercar_articles_semantics(pregunta, max_noticies=8, max_entrades=6, llindar_minim=0.18):
    vector_pregunta = obtenir_embedding_pregunta(pregunta)
    similituds = np.dot(matriu_normalitzada, vector_pregunta)
    indexs_ordenats = np.argsort(similituds)[::-1]

    noticies_sel = []
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
            if len(noticies_sel) < max_noticies:
                noticies_sel.append((art, puntuacio))

        if len(noticies_sel) >= max_noticies and len(entrades_sel) >= max_entrades:
            break

    return noticies_sel + entrades_sel

# 6. Interfície de cerca (amb suport per a búsquedes directes des d'uepmallorca.app)
pregunta_url = st.query_params.get("q", "")
pregunta = st.text_input(
    "Què vols saber? (Ex: concerts a Palma, teatre aquest cap de setmana, exposicions...)",
    value=pregunta_url
)