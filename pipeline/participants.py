"""Lecture du CSV des participants (colonnes : dossard, nom, course)."""

import csv


class ErreurParticipants(Exception):
    pass


def charger_participants(chemin, courses_evenement=None):
    """Retourne {dossard: {"nom": ..., "course": ...}}.

    Si `courses_evenement` est fourni, signale (sans bloquer) les courses du
    CSV absentes de l'event.yaml — souvent une faute de frappe d'un côté ou
    de l'autre.
    """
    participants = {}
    courses_inconnues = set()

    try:
        f = open(chemin, newline="", encoding="utf-8-sig")
    except FileNotFoundError:
        raise ErreurParticipants(f"fichier introuvable : {chemin}")

    with f:
        lecteur = csv.DictReader(f)
        colonnes = set(lecteur.fieldnames or [])
        if not {"dossard", "nom", "course"} <= colonnes:
            raise ErreurParticipants(
                f"le CSV '{chemin}' doit avoir les colonnes dossard, nom, course "
                f"(colonnes trouvées : {', '.join(sorted(colonnes)) or 'aucune'})."
            )
        for numero_ligne, ligne in enumerate(lecteur, start=2):
            dossard = (ligne["dossard"] or "").strip()
            if not dossard:
                continue
            if not dossard.isdigit():
                raise ErreurParticipants(
                    f"dossard non numérique ligne {numero_ligne} de {chemin} : "
                    f"'{dossard}'"
                )
            course = (ligne["course"] or "").strip()
            participants[dossard] = {
                "nom": (ligne["nom"] or "").strip(),
                "course": course,
            }
            if courses_evenement is not None and course not in courses_evenement:
                courses_inconnues.add(course)

    if not participants:
        raise ErreurParticipants(f"aucun participant dans {chemin}.")

    if courses_inconnues:
        print(
            f"Attention : course(s) du CSV absente(s) de event.yaml : "
            f"{', '.join(sorted(courses_inconnues))}. Le filtre par course de la "
            "galerie ne les proposera pas."
        )

    return participants
