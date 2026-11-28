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
    "exposicions de la setmana", "agenda literària", "agenda literaria",
    "presentacions de llibres", "esborrany", "borrador"
]

MESOS_CAT = {
    1: "gener", 2: "febrer", 3: "març", 4: "abril", 5: "maig", 6: "juny",
    7: "juliol", 8: "agost", 9: "setembre", 10: "octubre", 11: "novembre", 12: "desembre"
}

MESOS_ES = {
    1: "enero", 2: "febrero", 3: "marzo", 4: "abril", 5: "mayo", 6: "junio",
    7: "julio", 8: "agosto", 9: "septiembre", 10: "octubre", 11: "noviembre", 12: "diciembre"
}

SALAS_MUSICA_PALMA = [
    "Es Gremi", "Auditorium de Palma (auditoriumpalma.com/ca/)", "Trui Teatre",
    "Teatre Principal de Palma", "Teatre Xesc Forteza",
    "Jazz Voyeur Club", "La Movida Cafe Concierto", "CaixaForum Palma",
    "Conservatori Superior de Música"
]

SALAS_MUSICA_PART_FORANA = [
    "Factoria de So (Santa Maria)", "Auditori d'Alcúdia", "Auditori de Manacor",
    "Teatre Principal d'Inca", "Teatre de Lloseta", "Auditori de Porreres",
    "Auditori Sa Màniga (Cala Millor)", "Teatre d'Artà", "Teatre de Petra",
    "Espai 36 (Sant Llorenç)"
]

SALAS_TEATRO_PALMA = [
    "Teatre Principal de Palma", "Teatre del Mar", "Teatre Xesc Forteza",
    "Teatre Mar i Terra", "Teatre Sans", "Teatre Municipal Catalina Valls",
    "Auditorium de Palma (auditoriumpalma.com/ca/)", "Trui Teatre", "Sala Assaig"
]

SALAS_TEATRO_PART_FORANA = [
    "Auditori de Manacor", "Teatre Principal d'Inca", "Teatre de Lloseta",
    "Teatre d'Artà", "Auditori d'Alcúdia", "Auditori de Porreres",
    "Auditori Sa Màniga (Cala Millor)", "Teatre de Petra", "Teatre de Capdepera",
    "Auditori de Peguera", "Teatre Sa Teulera (Andratx)"
]

MUSEUS_EXPOSICIONS_PALMA = [
    "Es Baluard Museu", "Casal Solleric", "Fundació Miró Mallorca",
    "CaixaForum Palma", "Museu Fundación Juan March", "La Misericòrdia",
    "Centre de Cultura Sa Nostra", "Museu de Mallorca"
]

GALERIES_ART_PALMA = [
    "Art Palma Contemporani (artpalmacontemporani.com)",
    "Galeria Pelaires", "Galeria Kewenig", "Galeria Baró",
    "6a Taller i Galeria", "Pep Llabrés", "ABA ART",
    "Galería Reus", "Xavier Fiol", "Galería Fermay",
    "Florit / Florit", "BALAZSI", "LA BIBI GALLERY", "a66Gallery"
]

SALAS_EXPOSICIONS_PART_FORANA = [
    "CCA Andratx (ccandratx.eu)", "Museu Sa Bassa Blanca (Alcúdia)",
    "Fundació Toni Catany (Llucmajor)", "Casal de Cultura Can Gelabert (Binissalem)",
    "Galeria Maior (Pollença)", "Museu d'Art Contemporani de sa Pobla (Can Planes)",
    "Claustre de Sant Domingo (Pollença)", "Museu d'Història de Manacor",
    "Fundació Coll Bardolet (Valldemossa)"
]

LLIBRERIES_I_CENTRES_PALMA = [
    "Rata Corner (ratacorner.com)", "Llibreria Quart Creixent (quartcreixent.es)",
    "Llibreria Drac Màgic (llibreriadracmagic.com)", "Llibreria Embat",
    "Ínsula Literària", "Literanta", "La Biblioteca de Babel", "Finis Africae",
    "Ámbito Cultural El Corte Inglés Palma", "Can Alcover (OCB)",
    "Biblioteca Pública de Palma Can Sales", "Biblioteques de Palma (Bibliopalma)",
    "La Misericòrdia", "CaixaForum Palma", "Centre de Cultura Sa Nostra"
]

ESPAIS_LITERATURA_PART_FORANA = [
    "Fundació Mallorca Literària (mallorcaliteraria.cat)",
    "Casa Museu Llorenç Villalonga (Binissalem)", "Museu de la Paraula (Sant Joan)",
    "Casa Blai Bonet (Santanyí)", "Institució Pública Antoni M. Alcover (Manacor)",
    "Llibreria Món de Llibres (Manacor)", "Casal de Cultura Can Gelabert (Binissalem)",
    "Fundació Toni Catany (Llucmajor)", "Can Planes (sa Pobla)",
    "Biblioteques municipals d'Inca, Manacor, Pollença, Sóller, Felanitx i Alcúdia"
]

EDITORIALS_MALLORCA = [
    "Lleonard Muntaner Editor", "Documenta Balear", "Nova Editorial Moll",
    "AdiA Edicions", "El Gall Editor", "Ensiola Editorial", "Editorial Sloper",
    "Gremi de Llibreters de Mallorca"
]

ESPAIS_AGENDA_PALMA = [
    "Teatre Principal de Palma", "Auditorium de Palma (auditoriumpalma.com/ca/)", "Es Gremi",
    "Teatre Xesc Forteza", "Teatre del Mar", "Teatre Mar i Terra",
    "Es Baluard", "Casal Solleric", "CaixaForum Palma", "Fundació Miró Mallorca",
    "Art Palma Contemporani", "PalmaCultura", "CineCiutat", "La Misericòrdia"
]

ESPAIS_AGENDA_PART_FORANA = [
    "Auditori de Manacor", "Teatre Principal d'Inca", "Auditori d'Alcúdia",
    "Teatre de Lloseta", "Teatre d'Artà", "Auditori de Porreres",
    "Auditori Sa Màniga (Cala Millor)", "Factoria de So (Santa Maria)",
    "CCA Andratx (ccandratx.eu)", "Auditori de Peguera"
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
        mes_cat = MESOS_CAT[f.month]
        mes_es = MESOS_ES[f.month]
        prep = "d'" if f.month in (4, 8, 10) else "de "
        patrones = [
            f.strftime("%d/%m/%Y"),
            f.strftime("%d/%m"),
            f.strftime("%Y-%m-%d"),
            f"{f.day} {prep}{mes_cat}",
            f"{f.day:02d} {prep}{mes_cat}",
            f"{f.day} de {mes_cat}",
            f"{f.day} {mes_cat}",
            f"{f.day} {mes_cat[:3]}",
            f"{f.day} de {mes_es}",
            f"{f.day:02d} de {mes_es}"
        ]
        if any(p in texto for p in patrones):
            return True
    return False


def extraer_ficha_web(url, max_chars=2500):
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
        }
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            return ""
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "nav", "footer", "header", "noscript", "aside", "form"]):
            tag.decompose()
        contenedor = soup.find("main") or soup.find("article") or soup.body or soup
        texto = contenedor.get_text(separator="\n", strip=True)
        lineas = [l.strip() for l in texto.splitlines() if len(l.strip()) > 2]
        return "\n".join(lineas)[:max_chars]
    except Exception:
        return ""


def extreure_cartelleres_directes(tipo):
    """Llegeix directament l'HTML de webs clau segons el tipus d'agenda."""
    fonts = [
        ("YOUTHING (només dades objectives, PROHIBIT citar o enllaçar youthing.es)", "https://youthing.es/"),
    ]
    if tipo == "literatura_semana":
        fonts.insert(0, ("FUNDACIÓ MALLORCA LITERÀRIA (web oficial: https://www.mallorcaliteraria.cat/ca/agenda)", "https://www.mallorcaliteraria.cat/ca/agenda"))
    else:
        fonts.insert(0, ("AUDITORIUM DE PALMA (web oficial: https://auditoriumpalma.com/ca/)", "https://auditoriumpalma.com/ca/"))
        if tipo in ("sabado", "domingo"):
            fonts.append(("FUNDACIÓ MALLORCA LITERÀRIA (web oficial: https://www.mallorcaliteraria.cat/ca/agenda)", "https://www.mallorcaliteraria.cat/ca/agenda"))

    blocs = []
    for nom, url in fonts:
        print(f"Llegint cartellera directa: {url}")
        text = extraer_ficha_web(url, max_chars=6000)
        if text:
            blocs.append(f"=== CARTELLERA DIRECTA: {nom} ===\n{text}")
        else:
            print(f"Avís: no s'ha pogut llegir text directe de {url}")
    return "\n\n".join(blocs)


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
            f"Redacta una agenda cultural molt completa i detallada per al dissabte {f.strftime('%d/%m/%Y')} a Mallorca. Descarta qualsevol acte que no tingui lloc aquell dia (llevat d'exposicions vigents aquell dissabte).",
            [f]
        )
    elif tipo == "domingo":
        dias = (6 - hoy.weekday()) % 7
        f = hoy + timedelta(days=dias)
        return (
            f"Agenda cultural del diumenge {f.strftime('%d/%m/%Y')} a Mallorca",
            f"Agenda cultural del domingo {f.strftime('%d/%m/%Y')} en Mallorca",
            f"Redacta una agenda cultural molt completa i detallada per al diumenge {f.strftime('%d/%m/%Y')} a Mallorca. Descarta qualsevol acte que no tingui lloc aquell dia (llevat d'exposicions vigents aquell diumenge).",
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
    elif tipo == "exposiciones_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Exposicions de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Exposiciones de la semana en Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT exposicions d'art, fotografia, escultura i inauguracions vigents o que obrin portes a Mallorca entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta concerts, teatre i qualsevol espai de Menorca o Eivissa.",
            fechas
        )
    elif tipo == "literatura_semana":
        fechas = [hoy + timedelta(days=i) for i in range(7)]
        return (
            f"Agenda literària de la setmana a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Agenda literaria de la semana en Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m/%Y')})",
            f"Selecciona ÚNICAMENT presentacions de llibres, recitals poètics, clubs de lectura, xerrades literàries i signatures d'autors a Mallorca entre el {fechas[0].strftime('%d/%m/%Y')} i el {fechas[-1].strftime('%d/%m/%Y')}. Descarta concerts, teatre, exposicions no literàries i qualsevol acte de Menorca o Eivissa.",
            fechas
        )
    raise ValueError("Tipus no vàlid")


def cargar_noticias_recientes_wp(fechas_objetivo):
    """Consulta en directe les darreres notícies publicades a uepmallorca.app (incloent les d'avui mateix)."""
    enriquecidos_wp = []
    try:
        url = "https://uepmallorca.app/wp-json/wp/v2/posts"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; UEPMallorcaBot/1.0)"}
        params = {"per_page": 60, "status": "publish", "orderby": "date", "order": "desc"}
        r = requests.get(url, headers=headers, params=params, timeout=20)
        if r.status_code != 200:
            print(f"Avís: no s'han pogut llegir les notícies recents de WP (status {r.status_code}).")
            return []

        for post in r.json():
            titol = BeautifulSoup(post.get("title", {}).get("rendered", ""), "html.parser").get_text(strip=True)
            enllac = post.get("link", "")
            contingut_html = post.get("content", {}).get("rendered", "")
            texto_completo = BeautifulSoup(contingut_html, "html.parser").get_text(separator="\n", strip=True)
            candidato = {"titol": titol, "resum": texto_completo, "enllac": enllac}

            if es_agenda_previa(candidato) or not es_de_mallorca(candidato):
                continue
            if coincide_fecha(candidato, fechas_objetivo):
                print(f"Llegint [NOTÍCIA RECENT UEP!]: {titol} -> {enllac}")
                enriquecidos_wp.append({
                    "origen": "NOTÍCIA (uepmallorca.app)",
                    "titol": titol,
                    "resum": texto_completo[:350],
                    "enllac": enllac,
                    "fitxa_completa": texto_completo[:2500]
                })
    except Exception as e:
        print(f"Avís llegint notícies recents de WP: {e}")
    return enriquecidos_wp


def cargar_eventos_enriquecidos(fechas_objetivo):
    enriquecidos = cargar_noticias_recientes_wp(fechas_objetivo)
    urls_vistes = {ev["enllac"].rstrip("/") for ev in enriquecidos if ev.get("enllac")}

    try:
        with open("hemeroteca_vectors.json", "r", encoding="utf-8") as f:
            datos = json.load(f)
    except FileNotFoundError:
        datos = []

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

    seleccion = entradas[:35] + noticias[:25]

    for ev in seleccion:
        enllac = ev.get("enllac", "")
        if enllac and enllac.rstrip("/") in urls_vistes:
            continue
        if enllac:
            urls_vistes.add(enllac.rstrip("/"))
        origen = "TAQUILLA (entradas.uepmallorca.app)" if ev.get("tipus") == "entrada" else "NOTÍCIA (uepmallorca.app)"
        print(f"Llegint [{origen}]: {ev.get('titol')} -> {enllac}")
        texto_web = extraer_ficha_web(enllac)
        enriquecidos.append({
            "origen": origen,
            "titol": ev.get("titol", ""),
            "resum": ev.get("resum", ""),
            "enllac": enllac,
            "fitxa_completa": texto_web
        })
    return enriquecidos


def _fer_cerca_zona(client, disciplina, rang_dates, zona, llista_sales):
    salas_str = ", ".join(llista_sales)
    prompt_cerca = f"""
Fes una cerca exhaustiva a internet de la programació confirmada de {disciplina} a {zona} (Mallorca) {rang_dates}.
Revisa especialment les webs oficials d'aquests espais culturals: {salas_str}.

Objectiu: recopilar el màxim nombre d'esdeveniments CONFIRMATS (idealment entre 10 i 15 propostes diferents) programats dins aquestes dates exactes. Descarta qualsevol acte d'Eivissa, Menorca o Formentera, i qualsevol proposta ja finalitzada o fora del rang indicat.

REGLA ESTRICTA DE FONTS:
- Prioritza sempre la informació de les webs oficials de les llibreries, sales, museus, galeries, editorials o ajuntaments.
- PROHIBIT incloure referències, atribucions ni frases com "Més informació a..." apuntant a altres mitjans de comunicació, revistes o portals culturals externs (mai youthing.es, bonart.cat, diariodemallorca, ultimahora, dbalears, arabalears, mallorcadiario, artsmallorca, etc.).

Per a CADA proposta trobada, indica:
- Nom de l'autor/a, títol del llibre o obra, editorial (si és literatura) o artista/companyia.
- Data exacta (o dates de vigència) i hora si consta.
- Llibreria, biblioteca, sala, museu o galeria, municipi de Mallorca i preu si consta.
- Breu descripció (2-3 frases sobre la proposta).

No escriguis cap notícia encara, només el dossier verificat. Si d'algun espai no hi ha programació confirmada en aquestes dates, no t'inventis res.
"""
    print(f"Cercant programació externa [{zona}] ({rang_dates})...")
    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search"}],
        input=prompt_cerca
    )
    return response.output_text


def cercar_agenda_externa(client, tipo, fechas_objetivo):
    if len(fechas_objetivo) == 1:
        rang_dates = f"el dia {fechas_objetivo[0].strftime('%d/%m/%Y')}"
    else:
        rang_dates = f"entre el {fechas_objetivo[0].strftime('%d/%m/%Y')} i el {fechas_objetivo[-1].strftime('%d/%m/%Y')}"

    cartelleres_directes = extreure_cartelleres_directes(tipo)

    if tipo == "literatura_semana":
        disc_lit = "presentacions de llibres, recitals poètics, xerrades literàries, signatures d'autors i clubs de lectura"
        d_palma = _fer_cerca_zona(client, disc_lit, rang_dates, "Llibreries i centres culturals de Palma", LLIBRERIES_I_CENTRES_PALMA)
        d_forana = _fer_cerca_zona(client, disc_lit, rang_dates, "Part Forana de Mallorca i Fundació Mallorca Literària", ESPAIS_LITERATURA_PART_FORANA)
        d_edit = _fer_cerca_zona(client, disc_lit, rang_dates, "Editorials de Mallorca", EDITORIALS_MALLORCA)
        return (
            f"--- CARTELLERES DIRECTES (MALLORCA LITERÀRIA I YOUTHING) ---\n{cartelleres_directes}\n\n"
            f"--- LLIBRERIES I CENTRES DE PALMA ---\n{d_palma}\n\n"
            f"--- PART FORANA ---\n{d_forana}\n\n"
            f"--- EDITORIALS MALLORQUINES ---\n{d_edit}"
        )

    if tipo == "exposiciones_semana":
        disc_expo = "exposicions d'art contemporani, fotografia, escultura i inauguracions (tant noves inauguracions com mostres vigents)"
        d_museus = _fer_cerca_zona(client, disc_expo, rang_dates, "Museus i centres culturals de Palma", MUSEUS_EXPOSICIONS_PALMA)
        d_galeries = _fer_cerca_zona(client, disc_expo, rang_dates, "Galeries d'Art Palma Contemporani", GALERIES_ART_PALMA)
        d_forana = _fer_cerca_zona(client, disc_expo, rang_dates, "la Part Forana de Mallorca", SALAS_EXPOSICIONS_PART_FORANA)
        return (
            f"--- CARTELLERES DIRECTES (AUDITORIUM I YOUTHING) ---\n{cartelleres_directes}\n\n"
            f"--- MUSEUS DE PALMA ---\n{d_museus}\n\n"
            f"--- GALERIES ART PALMA CONTEMPORANI ---\n{d_galeries}\n\n"
            f"--- PART FORANA ---\n{d_forana}"
        )

    if tipo == "conciertos_semana":
        disciplina = "concerts, festivals, jazz, clàssica i música en directe"
        sales_palma = SALAS_MUSICA_PALMA
        sales_forana = SALAS_MUSICA_PART_FORANA
    elif tipo == "teatro_semana":
        disciplina = "teatre, dansa, circ, monòlegs i arts escèniques"
        sales_palma = SALAS_TEATRO_PALMA
        sales_forana = SALAS_TEATRO_PART_FORANA
    else:
        disciplina = "cultura (concerts, teatre, dansa, exposicions, literatura, cinema i activitats familiars)"
        sales_palma = ESPAIS_AGENDA_PALMA
        sales_forana = ESPAIS_AGENDA_PART_FORANA

    dossier_palma = _fer_cerca_zona(client, disciplina, rang_dates, "Palma", sales_palma)
    dossier_forana = _fer_cerca_zona(client, disciplina, rang_dates, "la Part Forana de Mallorca", sales_forana)

    return (
        f"--- CARTELLERES DIRECTES ---\n{cartelleres_directes}\n\n"
        f"--- PALMA ---\n{dossier_palma}\n\n"
        f"--- PART FORANA ---\n{dossier_forana}"
    )


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
            "=== PROGRAMACIÓ EXTERNA I CARTELLERES DIRECTES DE MALLORCA ===\n"
            f"{dossier_externo}\n\n"
        )

    prompt_sistema = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Avui és {fecha_hoy}.
OBJECTIU: {instruccion_filtro}

Redacta una notícia periodística d'agenda en català a partir del dossier complet proporcionat. Aprofita al màxim tot el material del dossier (objectiu orientatiu: entre 1.000 i 1.500 paraules si hi ha prou actes). Humanitza el text perquè la lectura sigui natural i fluida. Organitza la informació segons la piràmide invertida.

TRACTAMENT DE LA INFORMACIÓ I PRIORITAT DE FONTS:
- Mirada periodística: Identifica el fet noticiable principal abans de redactar. Aquest fet ha de marcar l'enfocament del lead i l'ordre de la informació. Mantén un to clar, neutral, rigorós i imparcial. No emetis judicis de valor personals ni utilitzis la primera persona.
- Base estricta i exhaustivitat: Extreu la màxima informació rellevant del dossier per crear un article profund i complet. Inclou TOTS els actes marcats com a [TAQUILLA (entradas.uepmallorca.app)] i [NOTÍCIA (uepmallorca.app)] que encaixin amb la data i la disciplina, i afegeix TOTS els actes confirmats de les [CARTELLERES DIRECTES] i la [PROGRAMACIÓ EXTERNA]. Si un acte apareix a UEP! i també fora, fusiona'l en un sol paràgraf mantenint SEMPRE l'enllaç d'UEP! Mallorca. NO inventis fets, NO facis suposicions i NO afegeixis dades (com preus o horaris) que no figurin al dossier. Descarta qualsevol acte d'Eivissa, Menorca o Formentera.
- Zero citacions d'altres mitjans: PROHIBIT citar o enllaçar altres mitjans de comunicació o portals culturals externs (mai youthing.es, bonart.cat, Diario de Mallorca, etc.). De youthing.es només s'aprofiten les dades objectives (acte, data, hora, lloc, preu), redactades amb les teves pròpies paraules i sense citar mai la font. Si un acte no té notícia a UEP! Mallorca, remet únicament al nom de la llibreria, biblioteca, sala, museu o galeria (o a la seva web oficial si consta al dossier).
- Estructura: Aplica la piràmide invertida. El primer paràgraf (lead) ha de contenir les 5W (Qui, Què, Quan, On, Per què) de forma directa, obrint amb els protagonistes reals de la jornada o setmana.

ESTIL DE REDACCIÓ:
- Frases curtes, dinàmiques i fluides.
- Vocabulari precís i ric, sense adjectius valoratius ni llenguatge administratiu/institucional. Prohibits tòpics com "epicentre de la cultura", "oferta variada", "promet emocionar" o "experiència única".
- Noms propis, institucions i títols d'obres: mai traduïts ni adaptats; respecta l'original.
- Integra els enllaços de compra i de notícies d'UEP! de manera natural dins les frases amb <a href="..." target="_blank" rel="noopener noreferrer">...</a>.

SEO I FORMATS (REGLES ESTRICTES):
- Jerarquia de Subtítols (H2): Divideix el text lògicament en 4 o 5 grans blocs temàtics o geogràfics utilitzant només etiquetes <h2> descriptives que responguin a la intenció de cerca del lector. NO utilitzis H3 ni H4, ni facis un H2 per a cada acte individual.
- SEO Local i Retenció visual: Aplica negretes (exclusivament amb <strong>...</strong>, mai asteriscos ** ni cites numèriques [1]) únicament a les entitats més importants: noms de persones clau, municipis o espais culturals de Mallorca, i dates rellevants.
- Densitat de Paraules Clau: Identifica la temàtica principal i assegura't que el concepte clau aparegui de forma natural al primer paràgraf i unes 2 vegades més al llarg del text.
- NO afegeixis cap caixa ni secció de "Dades pràctiques" al final; integra totes les dades (dia, hora, sala, municipi, preu) dins dels paràgrafs (<p>).

BLOC DE REDACCIÓ AL FINAL (separat per <hr>):
- Propostes de Titular: Genera 3 opcions de titular (màxim 60 caràcters) que fugin absolutament del to institucional o d'agenda plana però il·lustrin el contingut:
  1) Purament periodístic.
  2) Optimitzat per a Google Discover (suggerent, que convidi al clic sense ser clickbait).
  3) Enfocat en la paraula clau (SEO).
- Meta descripció: Màxim 140 caràcters incloent la paraula clau principal.
- Xarxes Socials: Redacta un post adaptat per a Instagram, Facebook, Threads i Bluesky.
  - Threads i Bluesky: Màxim 280 caràcters, directes i informatius.
  - Instagram i Facebook: To natural i fluid.
  - Regla general RRSS: No utilitzis la fórmula "llegeix més" ni un to excessivament promocional. Inclou 3 o 4 etiquetes (hashtags) rellevants i locals.

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.35,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )
    return limpiar_y_formatear_html(respuesta.choices[0].message.content)


def adaptar_noticia_es(client, html_cat):
    prompt_sistema = """
Actua com una periodista experimentada d'UEP! Mallorca.
Genera una versió íntegra en castellà de la notícia següent (incloent les 3 opcions de titular de màxim 60 caràcters, la meta descripció de màxim 140 caràcters i els posts per a xarxes socials després de l'<hr>).

REGLES ESTRICTES:
1. No ha de ser una traducció literal, sinó una adaptació periodística amb el mateix rigor, sense resumir ni ometre absolutament cap esdeveniment, detall, horari, preu ni enllaç (<a href="..." target="_blank" rel="noopener noreferrer">).
2. Contextualitza lleugerament els conceptes culturals, festivitats o institucions molt locals perquè un lector castellanoparlant no familiaritzat els comprengui, mantenint l'essència original, però EVITA explicacions innecessàries com "Consell de Mallorca (gobierno insular)" o "Xeremiers (gaiteros)".
3. Respecta els noms propis, espais culturals, festivals i títols originals d'obres sense traduir-los.
4. Mantén la mateixa estructura de <h2> i <p> (sense H3, H4 ni secció de "Datos prácticos").
5. PROHIBIT citar o mencionar altres mitjans de comunicació o portals externs (mai "Más información en youthing.es", "bonart.cat" ni similars).
6. Sense tòpics ni llenguatge administratiu. A les xarxes socials, no utilitzis "lee más" ni un to excessivament promocional, i inclou 3 o 4 hashtags rellevants i locals.
7. Utilitza EXCLUSIVAMENT HTML net (<strong> per a negretes, mai asteriscos **).

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.3,
        max_tokens=4096,
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
    parser.add_argument(
        "--tipus",
        required=True,
        choices=[
            "sabado",
            "domingo",
            "conciertos_semana",
            "teatro_semana",
            "exposiciones_semana",
            "literatura_semana"
        ]
    )
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
