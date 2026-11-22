import os
import re
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from openai import OpenAI

client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])


def obtenir_data_divendres():
    avui = datetime.now()
    dies_fins_divendres = (4 - avui.weekday()) % 7
    divendres = avui + timedelta(days=dies_fins_divendres)
    return divendres.strftime("%d/%m/%Y")


def limpiar_y_formatear_html(html):
    html = re.sub(r"^```html\s*", "", html.strip(), flags=re.IGNORECASE)
    html = re.sub(r"\s*```$", "", html.strip())
    html = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", html)
    # Elimina possibles cites numèriques tipus [1] o [1, 2]
    html = re.sub(r"\s*\[\d+(?:[\.,\s]+\d+)*\]", "", html)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["rel"] = "noopener noreferrer"
    return str(soup)


def redactar_estrenes_cat(data_divendres):
    prompt = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Cerca a internet les estrenes de cinema que arriben aquest divendres {data_divendres} a les sales de Mallorca:
- CineCiutat (Palma)
- Aficine (Augusta, Ocimax Palma, Rívoli)
- Artesiete FAN (Palma)
- Cinesa Festival Park / Mallorca Fashion Outlet (Marratxí)

REGLES INNEGOCIABLES:
1. ZERO TÒPICS I ZERO CLIXÉS: Prohibit usar expressions buides ("epicentre cultural", "oferta variada", "promet emocionar", "experiència única", "no es pot perdre").
2. PIRÀMIDE INVERTIDA: Obre el primer paràgraf (lead) directament amb els títols principals de la setmana, integrant les 5W i la paraula clau "estrenes de cinema a Mallorca".
3. ESTRUCTURA PERIODÍSTICA: Agrupa les estrenes en 3 blocs temàtics amb subtítols <h2> descriptius (ex: cinema estatal, cinema d'autor/VOSE, cinema comercial). Redacta en paràgrafs (<p>) complets integrant sinopsi, direcció, repartiment i en quines sales de Mallorca es projecta cada títol (indicant si hi ha VOSE).
4. RIGOR ABSOLUT: No inventis dades ni sales. No tradueixis mai els títols originals ni els noms propis. PROHIBIT incloure cites numèriques tipus [1] o enllaços automàtics de cerca.
5. FORMAT HTML ESTRICTE: Utilitza EXCLUSIVAMENT etiquetes HTML (<p>, <h2>, <ul>, <li>, <strong>, <em>). PROHIBIT asteriscos de Markdown (**). Aplica <strong> només a noms clau (directors, intèrprets), sales de Mallorca i dates.
6. BLOC DE REDACCIÓ AL FINAL (separat per <hr>):
   - 3 propostes de titular (màx. 60 caràcters): 1) Periodístic, 2) Google Discover, 3) SEO.
   - Meta descripció (màx. 140 caràcters).
   - Posts per a xarxes en català: Threads i Bluesky (màx. 280 caràcters), Instagram i Facebook (to natural, sense "llegeix més", 3-4 hashtags locals).

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search"}],
        input=prompt
    )
    return limpiar_y_formatear_html(response.output_text)


def adaptar_estrenes_es(html_cat):
    prompt_sistema = """
Actua com una periodista experimentada d'UEP! Mallorca.
Fes una adaptació periodística ÍNTEGRA al castellà del següent article en català (sense resumir-lo ni ometre cap pel·lícula, sala ni detall).

REGLES ESTRICTES:
1. Mantén exactament totes les pel·lícules, sales i la mateixa estructura de <h2> i <p>.
2. Respecta els noms propis, sales de Mallorca i títols originals sense traduir-los.
3. Sense tòpics ni clixés. Utilitza EXCLUSIVAMENT HTML net (<strong> per a negretes, mai asteriscos **).
4. Adapta també al castellà el bloc final de redacció després de l'<hr> (3 titulars màx. 60 caràcters, meta descripció màx. 140 caràcters i posts per a xarxes socials).

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
    url = "https://uepmallorca.app/wp-json/wp/v2/posts"
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
    data_divendres = obtenir_data_divendres()
    html_cat = redactar_estrenes_cat(data_divendres)
    if html_cat:
        enviar_borrador_wordpress(f"[ESBORRANY CAT] Estrenes de cinema a Mallorca ({data_divendres})", html_cat)
        html_es = adaptar_estrenes_es(html_cat)
        if html_es:
            enviar_borrador_wordpress(f"[BORRADOR ES] Estrenos de cine en Mallorca ({data_divendres})", html_es)
