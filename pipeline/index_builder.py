"""Construction de l'index.json consommé par la galerie et la page admin.

Volontairement sans les noms des participants : l'index est publié sur un
bucket public, les noms restent dans le CSV local. La galerie n'affiche que
des numéros de dossard.
"""

import json
from datetime import datetime, timezone
from pathlib import Path


def construire_index(evenement, entrees, participants):
    photos = []
    for entree in sorted(
        entrees.values(), key=lambda e: (e.get("horodatage") or "9999", e["fichier"])
    ):
        dossards = []
        for d in entree.get("dossards", []):
            participant = participants.get(d["numero"], {})
            dossard = {
                "numero": d["numero"],
                "confiance": d["confiance"],
                "course": participant.get("course", ""),
            }
            if d["confiance"] != "haute":
                dossard["lu"] = d.get("lu", "")
            dossards.append(dossard)
        photo = {
            "fichier": entree["fichier"],
            "horodatage": entree.get("horodatage"),
            "miniature": entree.get("miniature"),
            "web": entree.get("web"),
            "dossards": dossards,
        }
        # Photo passée en revue au poste de tri (permet de ne pas la
        # représenter dans la liste "sans dossard" de la page admin)
        if entree.get("verifiee"):
            photo["verifiee"] = True
        photos.append(photo)

    organisateur = evenement.get("organisateur", {})
    return {
        "evenement": {
            "slug": evenement["slug"],
            "nom": evenement["nom"],
            "date": evenement["date"],
            "courses": evenement["courses"],
        },
        "organisateur": {
            "nom": organisateur.get("nom", ""),
            "site": organisateur.get("site", ""),
            "couleurs": organisateur.get("couleurs", {}),
        },
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        # Numéros valides et leur course (jamais les noms) : sert à la page
        # admin pour contrôler les saisies manuelles, et équivaut à une
        # liste de départ, donnée publique dans une course.
        "dossards_connus": {
            numero: info.get("course", "") for numero, info in participants.items()
        },
        "photos": photos,
    }


def ecrire_index(index, chemin):
    chemin = Path(chemin)
    chemin.parent.mkdir(parents=True, exist_ok=True)
    with open(chemin, "w", encoding="utf-8") as f:
        json.dump(index, f, ensure_ascii=False, indent=1)
    return chemin
