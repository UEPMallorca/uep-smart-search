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

PALABRAS_LITERATURA = [
    "llibre", "llibres", "libro", "libros", "novel·la", "novela",
    "poesia", "poesía", "poemari", "poemario", "assaig", "ensayo",
    "editorial", "edicions", "llibreria", "librería", "escriptor",
    "escriptora", "escritor", "escritora", "literatura", "literari",
    "literària", "literaria", "relats", "relatos", "còmic", "cómic",
    "novel·la gràfica", "novela gráfica", "club de lectura",
    "recital poètic", "recital poético", "rata corner", "quart creixent",
    "drac màgic", "mallorca literària", "lleonard muntaner",
    "documenta balear", "el gall editor", "adia edicions", "nova editorial moll"
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
    "Biblioteca Pública de Palma Can Sales", "Biblioteques de Palma (Bibliopalma)"
]

ESPAIS_LITERATURA_PART_FORANA = [
    "Fundació Mallorca Literària (mallorcaliteraria.cat)",
    "Casa Museu Llorenç Villalonga (Binissalem)", "Museu de la Paraula (Sant Joan)",
    "Casa Blai Bonet (Santanyí)", "Institució Pública Antoni M. Alcover (Manacor)",
    "Llibreria Món de Llibres (Manacor)", "Casal de Cultura Can Gelabert (Binissalem)",
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


def es_de_literatura(evento):
    texto = f"{evento.get('titol', '')} {evento.get('resum', '')}".lower()
    return any(p in texto for p in PALABRAS_LITERATURA)


def es_agenda_previa(evento):
    titulo = evento.get("titol", "").lower()
    return any(t in titulo for t in TITULOS_IGNORAR)


def es_d_any_anterior(evento, fechas_objetivo):
    """Descarta elements que pertanyin a anys anteriors al rang objectiu."""
    anys_valids = {str(f.year) for f in fechas_objetivo}
    any_minim = min(f.year for f in fechas_objetivo)
    anys_passats = [str(y) for y in range(2020, any_minim)]

    texto = f"{evento.get('titol', '')} {evento.get('resum', '')} {evento.get('enllac', '')}".lower()
    te_any_valid = any(re.search(rf"\b{y}\b", texto) for y in anys_valids)
    te_any_passat = any(re.search(rf"\b{y}\b", texto) for y in anys_passats)

    return te_any_passat and not te_any_valid


def coincide_fecha(evento, fechas_objetivo):
    if es_d_any_anterior(evento, fechas_objetivo):
        return False

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
        if any(re.search(rf"(?<!\d){re.escape(p)}(?!\d)", texto) for p in patrones):
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
    if tipo == "literatura_semana":
        fonts = [
            ("FUNDACIÓ MALLORCA LITERÀRIA (web oficial: https://www.mallorcaliteraria.cat/ca/agenda)", "https://www.mallorcaliteraria.cat/ca/agenda"),
        ]
    else:
        fonts = [
            ("AUDITORIUM DE PALMA (web oficial: https://auditoriumpalma.com/ca/)", "https://auditoriumpalma.com/ca/"),
            ("YOUTHING (només dades objectives, PROHIBIT citar o enllaçar youthing.es)", "https://youthing.es/"),
        ]
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
            f"Presentacions de llibres i agenda literària a Mallorca ({fechas[0].strftime('%d/%m')} - {fechas[-1].strftime('%d/%m
