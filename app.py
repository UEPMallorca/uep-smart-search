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

# 4. Cerca equilibrada AMB filtre de qualitat (ni tapa la taquilla ni posa farciment)
def cercar_articles_semantics(pregunta, max_noticies=5, max_entrades=5, llindar_minim=0.33):
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
        # Si ja baixam del llindar mínim, aturam la cerca (evita farciment irrellevant)
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
            top_articles = cercar_articles_semantics(pregunta, max_noticies=5, max_entrades=5, llindar_minim=0.33)
            data_avui = datetime.now().strftime("%d/%m/%Y")
            
            if not top_articles:
                st.info("No hem trobat cap notícia ni entrada relacionada amb aquesta cerca.")
            else:
                context_articles = ""
                for art, puntuacio in top_articles:
                    etiqueta = "🎟️ VENDA D'ENTRADES" if art.get("tipus") == "entrada" else "📰 NOTÍCIA"
                    context_articles += (
                        f"- [{etiqueta}] Data: {art['data']}\n"
                        f"  Títol: {art['titol']}\n"
                        f"  Resum: {art['resum']}\n"
                        f"  Enllaç: {art['enllac']}\n\n"
                    )
                
                instruccions_sistema = f"""
                Ets l'assistent cultural intel·ligent del diari UEP! Mallorca.
                La data d'avui és: {data_avui}.
                
                Respon a la pregunta de l'usuari utilitzant ÚNICAMENT els elements pertinents d'aquesta llista:
                
                {context_articles}
                
                Normes estrictes:
                1. Respon SEMPRE en català, amb un to clar, pràctic i periodístic.
                2. FILTRE ESTRICTE DE TEMA I LLOC: Inclou NOMÉS els elements que coincideixin realment amb el tema i el municipi demanats. Si l'usuari demana "Teatre a Palma", descarta esdeveniments d'altres municipis (com Inca, Calvià o Manacor) i altres disciplines.
                3. ORGANITZACIÓ CLARA: Si hi ha tant notícies com entrades pertinents, separa la resposta en dos blocs curts: **Actualitat i notícies** (📰) i **Entrades disponibles a la taquilla** (🎟️).
                4. DATA D'AVUI ({data_avui}): No recomanis funcions que ja han passat (anteriors a avui) com si fossin opcions actuals.
                5. Si cap element encaixa realment, digues-ho clarament. NO inventis mai dades.
                6. Cita els enllaços de forma natural.
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