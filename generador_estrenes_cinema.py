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
    html = re.sub(r"\s*\[\d+(?:[\.,\s]+\d+)*\]", "", html)
    soup = BeautifulSoup(html, "html.parser")
    for a in soup.find_all("a"):
        a["target"] = "_blank"
        a["rel"] = "noopener noreferrer"
    return str(soup)


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
A partir EXCLUSIVAMENT del dossier proporcionat, redacta la crònica d'estrenes de cinema a Mallorca per al divendres {data_divendres}.

REGLES INNEGOCIABLES:
1. PROTAGONISME ABSOLUT PER A LES PEL·LÍCULES (80% cinema, 20% sales):
   - Dedica el gruix de cada paràgraf a explicar bé de què va la pel·lícula, quin enfocament té, qui la dirigeix, qui la protagonitza i quin interès cultural aporta.
   - NO facis llistats mecànics ni paràgrafs buits parlant només de cines.
2. PROHIBIT REPETIR FÓRMULES NI DATES:
   - La data d'estrena ({data_divendres}) només s'escriu UNA vegada, al primer paràgraf (lead). NO repeteixis mai "també s'estrena divendres", "arriba a Espanya i Mallorca", etc. a la resta de l'article.
   - Per indicar les sales, fes servir una sola frase curta i natural al final del comentari de cada film (ex: "Es pot veure a <strong>CineCiutat</strong> i <strong>Augusta</strong> en VOSE."). PROHIBIT repetir estructures pesades com "en versió doblada i addicionalment ofereix sessions en idioma original subtitulat".
3. ZERO TÒPICS I ZERO CLIXÉS: Prohibit usar expressions buides ("epicentre cultural", "oferta variada", "promet emocionar", "experiència única", "no es pot perdre").
4. ESTRUCTURA PERIODÍSTICA:
   - Primer paràgraf (lead) directe amb les 5W, els títols destacats i la paraula clau "estrenes de cinema a Mallorca".
   - Agrupa les pel·lícules en 3 blocs temàtics amb subtítols <h2> descriptius (ex: cinema estatal, cinema d'autor/VOSE, cinema comercial).
   - No tradueixis mai els títols ni els noms propis. No inventis dades que no siguin al dossier.
5. FORMAT HTML ESTRICTE: Utilitza EXCLUSIVAMENT etiquetes HTML (<p>, <h2>, <ul>, <li>, <strong>, <em>). PROHIBIT asteriscos de Markdown (**) i PROHIBIT cites numèriques tipus [1]. Aplica <strong> només a noms clau (directors, intèrprets), sales de Mallorca i dates.
6. BLOC DE REDACCIÓ AL FINAL (separat per <hr>):
   - 3 propostes de titular (màx. 60 caràcters): 1) Periodístic, 2) Google Discover, 3) SEO.
   - Meta descripció (màx. 140 caràcters).
   - Posts per a xarxes en català: Threads i Bluesky (màx. 280 caràcters), Instagram i Facebook (to natural, sense "llegeix més", 3-4 hashtags locals).

Retorna ÚNICAMENT HTML net per a WordPress (sense etiquetes <html>, <head> ni <body>).
"""

    respuesta = client.chat.completions.create(
        model="gpt-4o",
        temperature=0.4,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )
    return limpiar_y_formatear_html(respuesta.choices[0].message.content)


def adaptar_estrenes_es(html_cat):
    prompt_sistema = """
Actua com una periodista experimentada d'UEP! Mallorca.
Fes una adaptació periodística ÍNTEGRA al castellà del següent article en català (sense resumir-lo ni ometre cap pel·lícula, sinopsi, sala ni detall).

REGLES ESTRICTES:
1. Mantén exactament totes les pel·lícules, sales i la mateixa estructura de <h2> i <p>.
2. To àgil, natural i cinematogràfic, sense repeticions de dates ni tòpics.
3. Respecta els noms propis, sales de Mallorca i títols originals sense traduir-los.
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
    print(f"Cercant estrenes per al divendres {data_divendres}...")
    dossier = cercar_dossier_estrenes(data_divendres)
    if dossier:
        html_cat = redactar_estrenes_cat(data_divendres, dossier)
        if html_cat:
            enviar_borrador_wordpress(f"[ESBORRANY CAT] Estrenes de cinema a Mallorca ({data_divendres})", html_cat)
            html_es = adaptar_estrenes_es(html_cat)
            if html_es:
                enviar_borrador_wordpress(f"[BORRADOR ES] Estrenos de cine en Mallorca ({data_divendres})", html_es)
