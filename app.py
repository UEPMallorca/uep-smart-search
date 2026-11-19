import os
import json
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# 1. Configuración de la página
st.set_page_config(page_title="UEP! Smart Search", page_icon="🕷️")

st.title("🕷️ UEP! Smart Search")
st.write("El cercador cultural intel·ligent de Mallorca (Hemeroteca i Taquilla).")

# 2. Cargar clave de OpenAI (compatible con Streamlit Cloud y local)
load_dotenv()
clau = st.secrets.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=clau)

# 3. Cargar la base de datos vectorial
@st.cache_data
def carregar_hemeroteca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as arxiu:
        dades = json.load(arxiu)
    matriu_vectors = np.array([a["vector"] for a in dades])
    return dades, matriu_vectors

articles, matriu_vectors = carregar_hemeroteca()

# 4. Búsqueda semántica vectorial
def cercar_articles_semantics(pregunta, top_k=5):
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=pregunta
    )
    vector_pregunta = np.array(resposta_emb.data[0].embedding)
    
    norma_articles = np.linalg.norm(matriu_vectors, axis=1)
    norma_pregunta = np.linalg.norm(vector_pregunta)
    similituds = np.dot(matriu_vectors, vector_pregunta) / (norma_articles * norma_pregunta)
    
    millors_indexs = np.argsort(similituds)[::-1][:top_k]
    
    resultats = []
    for idx in millors_indexs:
        resultats.append((articles[idx], float(similituds[idx])))
    return resultats

# 5. Interfaz de búsqueda
pregunta = st.text_input("Què vols saber de l'actualitat cultural o d'entrades a Mallorca?")

if st.button("Cercar"):
    if pregunta:
        with st.spinner("Cercant a l'hemeroteca i a la taquilla..."):
            top_articles = cercar_articles_semantics(pregunta, top_k=5)
            
            # PRIMERO construimos el contexto diferenciando noticias y entradas
            context_articles = ""
            for art, puntuacio in top_articles:
                etiqueta = "🎟️ VENDA D'ENTRADES" if art.get("tipus") == "entrada" else "📰 NOTÍCIA"
                context_articles += (
                    f"- [{etiqueta}] Data: {art['data']}\n"
                    f"  Títol: {art['titol']}\n"
                    f"  Resum: {art['resum']}\n"
                    f"  Enllaç: {art['enllac']}\n\n"
                )
            
            # DESPUÉS insertamos ese contexto en las instrucciones
            instruccions_sistema = f"""
            Ets l'assistent intel·ligent del diari cultural UEP! Mallorca.
            Respon a la pregunta de l'usuari utilitzant ÚNICAMENT els següents elements seleccionats de la nostra hemeroteca i taquilla:
            
            {context_articles}
            
            Normes estrictes:
            1. Respon SEMPRE en català.
            2. Si cap dels elements respon a la pregunta, digues clarament que no tens aquesta informació. NO inventis mai dades, dates ni recintes.
            3. Cita sempre els enllaços rellevants de forma natural.
            4. Si entre les fonts hi ha un element de [🎟️ VENDA D'ENTRADES] relacionat amb la consulta, destaca-ho clarament i facilita l'enllaç directe per comprar les entrades.
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
            
            with st.expander("🔍 Veure les 5 fonts seleccionades pel motor vectorial"):
                for art, puntuacio in top_articles:
                    icona = "🎟️" if art.get("tipus") == "entrada" else "📰"
                    st.markdown(f"{icona} **{art['titol']}** ({art['data']}) — *Similitud: {puntuacio:.2f}*  \n{art['enllac']}")
    else:
        st.warning("Escriu una pregunta abans de fer clic.")