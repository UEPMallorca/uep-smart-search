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
        "_fields": "title,excerpt,link,date"
    }
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "application/json"
    }
    r = requests.get(url, params=params, headers=headers, timeout=10)
    if r.status_code != 200:
        return [], f"Error WP HTTP {r.status_code}"
    return r.json(), None

@st.cache_data(ttl=600, show_spinner=False)
def cercar_hemeroteca_wp(pregunta, max_resultats=10):
    try:
        terme = pregunta.strip()
        posts, error = _consultar_api_wp(terme, max_resultats)

        # Si la pregunta és una frase llarga i WP no troba coincidència exacta, reintentam amb paraules clau
        if not posts and not error:
            claus = extreure_paraules_clau(terme)
            if claus and claus != terme.lower():
                posts, error = _consultar_api_wp(claus, max_resultats)

        if error:
            return [], error

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
                None
            ))
        return resultats, None
    except Exception as e:
        return [], str(e)

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
    if max_wp > 0:
        resultats_wp, wp_error = cercar_hemeroteca_wp(pregunta, max_resultats=max_wp)
    else:
        resultats_wp, wp_error = [], None

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

    return combinats, wp_error

# 7. Estat inicial (suport per a ?q= des d'uepmallorca.app i botons ràpids)
pregunta_url = st.query_params.get("q", "")

if "pregunta_input" not in st.session_state:
    st.session_state.pregunta_input = pregunta_url
if "nomes_entrades" not in st.session_state:
    st.session_state.nomes_entrades = False
if "llancar_cerca" not in st.session_state:
    st.session_state.llancar_cerca = bool(pregunta_url)

def seleccionar_xip(text_cerca, activar_nomes_entrades=False):
    st.session_state.pregunta_input = text_cerca
    st.session_state.nomes_entrades = activar_nomes_entrades
    st.session_state.llancar_cerca = True

# 8. Interfície: casella + botons ràpids + interruptor d'entrades
pregunta = st.text_input(
    "Què vols saber? (Ex: concerts a Palma, teatre aquest cap de setmana, entrevistes, exposicions...)",
    key="pregunta_input"
)

st.caption("Cerques ràpides:")
col1, col2, col3, col4 = st.columns(4)
with col1:
    st.button("🎭 Teatre Palma", use_container_width=True, on_click=seleccionar_xip, args=("Teatre a Palma", False))
with col2:
    st.button("🎸 Concerts", use_container_width=True, on_click=seleccionar_xip, args=("Concerts aquest cap de setmana", False))
with col3:
    st.button("🖼️ Exposicions", use_container_width=True, on_click=seleccionar_xip, args=("Exposicions a Mallorca", False))
with col4:
    st.button("🎟️ Entrades", use_container_width=True, on_click=seleccionar_xip, args=("Entrades disponibles a Mallorca", True))

nomes_entrades = st.toggle("🎟️ Només esdeveniments amb entrades disponibles", key="nomes_entrades")
cercar_clic = st.button("Cercar", type="primary")

if cercar_clic:
    st.session_state.llancar_cerca = True

if st.session_state.llancar_cerca:
    if pregunta:
        with st.spinner("Cercant a l'hemeroteca completa d'UEP! Mallorca i a la taquilla..."):
            top_articles, wp_error = cercar_hibrid(
                pregunta,
                max_wp=10,
                max_noticies_vec=6,
                max_entrades=6,
                llindar_minim=0.18,
                nomes_entrades=nomes_entrades
            )
            data_avui = datetime.now().strftime("%d/%m/%Y")

        if not top_articles:
            st.info("No hem trobat cap notícia ni entrada relacionada amb aquesta cerca.")
            if wp_error:
                st.caption(f"⚠️ Avís connexió hemeroteca WP: {wp_error}")
        else:
            context_articles = ""
            for art, puntuacio in top_articles:
                if art.get("tipus") == "entrada":
                    context_articles += (
                        f"- [🎟️ VENDA D'ENTRADES]\n"
                        f"  Títol i dades: {art['titol']}\n"
                        f"  Detalls: {art['resum']}\n"
                        f"  Enllaç: {art['enllac']}\n\n"
                    )
                else:
                    etiqueta = "📰 HEMEROTECA UEP!" if art.get("tipus") == "noticia_wp" else "📰 NOTÍCIA"
                    context_articles += (
                        f"- [{etiqueta}] (Publicada el {art['data']})\n"
                        f"  Títol: {art['titol']}\n"
                        f"  Resum: {art['resum']}\n"
                        f"  Enllaç: {art['enllac']}\n\n"
                    )

            instruccions_sistema = f"""
            Ets l'assistent cultural intel·ligent del diari UEP! Mallorca.
            La data d'AVUI és: {data_avui}.

            Respon a la pregunta de l'usuari utilitzant ÚNICAMENT els elements pertinents d'aquesta llista:

            {context_articles}

            Normes estrictes:
1. Respon SEMPRE en català, amb un to clar, pràctic i periodístic.
2. GESTIÓ INTEL·LIGENT DE DATES (MOLT IMPORTANT):
  - Si l'usuari demana AGENDA, plans propers, "aquesta setmana", "aquest cap de setmana" o esdeveniments futurs: compara les dates reals amb AVUI ({data_avui}) i DESCARTA qualsevol funció o concert ja passat.
  - Si l'usuari cerca informació d'HEMEROTECA (un artista, una entrevista, una obra, un festival o un tema general sense demanar agenda futura): INCLOU els articles històrics rellevants indicant breument quan es van publicar.
3. RIGOR TEMÀTIC: Inclou només notícies el tema principal de les quals sigui el que demana l'usuari. Descarta notícies genèriques que només mencionin el tema de passada.
4. RIGOR GEOGRÀFIC: Si l'usuari demana un municipi concret (ex: Palma), inclou els elements d'aquest municipi (incloent espais coneguts de Palma com Teatre del Mar, Teatre Principal, Teatre Sans, Espai el Tub, etc.). NO incloguis esdeveniments d'altres municipis ni inventis la ubicació si no consta.
5. ENTRADES AMB "DIVERSES DATES": Inclou sempre les entrades que diguin "Diverses dates" si coincideixen amb el tema i el municipi.
6. FORMAT NET I CONCÍS: Separa la resposta en dos blocs si hi ha contingut per a tots dos: **Actualitat i hemeroteca (📰)** i **Entrades disponibles a la taquilla (🎟️)**. Utilitza UN SOL punt de llista per cada element (títol en negreta, dades essencials i l'enllaç al final). No repeteixis frases genèriques com "Esdeveniment amb venda d'entrades disponible...".
            """

            flux_resposta = client.chat.completions.create(
                model="gpt-4o-mini",
                temperature=0.2,
                stream=True,
                messages=[
                    {"role": "system", "content": instruccions_sistema},
                    {"role": "user", "content": pregunta}
                ]
            )

            st.write_stream(flux_resposta)

            with st.expander("🔍 Veure les fonts analitzades"):
                if wp_error:
                    st.caption(f"⚠️ Avís connexió hemeroteca WP: {wp_error}")
                for art, puntuacio in top_articles:
                    icona = "🎟️" if art.get("tipus") == "entrada" else "📰"
                    origen = "Hemeroteca WP" if puntuacio is None else f"Similitud: {puntuacio:.2f}"
                    st.markdown(f"{icona} **{art['titol']}** ({art['data']}) — *{origen}*  \n{art['enllac']}")
    else:
        st.warning("Escriu una pregunta abans de fer clic.")
