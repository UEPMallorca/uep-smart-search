import os
import re
import json
import argparse
import requests
from datetime import datetime, timedelta
from openai import OpenAI

# 1. Filtro estricto para excluir Eivissa, Formentera y Menorca
PALABRAS_EXCLUIDAS = [
    "eivissa", "ibiza", "formentera", "menorca",
    "maó", "mahón", "mahon", "ciutadella", "alaior", "es mercadal",
    "ferreries", "sant lluís", "sant lluis", "es castell", "es migjorn",
    "sant antoni de portmany", "santa eulària", "santa eularia",
    "sant josep de sa talaia", "sant joan de labritja"
]

def es_de_mallorca(evento):
    texto = f"{evento.get('titol', '')} {evento.get('resum', '')} {evento.get('enllac', '')}".lower()
    return not any(re.search(rf"\b{re.escape(p)}\b", texto) for p in PALABRAS_EXCLUIDAS)

def cargar_entradas_mallorca():
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as f:
        datos = json.load(f)
    return [a for a in datos if a.get("tipus") == "entrada" and es_de_mallorca(a)]

def configurar_formato(tipo):
    hoy = datetime.now()
    if tipo == "sabado":
        dias = (5 - hoy.weekday()) % 7
        fecha_obj = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del dissabte {fecha_obj.strftime('%d/%m/%Y')} a Mallorca",
            f"Selecciona ÚNICAMENT els esdeveniments que tinguin lloc el dissabte {fecha_obj.strftime('%d/%m/%Y')} (o cicles actius amb funció aquell dia). Descarta qualsevol altra data."
        )
    elif tipo == "domingo":
        dias = (6 - hoy.weekday()) % 7
        fecha_obj = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del diumenge {fecha_obj.strftime('%d/%m/%Y')} a Mallorca",
            f"Selecciona ÚNICAMENT els esdeveniments que tinguin lloc el diumenge {fecha_obj.strftime('%d/%m/%Y')} (o cicles actius amb funció aquell dia). Descarta qualsevol altra data."
        )
    elif tipo == "conciertos_semana":
        fin = hoy + timedelta(days=6)
        return (
            f"Concerts de la setmana a Mallorca ({hoy.strftime('%d/%m')} - {fin.strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT concerts i esdeveniments musicals que tinguin lloc entre el {hoy.strftime('%d/%m/%Y')} i el {fin.strftime('%d/%m/%Y')}. Descarta teatre, exposicions o altres disciplines."
        )
    elif tipo == "teatro_semana":
        fin = hoy + timedelta(days=6)
        return (
            f"Teatre de la setmana a Mallorca ({hoy.strftime('%d/%m')} - {fin.strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT obres de teatre, arts escèniques, monòlegs o dansa que tinguin lloc entre el {hoy.strftime('%d/%m/%Y')} i el {fin.strftime('%d/%m/%Y')}. Descarta concerts o altres disciplines."
        )
    raise ValueError("Tipus no vàlid")

def redactar_noticia(tipo, entradas):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    titulo_borrador, instruccion_filtro = configurar_formato(tipo)
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    listado = ""
    for e in entradas:
        listado += (
            f"- Títol: {e.get('titol')}\n"
            f"  Resum/Detalls: {e.get('resum')}\n"
            f"  Enllaç entrades: {e.get('enllac')}\n\n"
        )

    prompt_sistema = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
La data d'AVUI és: {fecha_hoy}.

OBJECTIU: {instruccion_filtro}

REGLES ESTRICTES DE REDACCIÓ I SEO D'UEP! MALLORCA:
1. Redacta en català amb piràmide invertida, frases curtes, dinàmiques i vocabulari precís. Sense llenguatge institucional, sense adjectius valoratius ni primera persona.
2. RIGOR ABSOLUT: Fes servir ÚNICAMENT les dades proporcionades a la llista. NO inventis hores, preus, recintes ni artistes. Respecta els noms propis i títols originals sense traduir-los.
3. Si un esdeveniment és d'Eivissa, Menorca o Formentera, DESCARTA'L completament.
4. FORMAT HTML NET PER A WORDPRESS (sense etiqueta <html> ni <body>):
   - Primer paràgraf (lead) amb les 5W i la paraula clau principal de forma natural.
   - Divideix l'article només amb subtítols <h2> (mai <h3> ni <h4>), descriptius i orientats a cerca.
   - Aplica <strong> exclusivament a noms clau, municipis, espais culturals de Mallorca i dates rellevants.
   - Enllaça cada esdeveniment a la seva URL d'entrades (<a href="...">entrades disponibles aquí</a>).
   - Al final de l'article en català, afegeix un <h2>Dades pràctiques</h2> amb llista <ul><li> amb les dades essencials (data, hora, lloc i preu només si consten).
5. DESPRÉS DE L'ARTICLE (separat per <hr>), afegeix un bloc de notes per a redacció (per esborrar abans de publicar) que contingui:
   - 3 propostes de titular (màx. 60 caràcters): 1) Periodístic, 2) Google Discover, 3) SEO.
   - Meta descripció (màx. 140 caràcters).
   - Posts per a xarxes socials: Threads i Bluesky (màx. 280 caràcters), Instagram i Facebook (natural, sense "llegeix més", 3-4 hashtags locals).
   - Versió íntegra adaptada al castellà (amb titular i meta descripció).

Si no hi ha cap esdeveniment a la llista que encaixi amb el filtre de dates i disciplina, respon ÚNICAMENT amb la paraula: SENSE_ESDEVENIMENTS
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": f"Llista d'esdeveniments disponibles a entradas.uepmallorca.app:\n\n{listado}"}
        ]
    )
    return titulo_borrador, respuesta.choices[0].message.content.strip()

def enviar_borrador_wordpress(titulo, contenido_html):
    url = "https://uepmallorca.app/wp-json/wp/v2/posts"
    auth = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])
    payload = {
        "title": f"[ESBORRANY IA] {titulo}",
        "content": contenido_html,
        "status": "draft"
    }
    resp = requests.post(url, auth=auth, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Esborrany creat correctament! ID: {resp.json().get('id')}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tipus", required=True, choices=["sabado", "domingo", "conciertos_semana", "teatro_semana"])
    args = parser.parse_args()

    entradas = cargar_entradas_mallorca()
    titulo, html = redactar_noticia(args.tipus, entradas)

    if html == "SENSE_ESDEVENIMENTS":
        print("No s'han trobat esdeveniments per a aquest filtre. No s'ha creat cap esborrany.")
    else:
        enviar_borrador_wordpress(titulo, html)
