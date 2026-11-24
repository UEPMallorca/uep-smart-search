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
    "exposicions de la setmana", "esborrany", "borrador"
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
    "Es Gremi", "Auditorium de Palma", "Trui Teatre",
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
    "Auditorium de Palma", "Trui Teatre", "Sala Assaig"
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
    "CCA Andratx", "Museu Sa Bassa Blanca (Alcúdia)",
    "Fundació Toni Catany (Llucmajor)", "Casal de Cultura Can Gelabert (Binissalem)",
    "Galeria Maior (Pollença)", "Museu d'Art Contemporani de sa Pobla (Can Planes)",
    "Claustre de Sant Domingo (Pollença)", "Museu d'Història de Manacor",
    "Fundació Coll Bardolet (Valldemossa)"
]

ESPAIS_AGENDA_PALMA = [
    "Teatre Principal de Palma", "Auditorium de Palma", "Es Gremi",
    "Teatre Xesc Forteza", "Teatre del Mar", "Teatre Mar i Terra",
    "Es Baluard", "Casal Solleric", "CaixaForum Palma", "Fundació Miró Mallorca",
    "Art Palma Contemporani", "PalmaCultura"
]

ESPAIS_AGENDA_PART_FORANA = [
    "
