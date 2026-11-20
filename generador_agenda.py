import os
import re
import json
import argparse
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI

PALABRAS_EXCLUIDAS = [
    "eivissa", "ibiza", "formentera", "menorca",
    "maó", "mahón", "mahon", "ciutadella", "alaior", "es mercadal",
    "ferreries", "sant lluís", "sant lluis", "es castell", "es migjorn",
    "sant antoni de portmany", "santa eulària", "santa eularia",
    "sant josep de sa talaia", "sant joan de labritja"
]

MESOS_CAT = {
    1: "gener", 2: "febrer", 3: "març", 4: "abril", 5: "maig", 6: "juny",
    7: "juliol", 8: "agost", 9: "setembre", 10: "octubre", 11: "novembre", 12: "desembre"
}

def es_de_mallorca(evento):
    texto = f"{evento.get('titol', '')} {evento.get('resum', '')} {evento.get('enllac', '')}".lower()
    return not any(re.search(rf"\b{re.escape(p)}\b", texto) for p in PALABRAS_EXCLUIDAS)

def coincide_fecha(evento, fechas_objetivo):
    texto = f"{evento.get('titol', '')} {evento.get('resum', '')}".lower()
    for f in fechas_objetivo:
        patrones = [
            f.strftime("%d/%m/%Y"),
            f.strftime("%d/%m"),
            f"{f.day} de {MESOS_CAT[f.month]}",
            f"{f.day:02d} de {MESOS_CAT[f.month]}",
            f"{f.day} {MESOS_CAT[f.month][:3]}"
        ]
        if any(p in texto for p in patrones):
            return True
    return False

def extraer_ficha_web(url):
    try:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UEPMallorcaBot/1.0)"}
        r = requests.get(url, headers=headers, timeout=12)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript"]):
            tag.decompose()
        texto = soup.get_text(separator="\n", strip=True)
        lineas = [l.strip() for l in texto.splitlines() if len(l.strip()) > 2]
        return "\n".join(lineas)[:2500]
    except Exception:
        return ""

def configurar_formato(tipo):
    hoy = datetime.now()
    if tipo == "sabado":
        dias = (5 - hoy.weekday()) % 7
        f = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del dissabte {f.strftime('%d/%m/%Y')} a Mallorca",
            f"Redacta la notícia d'agenda cultural per al dissabte {f.strftime('%d/%m/%Y')} a Mallorca.",
            [f]
        )
    elif tipo == "domingo":
        dias = (6 - hoy.weekday()) % 7
        f = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del diumenge {f.strftime('%d/%m/%Y')} a Mallorca",
            f"Redacta la notícia d'agenda cultural per al diumenge {f.strftime('%d/%m/%Y')} a Mallorca.",
            [f]
        )
    elif tipo == "conciertos_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Concerts de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT concerts i música en directe entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta teatre i altres disciplines.",
            fechas
        )
    elif tipo == "teatro_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Teatre de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT teatre, dansa, monòlegs i arts escèniques entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta concerts.",
            fechas
        )
    raise ValueError("Tipus no vàlid")

def cargar_eventos_enriquecidos(fechas_objetivo):
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as f:
        datos = json.load(f)

    candidatos = [
        a for a in datos
        if a.get("tipus") == "entrada" and es_de_mallorca(a) and coincide_fecha(a, fechas_objetivo)
    ]

    enriquecidos = []
    for ev in candidatos[:15]:
        print(f"Llegint fitxa completa: {ev.get('titol')} -> {ev.get('enllac')}")
        texto_web = extraer_ficha_web(ev.get("enllac", ""))
        enriquecidos.append({
            "titol": ev.get("titol", ""),
            "resum": ev.get("resum", ""),
            "enllac": ev.get("enllac", ""),
            "fitxa_completa": texto_web
        })
    return enriquecidos

def redactar_noticia(tipo, eventos, titulo_borrador, instruccion_filtro):
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    dossier = ""
    for i, e in enumerate(eventos, 1):
        dossier += (
            f"=== ESDEVENIMENT {i} ===\n"
            f"Títol: {e['titol']}\n"
            f"Resum breu: {e['resum']}\n"
            f"Enllaç entrades: {e['enllac']}\n"
            f"TEXT COMPLET DE LA FITXA WEB:\n{e['fitxa_completa']}\n\n"
        )

    prompt_sistema = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Avui és {fecha_hoy}.
OBJECTIU: {instruccion_filtro}

REGLES INNEGOCIABLES (SI LES INCOMPLEIXES, L'ARTICLE NO SERVEIX):
1. ZERO TÒPICS NI FARCIMENT: Està TERMINANTMENT PROHIBIT escriure frases buides com "promet emocionar", "promet ser un dels esdeveniments destacats", "una experiència musical única", "un concert que no es pot perdre", "farà gaudir al públic" o "forma part de la programació". Cada frase ha d'aportar dades concretes extretes de la fitxa web (artistes, repertori, sinopsi, horari, preu, recinte, municipi).
2. ESTRUCTURA PERIODÍSTICA REAL (NO UN LLISTAT):
   - Obre amb un LEAD potent (piràmide invertida, 5W) que destaqui les cites principals de la jornada/setmana i inclogui la paraula clau principal.
   - Agrupa els esdeveniments en 2 o 3 grans blocs temàtics o geogràfics amb subtítols <h2> descriptius (ex: <h2>Jazz, lírica i música en directe a Palma i la Part Forana</h2>, <h2>Escena teatral i propostes nocturnes</h2>). NO facis un <h2> per a cada esdeveniment individual.
   - Redacta en paràgrafs (<p>) rics i enllaçats entre si, aprofitant al màxim la informació real de cada fitxa web. PROHIBIT utilitzar llistes <ul>/<li> dins el cos de la notícia.
   - Integra els enllaços de compra de forma natural dins el text (<a href="...">entrades disponibles en línia</a>).
   - Aplica <strong> només a noms clau, municipis, espais culturals i dates.
3. RIGOR ABSOLUT: No inventis mai cap dada. Respecta els noms propis i títols originals sense traduir-los (ni al català ni al castellà). Descarta qualsevol esdeveniment d'Eivissa, Menorca o Formentera.
4. CAIXA FINAL OBLIGATÒRIA: Al final de la notícia en català, posa <h2>Dades pràctiques</h2> amb una llista <ul><li> detallada, UN PUNT PER CADA ESDEVENIMENT, indicant: nom, data, hora exacta (si consta a la fitxa), recinte i municipi, preu (si consta) i enllaç.
5. BLOC DE REDACCIÓ (després d'un <hr>):
   - 3 propostes de titular (màx. 60 caràcters): 1) Periodístic, 2) Google Discover, 3) SEO.
   - Meta descripció (màx. 140 caràcters).
   - Posts per a xarxes: Threads i Bluesky (màx. 280 caràcters, sense "no t'ho perdis"), Instagram i Facebook (to natural, 3-4 hashtags locals).
   - Versió íntegra adaptada periodísticament al castellà (mateix rigor, sense tòpics, mateixa caixa de Datos prácticos detallada, titular i meta descripció).

Format de sortida: HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>, i sense blocs ```html).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )
    return respuesta.choices[0].message.content.strip()

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

    titulo, instruccion, fechas = configurar_formato(args.tipus)
    eventos = cargar_eventos_enriquecidos(fechas)

    if not eventos:
        print("No s'han trobat esdeveniments per a aquest filtre.")
    else:
        html = redactar_noticia(args.tipus, eventos, titulo, instruccion)
        enviar_borrador_wordpress(titulo, html)
