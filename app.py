import os
import json
import numpy as np
import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI

# 1. Configuración de la página
st.set_page_config(page_title="UEP! Smart Search", page_icon="🕷️")

st.title("🕷️ UEP! Smart Search")
st.write("El cercador cultural intel·ligent de Mallorca (Motor Vectorial RAG).")

# 2. Cargar clave de OpenAI
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# 3. Cargar la base de datos vectorial (con caché para máxima velocidad)
@st.cache_data
def carregar_hemeroteca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as arxiu:
        dades = json.load(arxiu)
    # Convertimos la lista de vectores en una matriz de numpy para cálculos ultrarrápidos
    matriu_vectors = np.array([a["vector"] for a in dades])
    return dades, matriu_vectors

articles, matriu_vectors = carregar_hemeroteca()

# 4. Función matemática para buscar los K artículos más parecidos por significado
def cercar_articles_semantics(pregunta, top_k=5):
    # Convertimos la pregunta del usuario en un vector
    resposta_emb = client.embeddings.create(
        model="text-embedding-3-small",
        input=pregunta
    )
    vector_pregunta = np.array(resposta_emb.data[0].embedding)
    
    # Calculamos la similitud del coseno frente a todos los artículos a la vez
    norma_articles = np.linalg.norm(matriu_vectors, axis=1)
    norma_pregunta = np.linalg.norm(vector_pregunta)
    similituds = np.dot(matriu_vectors, vector_pregunta) / (norma_articles * norma_pregunta)
    
    # Obtenemos los índices de los 'top_k' artículos con mayor puntuación
    millors_indexs = np.argsort(similituds)[::-1][:top_k]
    
    resultats = []
    for idx in millors_indexs:
        resultats.append((articles[idx], float(similituds[idx])))
    return resultats

# 5. Interfaz de búsqueda
pregunta = st.text_input("Què vols saber de l'actualitat cultural?")

if st.button("Cercar"):
    if pregunta:
        with st.spinner("Cercant semànticament a l'hemeroteca..."):
            # Fase 1: Recuperación vectorial (solo los 5 mejores artículos)
            top_articles = cercar_articles_semantics(pregunta, top_k=5)
            
            # Preparamos el contexto reducido para gpt-4o-mini
            context_articles = ""
            for art, puntuacio in top_articles:
                context_articles += (
                    f"- Data: {art['data']}\n"
                    f"  Títol: {art['titol']}\n"
                    f"  Resum: {art['resum']}\n"
                    f"  Enllaç: {art['enllac']}\n\n"
                )
            
            # Fase 2: Generación de la respuesta en catalán
            instruccions_sistema = f"""
            Ets l'assistent intel·ligent del diari cultural UEP! Mallorca.
            Respon a la pregunta de l'usuari utilitzant ÚNICAMENT els següents articles seleccionats de la nostra hemeroteca:
            
            {context_articles}
            
            Normes estrictes:
            1. Respon SEMPRE en català.
            2. Si cap dels articles respon a la pregunta, digues clarament que no tens aquesta informació a l'hemeroteca. NO inventis mai dades, dates ni recintes.
            3. Cita sempre els enllaços dels articles rellevants de forma natural.
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
            
            # Desplegable técnico para auditar qué artículos ha elegido el motor
            with st.expander("🔍 Veure les 5 fonts seleccionades pel motor vectorial"):
                for art, puntuacio in top_articles:
                    st.markdown(f"**{art['titol']}** ({art['data']}) — *Similitud: {puntuacio:.2f}*  \n{art['enllac']}")
    else:
        st.warning("Escriu una pregunta abans de fer clic.")