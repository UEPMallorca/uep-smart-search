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

TITULOS_IGNORAR = [
    "agenda cultural", "concerts de la setmana", "teatre de la setmana",
    "esborrany", "borrador"
]

MESOS_CAT = {
    1: "gener", 2: "febrer", 3: "març", 4: "abril", 5: "maig", 6: "juny",
    7: "juliol", 8: "agost", 9: "setembre", 10: "octubre", 11: "novembre", 12: "desembre"
}

SALAS_MUSICA = [
    "Es Gremi (Palma)", "Auditorium de Palma", "Trui Teatre (Palma)",
    "Teatre Principal de Palma", "Teatre Xesc Forteza (Palma)",
    "Factoria de So (Santa Maria)", "Jazz Voyeur Club (Palma)",
    "Auditori d'Alcúdia", "Auditori de Manacor", "Teatre Principal d'Inca",
    "Teatre de Lloseta"
]

SALAS_TEATRO = [
    "Teatre Principal de Palma", "Teatre del Mar (Palma)",
    "Teatre Xesc Forteza (Palma)", "Teatre Mar i Terra (Palma)",
    "Teatre Sans (Palma)", "Teatre Municipal Catalina Valls (Palma)",
    "Auditorium de Palma", "Trui Teatre (Palma)",
    "Auditori de Manacor", "Teatre Principal d'Inca",
    "Teatre de Lloseta", "Teatre d'Artà"
]


def es_de_mallorca(evento):
    texto = f"{evento.get('titol', '')} {evento.get('resum', '')} {evento.get('enllac', '')}".lower()
    return not any(re.search(rf"\b{re.escape(p)}\b", texto) for p in PALABRAS_EXCLUIDAS)


def es_agenda_previa(evento):
    titulo = evento.get("titol", "").lower()
    return any(t in titulo for t in TITULOS_IGNORAR)


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
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside"]):
            tag.decompose()
        contenedor = soup.find("article") or soup.find("main") or soup
        texto = contenedor.get_text(separator="\n", strip=True)
        lineas = [l.strip() for l in texto.splitlines() if len(l.strip()) > 2]
        return "\n".join(lineas)[:2500]
    except Exception:
        return ""


def limpiar_y_formatear_html(html):
    html = re.sub(r"^```html\s*", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\s*```$", "", html.strip())
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    html = re.sub(r"\s*\[\d+(?:[\.,\s]+\d+)*\]", "", html)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["rel"] = "noopener noreferrer"
    return str(soup)


def configurar_formato(tipo):
    hoy = datetime.now()
    if tipo == "sabado":
        dias = (5 - hoy.weekday()) % 7
        f = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del dissabte {f.strftime('%d/%m/%Y')} a Mallorca",
            f"Agenda cultural del sábado {f.strftime('%d/%m/%Y')} en Mallorca",
            f"Redacta la notícia d'agenda cultural per al dissabte {f.strftime('%d/%m/%Y')} a Mallorca. Descarta qualsevol acte que no tingui lloc aquell dia.",
            [f]
        )
    elif tipo == "domingo":
        dias = (6 - hoy.weekday()) % 7
        f = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del diumenge {f.strftime('%d/%m/%Y')} a Mallorca",
            f"Agenda cultural del domingo {f.strftime('%d/%m/%Y')} en Mallorca",
            f"Redacta la notícia d'agenda cultural per al diumenge {f.strftime('%d/%m/%Y')} a Mallorca. Descarta qualsevol acte que no tingui lloc aquell dia.",
            [f]
        )
    elif tipo == "conciertos_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Concerts de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Conciertos de la semana en Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT concerts i música en directe entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta teatre i altres disciplines.",
            fechas
        )
    elif tipo == "teatro_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Teatre de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Teatro de la semana en Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT teatre, dansa, monòlegs i arts escèniques entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta concerts.",
            fechas
        )
    raise ValueError("Tipus no vàlid")


def cargar_eventos_enriquecidos(fechas_objetivo):
    with open("hemeroteca_vectors.json", "r", encoding="utf-8") as f:
        datos = json.load(f)

    entradas = [
        a for a in datos
        if a.get("tipus") == "entrada" and es_de_mallorca(a) and coincide_fecha(a, fechas_objetivo)
    ]

    noticias = [
        a for a in datos
        if a.get("tipus") != "entrada"
        and not es_agenda_previa(a)
        and es_de_mallorca(a)
        and coincide_fecha(a, fechas_objetivo)
    ]

    seleccion = entradas[:15] + noticias[:10]
    enriquecidos = []

    for ev in seleccion:
        origen = "TAQUILLA (entradas.uepmallorca.app)" if ev.get("tipus") == "entrada" else "NOTÍCIA (uepmallorca.app)"
        print(f"Llegint [{origen}]: {ev.get('titol')} -> {ev.get('enllac')}")
        texto_web = extraer_ficha_web(ev.get("enllac", ""))
        enriquecidos.append({
            "origen": origen,
            "titol": ev.get("titol", ""),
            "resum": ev.get("resum", ""),
            "enllac": ev.get("enllac", ""),
            "fitxa_completa": texto_web
        })
    return enriquecidos


def cercar_agenda_externa(client, tipo, fechas_objetivo):
    if tipo not in ("conciertos_semana", "teatro_semana"):
        return ""

    data_inici = fechas_objetivo[0].strftime("%d/%m/%Y")
    data_fi = fechas_objetivo[-1].strftime("%d/%m/%Y")

    if tipo == "conciertos_semana":
        disciplina = "concerts i música en directe"
        salas = ", ".join(SALAS_MUSICA)
    else:
        disciplina = "teatre, dansa, monòlegs i arts escèniques"
        salas = ", ".join(SALAS_TEATRO)

    prompt_cerca = f"""
Cerca a internet la programació confirmada de {disciplina} a Mallorca entre el {data_inici} i el {data_fi} a les principals sales de referència:
{salas}.

Elabora un dossier informatiu en text pla amb els esdeveniments CONFIRMATS dins aquestes dates exactes (descarta qualsevol acte d'Eivissa, Menorca o Formentera, i qualsevol data fora del rang {data_inici} - {data_fi}).
Per a cada esdeveniment trobat, indica:
- Nom de l'artista, banda, obra o companyia.
- Data exacta i hora (si consta).
- Sala i municipi de Mallorca.
- Breu descripció (2-3 frases sobre la proposta artística).

No escriguis cap notícia encara, només el dossier verificat. Si d'alguna sala no hi ha programació confirmada en aquestes dates, no t'inventis res.
"""

    print(f"Cercant programació externa per a {tipo} ({data_inici} - {data_fi})...")
    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search"}],
        input=prompt_cerca
    )
    return response.output_text


def redactar_noticia_cat(client, eventos, instruccion_filtro, dossier_externo=""):
    fecha_hoy = datetime.now().strftime("%d/%m/%Y")

    dossier = ""
    for i, e in enumerate(eventos, 1):
        dossier += (
            f"=== ELEMENT {i} [{e['origen']}] ===\n"
            f"Títol: {e['titol']}\n"
            f"Resum breu: {e['resum']}\n"
            f"Enllaç: {e['enllac']}\n"
            f"TEXT COMPLET DE LA PÀGINA:\n{e['fitxa_completa']}\n\n"
        )

    if dossier_externo:
        dossier += (
            "=== PROGRAMACIÓ EXTERNA DE SALES DE REFERÈNCIA A MALLORCA ===\n"
            f"{dossier_externo}\n\n"
        )

    prompt_sistema = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Avui és {fecha_hoy}.
OBJECTIU: {instruccion_filtro}

REGLES INNEGOCIABLES:
1. COBERTURA EXHAUSTIVA DE TAQUILLA I INTEGRACIÓ DE SALES DE REFERÈNCIA:
  - Has d'incloure TOTS i CADA UN dels esdeveniments marcats com a [TAQUILLA (entradas.uepmallorca.app)] que encaixin amb la data i la disciplina demanada. NO n'ometis ni un sol ni els resumeixis en excés.
  - Afegeix també els actes rellevants procedents de [NOTÍCIA (uepmallorca.app)] i de [PROGRAMACIÓ EXTERNA DE SALES DE REFERÈNCIA A MALLORCA] que tinguin lloc exactament en el rang de dates objectiu.
  - Si un mateix esdeveniment apareix a TAQUILLA/NOTÍCIA i també a la PROGRAMACIÓ EXTERNA, fusiona la informació en un sol paràgraf sense repetir-lo i mantén SEMPRE l'enllaç d'UEP! Mallorca.
  - No inventis mai enllaços per als esdeveniments de la programació externa.
2. ZERO TÒPICS, ZERO CLIXÉS I ZERO ARRANCS REPETITIUS:
  - ESTÀ TERMINANTMENT PROHIBIT utilitzar expressions buides com "es converteix en l'epicentre de la cultura", "epicentre cultural", "amb una oferta variada", "promet emocionar", "una experiència única", "no es pot perdre" o "farà gaudir al públic".
  - Obre el primer paràgraf (lead) directament amb els protagonistes reals de la setmana (artistes, bandes, obres o espais concrets), integrant les 5W de forma natural.
3. ESTRUCTURA PERIODÍSTICA REAL (NO UN LLISTAT):
  - Agrupa els esdeveniments en 3 o 4 grans blocs temàtics o geogràfics amb subtítols <h2> descriptius. NO facis un <h2> per a cada esdeveniment individual.
  - Redacta en paràgrafs (<p>) complets i enllaçats entre si, integrant totes les dades pràctiques (dia, hora, recinte, municipi, preu si consta) dins el propi relat.
  - NO afegeixis cap secció de "Dades pràctiques" al final.
  - Integra els enllaços de compra i de notícies d'UEP! de manera natural dins les frases amb <a href="..." target="_blank" rel="noopener noreferrer">...</a>.
  - FORMAT HTML ESTRICTE: Utilitza EXCLUSIVAMENT etiquetes HTML (<strong>...</strong>) per a les negretes. PROHIBIT fer servir asteriscos de Markdown (**) i PROHIBIT cites numèriques tipus [1]. Aplica <strong> només a noms clau, municipis, espais culturals i dates.
4. RIGOR ABSOLUT: No inventis cap dada. Respecta els noms propis i títols originals sense traduir-los. Descarta qualsevol esdeveniment d'Eivissa, Menorca o Formentera.
5. BLOC DE REDACCIÓ AL FINAL (separat per <hr>):
  - 3 propostes de titular (màx. 60 caràcters): 1) Periodístic, 2) Google Discover, 3) SEO.
  - Meta descripció (màx. 140 caràcters).
  - Posts per a xarxes: Threads i Bluesky (màx. 280 caràcters), Instagram i Facebook (to natural, 3-4 hashtags locals).

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.35,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )
    return limpiar_y_formatear_html(respuesta.choices[0].message.content)


def adaptar_noticia_es(client, html_cat):
    prompt_sistema = """
Actua com una periodista experimentada d'UEP! Mallorca.
Fes una adaptació periodística ÍNTEGRA al castellà del següent article en català (sense resumir-lo ni ometre absolutament cap esdeveniment, detall, horari, preu ni enllaç).

REGLES ESTRICTES:
1. Mantén exactament tots els esdeveniments, tots els enllaços (<a href="..." target="_blank" rel="noopener noreferrer">) i la mateixa estructura de <h2> i <p>.
2. Respecta els noms propis, espais culturals, festivals i títols originals d'obres sense traduir-los.
3. Sense tòpics ("epicentro de la cultura", "oferta variada", "promete emocionar") i sense secció de "Datos prácticos".
4. Utilitza EXCLUSIVAMENT HTML net (<strong> per a negretes, mai asteriscos **).
5. Adapta també al castellà el bloc final de redacció després de l'<hr> (3 titulars màx. 60 caràcters, meta descripció màx. 140 caràcters i posts per a xarxes socials).

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": html_cat}
        ]
    )
    return limpiar_y_formatear_html(respuesta.choices[0].message.content)


def enviar_borrador_wordpress(titulo, contenido_html):
    url = "https://" + "uepmallorca.app/wp-json/wp/v2/posts"
    auth = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])
    payload = {
        "title": titulo,
        "content": contenido_html,
        "status": "draft"
    }
    resp = requests.post(url, auth=auth, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Esborrany creat correctament! [{titulo}] ID: {resp.json().get('id')}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--tipus", required=True, choices=["sabado", "domingo", "conciertos_semana", "teatro_semana"])
    args = parser.parse_args()

    titulo_cat, titulo_es, instruccion, fechas = configurar_formato(args.tipus)
    eventos = cargar_eventos_enriquecidos(fechas)
    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
    dossier_externo = cercar_agenda_externa(client, args.tipus, fechas)

    if not eventos and not dossier_externo:
        print("No s'han trobat esdeveniments per a aquest filtre.")
    else:
        html_cat = redactar_noticia_cat(client, eventos, instruccion, dossier_externo)
        if html_cat:
            enviar_borrador_wordpress(f"[ESBORRANY CAT] {titulo_cat}", html_cat)
            html_es = adaptar_noticia_es(client, html_cat)
            if html_es:
                enviar_borrador_wordpress(f"[BORRADOR ES] {titulo_es}", html_es)
