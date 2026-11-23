import os
import re
import json
import base64
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

# --- CONFIGURACIÓ DE PROVA ---
CAT_CINEMA_ID = 176
IMATGE_RECURS_ID = None     # Opcional: ID d'una foto de reserva per si falla la generació
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


def generar_i_pujar_imatge(prompt_imatge, data_divendres, alt_text):
    try:
        print("Generant imatge destacada editorial...")
        img_resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt_imatge,
            size="1536x1024",
            quality="medium",
            n=1
        )
        img_data = img_resp.data[0]
        if getattr(img_data, "b64_json", None):
            img_bytes = base64.b64decode(img_data.b64_json)
        elif getattr(img_data, "url", None):
            img_bytes = requests.get(img_data.url, timeout=30).content
        else:
            raise ValueError("No s'ha rebut cap imatge d'OpenAI.")

        data_slug = data_divendres.replace("/", "-")
        filename = f"estrenes-cinema-mallorca-{data_slug}.png"
        headers = {
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Type": "image/png"
        }

        print("Pujant imatge a la biblioteca de WordPress...")
        r = requests.post(
            f"{WP_BASE_URL}/media",
            headers=headers,
            data=img_bytes,
            auth=WP_AUTH,
            timeout=45
        )
        r.raise_for_status()
        media_id = r.json()["id"]

        requests.post(
            f"{WP_BASE_URL}/media/{media_id}",
            json={"alt_text": alt_text},
            auth=WP_AUTH,
            timeout=15
        )
        print(f"Imatge pujada correctament! Media ID: {media_id}")
        return media_id
    except Exception as e:
        print(f"Avís: no s'ha pogut generar/pujar la imatge ({e}).")
        return IMATGE_RECURS_ID

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

No escriguis cap article encara, només el dossier ric en dades sobre les pel·lícules.
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
A partir EXCLUSIVAMENT del dossier proporcionat, redacta la crònica d'estrenes de cinema a Mallorca per al divendres {data_divendres}, LLESTA PER PUBLICAR DIRECTAMENT al diari (sense notes internes, sense propostes de titulars i sense posts de xarxes).

REGLES INNEGOCIABLES:
1. PROTAGONISME ABSOLUT PER A LES PEL·LÍCULES (80% cinema, 20% sales):
   - Dedica el gruix de cada paràgraf a explicar bé de què va la pel·lícula, quin enfocament té, qui la dirigeix, qui la protagonitza i quin interès cultural aporta.
2. PROHIBIT REPETIR FÓRMULES NI DATES:
   - La data d'estrena ({data_divendres}) només s'escriu UNA vegada, al primer paràgraf (lead).
   - Indica les sales amb una sola frase curta i natural al final del comentari de cada film.
3. ZERO TÒPICS I ZERO CLIXÉS: Prohibit expressions buides ("epicentre cultural", "oferta variada", "promet emocionar", "experiència única", "no es pot perdre").
4. ESTRUCTURA PERIODÍSTICA:
   - Primer paràgraf (lead) directe amb les 5W, els títols destacats i la paraula clau "estrenes de cinema a Mallorca".
   - Agrupa les pel·lícules en 3 blocs temàtics amb subtítols <h2> descriptius.
   - No tradueixis mai els títols ni els noms propis. No inventis dades que no siguin al dossier.
5. FORMAT HTML ESTRICTE: Utilitza EXCLUSIVAMENT etiquetes HTML (<p>, <h2>, <ul>, <li>, <strong>, <em>). PROHIBIT asteriscos de Markdown (**), PROHIBIT <h1> i PROHIBIT cites numèriques tipus [1]. Aplica <strong> només a noms clau (directors, intèrprets), sales de Mallorca i dates.

HAS DE RETORNAR EXCLUSIVAMENT UN OBJECTE JSON VÀLID amb aquestes 6 claus exactes:
{{
  "titol": "Titular periodístic definitiu en català, màxim 60 caràcters, sense cometes innecessàries ni prefixos",
  "frase_clau": "estrenes de cinema a Mallorca",
  "meta_descripcio": "Meta descripció en català de màxim 140 caràcters que inclogui 'estrenes de cinema a Mallorca'",
  "etiquetes": ["Estrenes de cinema", "Cartellera Mallorca", "CineCiutat", "Palma"],
  "prompt_imatge": "Prompt en anglès per a una fotografia o il·lustració editorial cinematogràfica, format horitzontal, inspirada en l'atmosfera del cinema i el gènere principal d'aquesta setmana. SENSE cap text, lletres, logotips ni cares d'actors reals.",
  "contingut_html": "Cos complet de la notícia en HTML net, llest per a publicar sense cap bloc de redacció al final"
}}
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.35,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )

    dades = json.loads(respuesta.choices[0].message.content)
    dades["contingut_html"] = limpiar_y_formatear_html(dades["contingut_html"])
    return dades


def enviar_a_wordpress(dades, data_divendres):
    tag_ids = obtenir_o_crear_etiquetes(dades.get("etiquetes", []))
    media_id = generar_i_pujar_imatge(
        dades.get("prompt_imatge", "Editorial cinema photography, atmospheric movie theater projector beam, warm lighting, no text"),
        data_divendres,
        dades["titol"]
    )

    payload = {
        "title": dades["titol"],
        "content": dades["contingut_html"],
        "excerpt": dades["meta_descripcio"],
        "status": ESTAT_PUBLICACIO,
        "categories": [int(CAT_CINEMA_ID)],
        "tags": tag_ids,
        "meta": {
            "_yoast_wpseo_title": dades["titol"],
            "_yoast_wpseo_metadesc": dades["meta_descripcio"],
            "_yoast_wpseo_focuskw": dades["frase_clau"]
        }
    }

    if media_id:
        payload["featured_media"] = int(media_id)

    resp = requests.post(f"{WP_BASE_URL}/posts", auth=WP_AUTH, json=payload, timeout=30)
    resp.raise_for_status()
    print(f"Prova creada ({ESTAT_PUBLICACIO})! [{dades['titol']}] ID: {resp.json().get('id')}")


if __name__ == "__main__":
    data_divendres = obtenir_data_divendres()
    print(f"Cercant estrenes per al divendres {data_divendres}...")
    dossier = cercar_dossier_estrenes(data_divendres)
    if dossier:
        dades = redactar_estrenes_cat(data_divendres, dossier)
        enviar_a_wordpress(dades, data_divendres)
