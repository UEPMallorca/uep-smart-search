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

# 4. Cerca semàntica equilibrada (sempre combina notícies i entrades)
def cercar_articles_semantics(pregunta, top_noticies=7, top_entrades=5):
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
        art = articles[idx]
        puntuacio = float(similituds[idx])
        if art.get("tipus") == "entrada":
            if len(entrades_sel) < top_entrades:
                entrades_sel.append((art, puntuacio))
        else:
            if len(noticies_sel) < top_noticies:
                noticies_sel.append((art, puntuacio))
        
        if len(noticies_sel) >= top_noticies and len(entrades_sel) >= top_entrades:
            break
            
    # Retornam primer les entrades i després les notícies
    return entrades_sel + noticies_sel

# 5. Interfície de cerca
pregunta = st.text_input("Què vols saber? (Ex: concerts a Palma, teatre aquest cap de setmana, exposicions...)")

if st.button("Cercar"):
    if pregunta:
        with st.spinner("Cercant a l'hemeroteca i a la taquilla..."):
            top_articles = cercar_articles_semantics(pregunta, top_noticies=7, top_entrades=5)
            data_avui = datetime.now().strftime("%d/%m/%Y")
            
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
            
            Respon a la pregunta de l'usuari utilitzant ÚNICAMENT els següents elements de la nostra hemeroteca i taquilla:
            
            {context_articles}
            
            Normes estrictes:
            1. Respon SEMPRE en català, amb un to clar, pràctic i periodístic.
            2. Si l'usuari fa una pregunta general o d'agenda (com "concerts a Palma", "teatre aquest cap de setmana", "què fer a Mallorca"), ofereix una llista clara i ordenada amb les millors opcions disponibles, prioritzant els esdeveniments pròxims i els de [🎟️ VENDA D'ENTRADES].
            3. Tingues en compte la data d'avui ({data_avui}): no recomanis esdeveniments que ja han passat com si fossin futurs. Si només tens notícies antigues sobre el tema, aclareix-ho.
            4. Si cap dels elements respon a la pregunta, digues clarament que no tens aquesta informació. NO inventis mai dades, dates, preus ni recintes.
            5. Cita sempre els enllaços rellevants de forma natural, destacant clarament l'enllaç directe de compra quan es tracti de [🎟️ VENDA D'ENTRADES].
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
            
            with st.expander("🔍 Veure les fonts seleccionades (Taquilla + Hemeroteca)"):
                for art, puntuacio in top_articles:
                    icona = "🎟️" if art.get("tipus") == "entrada" else "📰"
                    st.markdown(f"{icona} **{art['titol']}** ({art['data']}) — *Similitud: {puntuacio:.2f}*  \n{art['enllac']}")
    else:
        st.warning("Escriu una pregunta abans de fer clic.")