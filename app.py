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

# 4. Cerca semàntica pura (sense forçar entrades irrellevants)
def cercar_articles_semantics(pregunta, top_k=10, llindar_minim=0.32):
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=pregunta
    )
    vector_pregunta = np.array(resposta_emb.data[0].embedding)
    
    norma_articles = np.linalg.norm(matriu_vectors, axis=1)
    norma_pregunta = np.linalg.norm(vector_pregunta)
    similituds = np.dot(matriu_vectors, vector_pregunta) / (norma_articles * norma_pregunta)
    
    indexs_ordenats = np.argsort(similituds)[::-1]
    
    resultats = []
    for idx in indexs_ordenats[:top_k]:
        puntuacio = float(similituds[idx])
        if puntuacio >= llindar_minim:
            resultats.append((articles[idx], puntuacio))
    return resultats

# 5. Interfície de cerca
pregunta = st.text_input("Què vols saber? (Ex: concerts a Palma, teatre aquest cap de setmana, exposicions...)")

if st.button("Cercar"):
    if pregunta:
        with st.spinner("Cercant a l'hemeroteca i a la taquilla..."):
            top_articles = cercar_articles_semantics(pregunta, top_k=10, llindar_minim=0.32)
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
                2. FILTRE ESTRICTE DE TEMA I LLOC: Inclou NOMÉS els elements que coincideixin realment amb el que demana l'usuari. Si demana "Teatre a Palma", NO incloguis concerts, xerrades ni esdeveniments d'altres municipis com Manacor, encara que apareguin a la llista. Descarta tot el que no encaixi.
                3. EQUILIBRI: Tracta notícies i entrades per igual segons la seva rellevància. No prioritzis una entrada si una notícia respon millor.
                4. Tingues en compte la data d'avui ({data_avui}): no recomanis esdeveniments ja passats com si fossin futurs.
                5. Si cap element encaixa realment amb el tema i el lloc demanats, digues clarament que no tens aquesta informació ara mateix. NO omplis la resposta amb temes diferents ni inventis dades.
                6. Cita els enllaços de forma natural (i indica si és per llegir la notícia o per comprar entrades).
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