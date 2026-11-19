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

# 2. Carregar clau d'OpenAI (compatible amb Streamlit Cloud i local)
load_dotenv()
clau = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=clau)

# 3. Carregar la base de dades vectorial
@st.cache_data
def carregar_hemeroteca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as arxiu:
        dades = json.load(arxiu)
    matriu_vectors = np.array([a["vector"] for a in dades])
    return dades, matriu_vectors

articles, matriu_vectors = carregar_hemeroteca()

# 4. Cerca equilibrada (fins a 10 notícies + fins a 8 entrades)
def cercar_articles_semantics(pregunta, max_noticies=10, max_entrades=8, llindar_minim=0.18):
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=pregunta
    )
    vector_pregunta = np.array(resposta_emb.data[0].embedding)
    
    norma_articles = np.linalg.norm(matriu_vectors, axis=1)
    norma_pregunta = np.linalg.norm(vector_pregunta)
    similituds = np.dot(matriu_vectors, vector_pregunta) / (norma_articles * norma_pregunta)
    
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

# 5. Interfície de cerca
pregunta = st.text_input("Què vols saber? (Ex: concerts a Palma, teatre aquest cap de setmana, exposicions...)")

if st.button("Cercar"):
    if pregunta:
        with st.spinner("Cercant a l'hemeroteca i a la taquilla..."):
            top_articles = cercar_articles_semantics(pregunta, max_noticies=10, max_entrades=8, llindar_minim=0.18)
            data_avui = datetime.now().strftime("%d/%m/%Y")
            
            if not top_articles:
                st.info("No hem trobat cap notícia ni entrada relacionada amb aquesta cerca.")
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
                        context_articles += (
                            f"- [📰 NOTÍCIA] (Publicada el {art['data']})\n"
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
                2. FILTRE ESTRICTE DE DATES (MOLT IMPORTANT): Compara sempre les dates reals de l'esdeveniment que surten al resum amb la data d'AVUI ({data_avui}).
                   - IGNORA paraules relatives escrites en el passat com "els propers dies", "aquest cap de setmana" o "demà" si el dia concret ja és anterior a {data_avui}.
                   - Si una funció va ser abans d'avui (per exemple, del 7 al 9 de novembre o el 14 i 15 de novembre quan avui és {data_avui}), DESCARTA-LA completament.
                   - En canvi, la data entre parèntesis "(Publicada el ...)" és només quan es va publicar l'article: si el resum diu que un cicle o obra dura fins a una data futura o és a partir d'avui, INCLOU-LA.
                3. RIGOR TEMÀTIC: Inclou només notícies el tema principal de les quals sigui el que demana l'usuari. Descarta notícies genèriques que només mencionin el tema de passada.
                4. RIGOR GEOGRÀFIC: Si l'usuari demana un municipi concret (ex: Palma), inclou els elements d'aquest municipi (incloent espais coneguts de Palma com Teatre del Mar, Teatre Principal, Teatre Sans, Espai el Tub, etc.). NO incloguis esdeveniments d'altres municipis ni inventis la ubicació si no consta.
                5. ENTRADES AMB "DIVERSES DATES": Inclou sempre les entrades que diguin "Diverses dates" si coincideixen amb el tema i el municipi.
                6. FORMAT NET I CONCÍS: Separa la resposta en dos blocs si hi ha contingut per a tots dos: **Actualitat i notícies (📰)** i **Entrades disponibles a la taquilla (🎟️)**. Utilitza UN SOL punt de llista per cada element (títol en negreta, dades essencials i l'enllaç al final). No repeteixis frases genèriques com "Esdeveniment amb venda d'entrades disponible...".
                """
                
                resposta = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": instruccions_sistema},
                        {"role": "user", "content": pregunta}
                    ]
                )
                
                st.success("Resposta trobada!")
                st.write(resposta.choices[0].message.content)
                
                with st.expander("🔍 Veure les fonts analitzades"):
                    for art, puntuacio in top_articles:
                        icona = "🎟️" if art.get("tipus") == "entrada" else "📰"
                        st.markdown(f"{icona} **{art['titol']}** ({art['data']}) — *Similitud: {puntuacio:.2f}*  \n{art['enllac']}")
    else:
        st.warning("Escriu una pregunta abans de fer clic.")