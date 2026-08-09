#!/usr/bin/env python3
"""Régénère le jeu de démonstration de la galerie (galerie/demo/).

Fabrique des photos factices (fond coloré + numéro de dossard) et un
index.json au même format que celui produit par le pipeline, avec des cas
variés : dossards nets, lectures partielles en confiance moyenne, photos
sans dossard. Les fichiers sont versionnés — ce script ne sert que si on
veut faire évoluer la démo.
"""

import json
import random
import sys
from pathlib import Path

from PIL import Image, ImageDraw

RACINE = Path(__file__).resolve().parent.parent
DEMO = RACINE / "galerie" / "demo"

COURSES = {"5km": (226, 116, 16), "10km": (24, 118, 168), "rando": (46, 190, 122)}

# (fichier, heure, course, dossards[(numero, confiance, lu)])
PHOTOS = [
    ("demo_001.jpg", "09:02:11", "5km", [("101", "haute", "101")]),
    ("demo_002.jpg", "09:05:43", "5km", [("102", "haute", "102"), ("103", "haute", "103")]),
    ("demo_003.jpg", "09:14:27", "5km", [("115", "moyenne", "11")]),
    ("demo_004.jpg", "09:31:05", "5km", [("103", "haute", "103")]),
    ("demo_005.jpg", "10:03:18", "10km", [("230", "haute", "230")]),
    ("demo_006.jpg", "10:08:52", "10km", [("231", "haute", "231"), ("245", "haute", "245")]),
    ("demo_007.jpg", "10:22:40", "10km", [("258", "moyenne", "58")]),
    ("demo_008.jpg", "10:47:09", "10km", [("245", "haute", "245")]),
    ("demo_009.jpg", "11:12:33", "rando", [("501", "haute", "501")]),
    ("demo_010.jpg", "11:19:06", "rando", [("502", "moyenne", "50")]),
    ("demo_011.jpg", "11:26:54", None, []),
    ("demo_012.jpg", None, None, []),
]


def dessiner(chemin, taille, couleur, numeros, libelle):
    largeur, hauteur = taille
    image = Image.new("RGB", taille, couleur)
    trace = ImageDraw.Draw(image)
    # léger dégradé vertical pour éviter l'aplat brut
    for y in range(hauteur):
        facteur = 1 - 0.35 * y / hauteur
        trace.line(
            [(0, y), (largeur, y)],
            fill=tuple(int(c * facteur) for c in couleur),
        )
    if numeros:
        # faux dossard : rectangle blanc avec le numéro
        rng = random.Random(chemin.name)
        for i, numero in enumerate(numeros):
            boite_l, boite_h = int(largeur * 0.28), int(hauteur * 0.18)
            x = int(largeur * (0.12 + 0.45 * i + rng.random() * 0.08))
            y = int(hauteur * (0.45 + rng.random() * 0.2))
            trace.rectangle([x, y, x + boite_l, y + boite_h], fill="white")
            trace.text(
                (x + boite_l // 2, y + boite_h // 2),
                numero,
                fill="black",
                anchor="mm",
                font_size=int(boite_h * 0.6),
            )
    trace.text(
        (largeur // 2, int(hauteur * 0.12)),
        libelle,
        fill="white",
        anchor="mm",
        font_size=int(hauteur * 0.07),
    )
    image.save(chemin, "JPEG", quality=70, optimize=True)


def main():
    (DEMO / "thumbs").mkdir(parents=True, exist_ok=True)
    (DEMO / "web").mkdir(parents=True, exist_ok=True)

    photos_index = []
    for fichier, heure, course, dossards in PHOTOS:
        couleur = COURSES.get(course, (90, 90, 100))
        numeros = [lu for _, _, lu in dossards]
        # sans accents : la police par defaut de Pillow ne les couvre pas
        libelle = f"Photo demo - {course or 'ambiance'}"
        dessiner(DEMO / "web" / fichier, (800, 533), couleur, numeros, libelle)
        dessiner(DEMO / "thumbs" / fichier, (400, 267), couleur, numeros, libelle)

        entree_dossards = []
        for numero, confiance, lu in dossards:
            d = {"numero": numero, "confiance": confiance, "course": course or ""}
            if confiance != "haute":
                d["lu"] = lu
            entree_dossards.append(d)
        photos_index.append(
            {
                "fichier": fichier,
                "horodatage": f"2026-05-17T{heure}" if heure else None,
                "miniature": f"galerie/demo/thumbs/{fichier}",
                "web": f"galerie/demo/web/{fichier}",
                "dossards": entree_dossards,
            }
        )

    index = {
        "evenement": {
            "slug": "demo",
            "nom": "La Pauléenne 2026 (démo)",
            "date": "2026-05-17",
            "courses": list(COURSES),
        },
        "organisateur": {
            "nom": "SENZU Sport Expérience",
            "site": "https://senzu-asso.fr",
            "couleurs": {
                "accent": "#e27410",
                "accent_fonce": "#b85c0a",
                "entete": "#16212e",
            },
        },
        "genere_le": "2026-05-17T18:00:00+00:00",
        "dossards_connus": {
            "101": "5km", "102": "5km", "103": "5km", "115": "5km",
            "230": "10km", "231": "10km", "245": "10km", "258": "10km",
            "501": "rando", "502": "rando",
        },
        "photos": photos_index,
    }
    with open(DEMO / "index.json", "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    print(f"Démo régénérée : {len(photos_index)} photos dans {DEMO}")


if __name__ == "__main__":
    main()
