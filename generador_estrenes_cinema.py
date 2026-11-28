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
Redacta una crònica periodística en català d'estrenes de cinema a Mallorca per al divendres {data_divendres} a partir, exclusivament, del dossier proporcionat. Aprofita al màxim el material del dossier. Humanitza el text perquè la lectura sigui natural i fluida. Organitza la informació segons la piràmide invertida.

TRACTAMENT DE LA INFORMACIÓ:
- Mirada periodística: Identifica el fet noticiable principal (l'estrena més potent o el fil conductor de la cartellera) abans de redactar. Aquest fet ha de marcar l'enfocament del lead i l'ordre de la informació. Mantén un to clar, neutral, rigorós i imparcial. No emetis judicis de valor personals ni utilitzis la primera persona.
- Base estricta: Extreu la màxima informació rellevant del dossier per crear un article profund i complet. NO inventis fets, NO facis suposicions i NO afegeixis dades que no figurin al dossier.
- Protagonisme absolut per a les pel·lícules (80% cinema, 20% sales): Dedica el gruix de cada paràgraf a explicar bé de què va la pel·lícula, quin enfocament té, qui la dirigeix, qui la protagonitza i quin interès cultural aporta. NO facis llistats mecànics ni paràgrafs buits parlant només de cines.
- Prohibit repetir fórmules ni dates: La data d'estrena ({data_divendres}) només s'escriu UNA vegada, al primer paràgraf (lead). NO repeteixis mai "també s'estrena divendres", "arriba a Espanya i Mallorca", etc. Per indicar les sales, fes servir una sola frase curta i natural al final del comentari de cada film (ex: "Es pot veure a <strong>CineCiutat</strong> i <strong>Augusta</strong> en VOSE."). PROHIBIT repetir estructures pesades com "en versió doblada i addicionalment ofereix sessions en idioma original subtitulat".
- Zero citacions d'altres mitjans: PROHIBIT citar o enllaçar altres diaris, revistes o portals externs.
- Estructura: Aplica la piràmide invertida. El primer paràgraf (lead) ha de contenir les 5W (Qui, Què, Quan, On, Per què) de forma directa, amb els títols destacats.

ESTIL DE REDACCIÓ:
- Frases curtes, dinàmiques i fluides.
- Vocabulari precís i ric, sense adjectius valoratius ni llenguatge administratiu/institucional. Prohibits tòpics com "epicentre cultural", "oferta variada", "promet emocionar", "experiència única" o "no es pot perdre".
- Noms propis, institucions, sales de Mallorca i títols d'obres: mai traduïts ni adaptats; respecta l'original.

SEO I FORMATS (REGLES ESTRICTES):
- Jerarquia de Subtítols (H2): Agrupa les pel·lícules en 3 blocs temàtics amb subtítols <h2> descriptius que responguin a la intenció de cerca del lector (ex: cinema estatal, cinema d'autor i VOSE, cinema comercial). No utilitzis H3 ni H4.
- SEO Local i Retenció visual: Aplica negretes (exclusivament amb <strong>...</strong>, mai asteriscos ** ni cites numèriques [1]) únicament a les entitats més importants: directors, intèrprets clau, sales o municipis de Mallorca i la data d'estrena.
- Densitat de Paraules Clau: Assegura't que el concepte clau "estrenes de cinema a Mallorca" (o variacions naturals) aparegui al primer paràgraf i unes 2 vegades més al llarg del text.
- NO afegeixis cap caixa ni secció de "Dades pràctiques" al final.

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
        temperature=0.4,
        max_tokens=4096,
        messages=[
            {"role": "system", "content": prompt_sistema},
            {"role": "user", "content": dossier}
        ]
    )
    return limpiar_y_formatear_html(respuesta.choices[0].message.content)


def adaptar_estrenes_es(html_cat):
    prompt_sistema = """
Actua com una periodista experimentada d'UEP! Mallorca.
Genera una versió íntegra en castellà de la crònica d'estrenes següent (incloent les 3 opcions de titular de màxim 60 caràcters, la meta descripció de màxim 140 caràcters i els posts per a xarxes socials després de l'<hr>).

REGLES ESTRICTES:
1. No ha de ser una traducció literal, sinó una adaptació periodística amb el mateix rigor, sense resumir ni ometre cap pel·lícula, sinopsi, sala ni detall.
2. Contextualitza lleugerament els conceptes culturals o locals si cal perquè un lector castellanoparlant els comprengui, però EVITA explicacions innecessàries com "Consell de Mallorca (gobierno insular)" o "Xeremiers (gaiteros)".
3. Mantén la mateixa estructura de <h2> i <p> (sense H3, H4 ni secció de "Datos prácticos").
4. To àgil, natural i cinematogràfic, sense repeticions de dates, sense tòpics ni llenguatge administratiu.
5. Respecta els noms propis, sales de Mallorca i títols originals sense traduir-los. PROHIBIT citar o mencionar altres mitjans de comunicació o portals externs.
6. A les xarxes socials, no utilitzis "lee más" ni un to excessivament promocional, i inclou 3 o 4 hashtags rellevants i locals.
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
