import os
import re
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- CONFIGURACIÓ DE PROVA ---
CAT_CINEMA_ID = 176
IMATGE_DESTACADA_ID = 72976
ESTAT_PUBLICACIO = "draft"  # Canvia a "publish" només quan validis la vista prèvia
# -----------------------------

WP_BASE_URL = "https://uepmallorca.app/wp-json/wp/v2"
WP_AUTH = (os.environ["WP_USER"], os.environ["WP_APP_PASSWORD"])


def obtenir_data_divendres():
    avui = datetime.now()
    dies_fins_divendres = (4 - avui.weekday()) % 7
    divendres = avui + timedelta(days=dies_fins_divendres)
    return divendres.strftime("%d/%m/%Y")


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


def obtenir_o_crear_etiquetes(llista_noms):
    ids = []
    for nom in llista_noms:
        nom_net = nom.strip()
        if not nom_net:
            continue
        r = requests.get(
            f"{WP_BASE_URL}/tags",
            params={"search": nom_net},
            auth=WP_AUTH,
            timeout=15
        )
        if r.status_code == 200:
            coincidencies = [t for t in r.json() if t["name"].lower() == nom_net.lower()]
            if coincidencies:
                ids.append(coincidencies[0]["id"])
                continue
        r_create = requests.post(
            f"{WP_BASE_URL}/tags",
            json={"name": nom_net},
            auth=WP_AUTH,
            timeout=15
        )
        if r_create.status_code in (200, 201):
            ids.append(r_create.json()["id"])
    return ids


def cercar_dossier_estrenes(data_divendres):
    prompt_cerca = f"""
Cerca a internet les 5 o 6 pel·lícules principals que s'estrenen el divendres {data_divendres} a les sales de Mallorca:
CineCiutat (Palma), Aficine (Augusta, Ocimax Palma, Rívoli), Artesiete FAN (Palma), Cinesa Mallorca Fashion Outlet / Festival Park (Marratxí) i Ocine Premium Porto Pi (Palma).

Elabora un dossier informatiu detallat en text pla per a un periodista de cultura. Per a CADA pel·lícula, cerca i inclou obligatòriament:
- Títol exacte (i títol original si és estrangera).
- Direcció i guió.
- Repartiment principal (3-5 noms).
- País, gènere i context (si ve d'algun festival, si adapta una novel·la, etc.).
- Sinopsi completa (3-4 frases explicant bé l'argument i el conflicte).
- Sales concretes de Mallorca on es projecta i si té passis en VOSE.

PROHIBIT incloure referències ni atribucions a altres mitjans de comunicació o portals externs. No escriguis cap article encara, només el dossier ric en dades sobre les pel·lícules.
"""

    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search"}],
        input=prompt_cerca
    )
    return response.output_text


def redactar_estrenes_cat(data_divendres, dossier):
    prompt_sistema = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Redacta una crònica periodística en català d'estrenes de cinema a Mallorca per al divendres {data_divendres} a partir, exclusivament, del dossier proporcionat, LLESTA PER PUBLICAR DIRECTAMENT al diari (sense notes internes, sense propostes de titulars i sense posts de xarxes dins del cos). Aprofita al màxim el material del dossier. Humanitza el text perquè la lectura sigui natural i fluida. Organitza la informació segons la piràmide invertida.

TRACTAMENT DE LA INFORMACIÓ:
- Mirada periodística: Identifica el fet noticiable principal (l'estrena més potent o el fil conductor de la cartellera) abans de redactar. Aquest fet ha de marcar l'enfocament del lead i l'ordre de la informació. Mantén un to clar, neutral, rigorós i imparcial. No emetis judicis de valor personals ni utilitzis la primera persona.
- Base estricta: Extreu la màxima informació rellevant del dossier per crear un article profund i complet. NO inventis fets, NO facis suposicions i
