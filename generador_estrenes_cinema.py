import os
import datetime
import requests
from requests.auth import HTTPBasicAuth
from openai import OpenAI

# Configuració de variables d'entorn (comprova que coincideixin amb els Secrets de GitHub)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
WP_URL = os.environ.get("WP_URL")          # Ex: https://uepmallorca.app/wp-json/wp/v2/posts
WP_USER = os.environ.get("WP_USER")
WP_PASSWORD = os.environ.get("WP_PASSWORD") # Contrasenya d'aplicació de WordPress
CAT_CINEMA_ID = os.environ.get("CAT_CINEMA_ID", "") # Opcional: ID numèric de la categoria Cinema

client = OpenAI(api_key=OPENAI_API_KEY)

def obtenir_data_divendres():
    avui = datetime.date.today()
    # Calcula el divendres d'aquesta setmana (0=dilluns ... 4=divendres)
    dies_fins_divendres = (4 - avui.weekday()) % 7
    divendres = avui + datetime.timedelta(days=dies_fins_divendres)
    return divendres.strftime("%d/%m/%Y")

def generar_noticia_estrenes():
    data_divendres = obtenir_data_divendres()
    
    prompt = f"""
Actua com una periodista jove, feminista i experimentada de la secció de cultura del diari digital UEP! Mallorca.
Cerca a internet les estrenes de cinema que arriben aquest divendres {data_divendres} a les sales de Mallorca:
- CineCiutat (Palma)
- Aficine (Augusta, Ocimax Palma, Rívoli)
- Artesiete FAN (Palma)
- Cinesa Festival Park / Mallorca Fashion Outlet (Marratxí)

Redacta una notícia periodística completa en CATALÀ i una segona versió íntegra adaptada al CASTELLÀ seguint aquestes regles estrictes:
1. Piràmide invertida: el primer paràgraf (lead) ha de contenir les 5W directament i la paraula clau "estrenes de cinema a Mallorca".
2. Estil: frases curtes, dinàmiques, to neutral i rigorós, sense primera persona ni adjectius valoratius ni llenguatge promocional.
3. No tradueixis mai els títols originals ni els noms propis de sales o persones.
4. PROHIBIT incloure cites numèriques, claudàtors o enllaços automàtics de cerca tipus [1] o (font.com). Text completament net.
5. Format HTML net per a WordPress (fent servir només etiquetes <p>, <h2>, <ul>, <li>, <strong>, <em>). No facis servir <h1> ni <h3>. Si inclous algun enllaç, afegeix sempre target="_blank" rel="noopener noreferrer".
6. Negretes (<strong>) exclusivament a noms clau (directors, intèrprets), sales de Mallorca i dates.
7. Estructura obligatòria per a cada idioma:
   - 3 propostes de titular (màx. 60 caràcters): Periodístic, Google Discover i SEO.
   - Meta descripció (màx. 140 caràcters).
   - Cos de la notícia dividit amb subtítols <h2> (ex: cinema estatal, cinema d'autor/VOSE, cinema comercial).
   - Bloc final <h2>Dades pràctiques</h2> en format llista (<ul><li>) indicant quina pel·lícula es projecta a cada sala.
   - Posts per a xarxes socials en català (Threads, Bluesky, Instagram i Facebook) sense "llegeix més" i amb 3-4 hashtags locals.
"""

response = client.responses.create(
        model="gpt-4o",
        tools=[{"type": "web_search"}],
        input=prompt
    )
    
    return response.output_text, data_divendres

def publicar_esborrany_wp(titol, contingut_html):
    payload = {
        "title": titol,
        "content": contingut_html,
        "status": "draft"
    }
    
    if CAT_CINEMA_ID and CAT_CINEMA_ID.isdigit():
        payload["categories"] = [int(CAT_CINEMA_ID)]

    r = requests.post(
        WP_URL,
        json=payload,
        auth=HTTPBasicAuth(WP_USER, WP_PASSWORD),
        timeout=30
    )
    r.raise_for_status()
    print(f"Esborrany creat correctament a WordPress. ID: {r.json().get('id')}")

if __name__ == "__main__":
    contingut, data_divendres = generar_noticia_estrenes()
    titol_esborrany = f"Estrenes de cinema a Mallorca ({data_divendres})"
    publicar_esborrany_wp(titol_esborrany, contingut)
