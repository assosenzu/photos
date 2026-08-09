#!/usr/bin/env python3
"""Test de l'OCR Google Cloud Vision sur quelques photos.

À lancer avant le vrai pipeline pour vérifier que le compte GCP est bien
configuré et se faire une idée de ce que l'OCR détecte sur de vraies photos
de course.

Usage :
    python scripts/test_vision.py                          # 5 photos de input/
    python scripts/test_vision.py --dossier autre/dossier
    python scripts/test_vision.py --max 10
    python scripts/test_vision.py --csv events/exemple/participants.csv
    python scripts/test_vision.py --oui                    # sans confirmation

Avec --csv, les nombres détectés sont comparés au fichier des participants :
seuls ceux présents dans le CSV sont de vrais dossards (c'est le principe de
validation du pipeline complet).
"""

import argparse
import csv
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

# Tarif Google Cloud Vision TEXT_DETECTION : 1,50 $ les 1000 images,
# les 1000 premières de chaque mois étant gratuites.
PRIX_PAR_IMAGE_USD = 1.50 / 1000
QUOTA_GRATUIT_MENSUEL = 1000

EXTENSIONS = {".jpg", ".jpeg", ".png"}

# Un dossard fait entre 1 et 5 chiffres. On capture large ici : le tri entre
# vrais dossards et faux positifs (heures, sponsors, panneaux) se fait par
# comparaison avec le CSV des participants.
RE_NOMBRE = re.compile(r"\b\d{1,5}\b")


def erreur(message):
    print(f"\nERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def verifier_credentials():
    load_dotenv()
    chemin = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not chemin:
        erreur(
            "la variable GOOGLE_APPLICATION_CREDENTIALS n'est pas définie.\n"
            "As-tu copié .env.example en .env ? (commande : cp .env.example .env)\n"
            "Voir le README, étape 5."
        )
    if not Path(chemin).is_file():
        erreur(
            f"le fichier de clé '{chemin}' est introuvable.\n"
            "Dépose la clé JSON téléchargée depuis Google Cloud dans le dossier "
            "secrets/ et renomme-la gcp-vision-key.json (README, étape 4)."
        )
    return chemin


def lister_photos(dossier, maximum):
    d = Path(dossier)
    if not d.is_dir():
        erreur(f"le dossier '{dossier}' n'existe pas.")
    photos = sorted(
        p for p in d.iterdir() if p.suffix.lower() in EXTENSIONS
    )
    if not photos:
        erreur(
            f"aucune photo JPEG trouvée dans '{dossier}'.\n"
            "Dépose 4 ou 5 photos de course (fichiers .jpg) dans ce dossier "
            "puis relance le script."
        )
    return photos[:maximum]


def charger_participants(chemin_csv):
    """Retourne {dossard: (nom, course)} à partir du CSV des participants."""
    participants = {}
    try:
        with open(chemin_csv, newline="", encoding="utf-8-sig") as f:
            lecteur = csv.DictReader(f)
            colonnes = set(lecteur.fieldnames or [])
            if not {"dossard", "nom", "course"} <= colonnes:
                erreur(
                    f"le CSV '{chemin_csv}' doit avoir les colonnes "
                    "dossard, nom, course (voir events/exemple/participants.csv)."
                )
            for ligne in lecteur:
                dossard = ligne["dossard"].strip()
                if dossard:
                    participants[dossard] = (ligne["nom"].strip(), ligne["course"].strip())
    except FileNotFoundError:
        erreur(f"le fichier CSV '{chemin_csv}' est introuvable.")
    return participants


def extraire_nombres(texte):
    """Nombres candidats dans le texte OCR, sans doublons, ordre d'apparition."""
    vus = []
    for m in RE_NOMBRE.findall(texte):
        if m not in vus:
            vus.append(m)
    return vus


def analyser_photo(client, chemin):
    from google.cloud import vision

    with open(chemin, "rb") as f:
        image = vision.Image(content=f.read())
    reponse = client.text_detection(image=image)
    if reponse.error.message:
        raise RuntimeError(reponse.error.message)
    if not reponse.text_annotations:
        return ""
    # La première annotation contient tout le texte de l'image
    return reponse.text_annotations[0].description


def main():
    parser = argparse.ArgumentParser(description="Test Vision API sur quelques photos")
    parser.add_argument("--dossier", default="input", help="dossier des photos (défaut : input)")
    parser.add_argument("--max", type=int, default=5, help="nombre maximum de photos (défaut : 5)")
    parser.add_argument("--csv", help="CSV des participants pour valider les dossards")
    parser.add_argument("--oui", action="store_true", help="ne pas demander de confirmation")
    args = parser.parse_args()

    verifier_credentials()
    photos = lister_photos(args.dossier, args.max)
    participants = charger_participants(args.csv) if args.csv else None

    cout = len(photos) * PRIX_PAR_IMAGE_USD
    print(f"\n{len(photos)} photo(s) à analyser dans '{args.dossier}'.")
    print(
        f"Coût estimé : {cout:.4f} $ "
        f"(gratuit si moins de {QUOTA_GRATUIT_MENSUEL} images ce mois-ci)."
    )
    if not args.oui:
        reponse = input("Lancer l'analyse ? [o/N] ").strip().lower()
        if reponse not in ("o", "oui"):
            print("Annulé.")
            return

    try:
        from google.cloud import vision
        client = vision.ImageAnnotatorClient()
    except Exception as e:
        erreur(
            f"impossible d'initialiser le client Google Vision : {e}\n"
            "Vérifie que la clé JSON est valide et que l'API Vision est activée "
            "dans ton projet Google Cloud (README, étape 3)."
        )

    total_candidats = 0
    total_valides = 0

    for chemin in photos:
        print(f"\n--- {chemin.name} ---")
        try:
            texte = analyser_photo(client, chemin)
        except Exception as e:
            message = str(e)
            if "billing" in message.lower():
                erreur(
                    "la facturation n'est pas activée sur ton projet Google Cloud.\n"
                    "Voir le README, étape 2 (il faut une carte bancaire, mais les "
                    "1000 premières images par mois restent gratuites)."
                )
            if "has not been used" in message or "disabled" in message.lower():
                erreur(
                    "l'API Cloud Vision n'est pas activée sur ton projet.\n"
                    "Voir le README, étape 3."
                )
            print(f"Échec de l'analyse : {message}")
            continue

        if not texte.strip():
            print("Aucun texte détecté sur cette photo.")
            continue

        apercu = " / ".join(l for l in texte.splitlines() if l.strip())
        if len(apercu) > 200:
            apercu = apercu[:200] + "…"
        print(f"Texte lu : {apercu}")

        candidats = extraire_nombres(texte)
        total_candidats += len(candidats)
        if not candidats:
            print("Aucun nombre détecté.")
            continue

        if participants is None:
            print(f"Nombres candidats : {', '.join(candidats)}")
        else:
            for c in candidats:
                if c in participants:
                    nom, course = participants[c]
                    print(f"  {c}  -> dossard valide ({nom}, {course})")
                    total_valides += 1
                else:
                    print(f"  {c}  -> absent du CSV, ignoré")

    print(f"\nTerminé : {len(photos)} photo(s), {total_candidats} nombre(s) détecté(s)", end="")
    if participants is not None:
        print(f", dont {total_valides} dossard(s) valide(s).")
    else:
        print(".")
        print(
            "Astuce : ajoute --csv events/exemple/participants.csv (ou ton vrai CSV) "
            "pour voir la validation des dossards."
        )
    print("Si les résultats te semblent bons, la configuration est prête pour la phase 2.")


if __name__ == "__main__":
    main()
