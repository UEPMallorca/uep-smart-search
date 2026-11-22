import os
import datetime
import requests
from requests.auth import HTTPBasicAuth
from openai import OpenAI

# Configuració de variables d'entorn (comprova que coincideixin amb els Secrets de GitHub)
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")
WP_URL = os.environ.get("WP_URL")
WP_USER = os.environ.get("WP_USER")
WP_PASSWORD = os.environ.get("WP_PASSWORD")
CAT_CINEMA_ID = os.environ.get("CAT_CINEMA_ID", "")

client = OpenAI(api_key=OPENAI_API_KEY)


def obtenir_data_divendres():
    avui = datetime.date.today()
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
2. Estil: frases curtes, dinàmiques, to neutral i
