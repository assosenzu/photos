"""Chargement de la configuration d'un événement (event.yaml)."""

import re
from pathlib import Path

import yaml


class ErreurConfig(Exception):
    pass


CHAMPS_OBLIGATOIRES = ("slug", "nom", "courses", "participants_csv")
RE_SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def charger_evenement(chemin):
    """Lit un event.yaml et retourne un dict validé.

    `chemin` peut être le fichier YAML lui-même ou le dossier de l'événement.
    """
    p = Path(chemin)
    if p.is_dir():
        p = p / "event.yaml"
    if not p.is_file():
        raise ErreurConfig(
            f"fichier de configuration introuvable : {p}\n"
            "Passe le chemin d'un event.yaml (exemple : events/exemple/event.yaml)."
        )

    with open(p, encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    manquants = [c for c in CHAMPS_OBLIGATOIRES if not data.get(c)]
    if manquants:
        raise ErreurConfig(
            f"champs manquants dans {p} : {', '.join(manquants)}\n"
            "Voir events/exemple/event.yaml pour le format attendu."
        )

    slug = str(data["slug"]).strip()
    if not RE_SLUG.match(slug):
        raise ErreurConfig(
            f"slug invalide : '{slug}'. Uniquement des minuscules, chiffres et "
            "tirets, sans espaces ni accents (exemple : pauleenne-2026)."
        )

    if not isinstance(data["courses"], list) or not all(
        isinstance(c, str) and c.strip() for c in data["courses"]
    ):
        raise ErreurConfig(f"'courses' doit être une liste de noms dans {p}.")

    # Le chemin du CSV peut être relatif à la racine du dépôt ou au dossier
    # de l'événement — on essaie les deux.
    csv_brut = Path(str(data["participants_csv"]))
    candidats = [csv_brut, p.parent / csv_brut.name, p.parent / csv_brut]
    csv_final = next((c for c in candidats if c.is_file()), None)
    if csv_final is None:
        raise ErreurConfig(
            f"CSV des participants introuvable : '{csv_brut}' (déclaré dans {p})."
        )

    # Identité de l'organisateur : tout est optionnel, la galerie a des
    # valeurs neutres par défaut. C'est ce qui rend l'outil utilisable par
    # n'importe quel club ou organisateur sans toucher au code.
    organisateur_brut = data.get("organisateur") or {}
    if not isinstance(organisateur_brut, dict):
        raise ErreurConfig(f"'organisateur' doit être un bloc clé/valeur dans {p}.")
    couleurs_brut = organisateur_brut.get("couleurs") or {}
    organisateur = {
        "nom": str(organisateur_brut.get("nom", "") or "").strip(),
        "site": str(organisateur_brut.get("site", "") or "").strip(),
        "couleurs": {
            str(k): str(v).strip() for k, v in couleurs_brut.items() if v
        },
        "watermark": str(organisateur_brut.get("watermark", "") or "").strip(),
    }

    return {
        "slug": slug,
        "nom": str(data["nom"]).strip(),
        "date": str(data.get("date", "")).strip(),
        "courses": [c.strip() for c in data["courses"]],
        "participants_csv": str(csv_final),
        "organisateur": organisateur,
    }
