#!/usr/bin/env python3
"""Pipeline complet d'un événement : OCR, validation, miniatures, upload, index.

Usage :
    python scripts/process_event.py events/pauleenne-2026/event.yaml
    python scripts/process_event.py events/exemple --sans-upload --limite 20

Le traitement est reprennable : chaque photo terminée est notée dans
output/{slug}/journal.jsonl. Si le script s'arrête (plantage, quota, Ctrl+C),
on relance la même commande et il reprend où il en était.

Options :
    --dossier D       dossier des photos sources (défaut : input)
    --sans-upload     tout faire sauf l'upload Supabase (test local)
    --limite N        ne traiter que N photos (pour essayer sur un échantillon)
    --workers N       photos traitées en parallèle (défaut : 4)
    --debit N         appels Vision par seconde au maximum (défaut : 5)
    --oui             ne pas demander de confirmation
"""

import argparse
import os
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from pipeline.config import ErreurConfig, charger_evenement
from pipeline.images import generer_versions, horodatage_exif
from pipeline.index_builder import construire_index, ecrire_index
from pipeline.journal import Journal
from pipeline.matching import associer
from pipeline.participants import ErreurParticipants, charger_participants
from pipeline.stockage import ErreurStockage, StockageSupabase
from pipeline.vision_ocr import (
    PRIX_PAR_IMAGE_USD,
    QUOTA_GRATUIT_MENSUEL,
    LecteurVision,
    extraire_nombres,
)

EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif"}
ECHECS_CONSECUTIFS_MAX = 5


def erreur(message):
    print(f"\nERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def lister_photos(dossier):
    d = Path(dossier)
    if not d.is_dir():
        erreur(f"le dossier '{dossier}' n'existe pas.")
    photos = sorted(p for p in d.iterdir() if p.suffix.lower() in EXTENSIONS)
    if not photos:
        erreur(f"aucune photo (JPEG, PNG ou HEIC) dans '{dossier}'.")
    heic = [p for p in photos if p.suffix.lower() in (".heic", ".heif")]
    if heic:
        from pipeline.images import HEIF_DISPONIBLE

        if not HEIF_DISPONIBLE:
            erreur(
                f"{len(heic)} photo(s) HEIC dans '{dossier}' mais le module "
                "pillow-heif n'est pas installé.\n"
                "Lance : pip install -r requirements.txt"
            )
    # Deux fichiers qui ne diffèrent que par l'extension (IMG_1.jpg et
    # IMG_1.heic) produiraient le même IMG_1.jpg en sortie
    doublons = {}
    for p in photos:
        doublons.setdefault(p.stem, []).append(p.name)
    en_conflit = [", ".join(noms) for noms in doublons.values() if len(noms) > 1]
    if en_conflit:
        erreur(
            "des fichiers porteraient le même nom une fois convertis en JPEG : "
            + " / ".join(en_conflit)
            + "\nRenomme l'un des deux avant de relancer."
        )
    return photos


def main():
    parser = argparse.ArgumentParser(description="Pipeline photos d'un événement")
    parser.add_argument("evenement", help="chemin de l'event.yaml (ou de son dossier)")
    parser.add_argument("--dossier", default="input", help="photos sources (défaut : input)")
    parser.add_argument("--sans-upload", action="store_true", help="pas d'upload Supabase")
    parser.add_argument("--limite", type=int, help="ne traiter que N photos")
    parser.add_argument("--workers", type=int, default=4, help="traitements en parallèle")
    parser.add_argument("--debit", type=float, default=5.0, help="appels Vision/seconde max")
    parser.add_argument("--oui", action="store_true", help="pas de confirmation")
    args = parser.parse_args()

    load_dotenv()

    chemin_credentials = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    if not chemin_credentials or not Path(chemin_credentials).is_file():
        erreur(
            "clé Google Cloud introuvable. Vérifie le fichier .env et la clé "
            "dans secrets/ (README, étapes 4 et 5)."
        )

    try:
        evenement = charger_evenement(args.evenement)
        participants = charger_participants(
            evenement["participants_csv"], evenement["courses"]
        )
    except (ErreurConfig, ErreurParticipants) as e:
        erreur(str(e))

    slug = evenement["slug"]
    sortie = Path("output") / slug
    dossier_miniatures = sortie / "thumbs"
    dossier_web = sortie / "web"
    dossier_miniatures.mkdir(parents=True, exist_ok=True)
    dossier_web.mkdir(parents=True, exist_ok=True)

    journal = Journal(sortie / "journal.jsonl")
    deja_faites = journal.entrees()

    photos = lister_photos(args.dossier)
    restantes = [p for p in photos if p.name not in deja_faites]
    if args.limite:
        restantes = restantes[: args.limite]

    print(f"\nÉvénement : {evenement['nom']} ({slug})")
    print(f"Participants : {len(participants)} dossards dans le CSV")
    print(
        f"Photos : {len(photos)} dans '{args.dossier}', "
        f"{len(deja_faites)} déjà traitée(s), {len(restantes)} à traiter."
    )
    if not restantes:
        print("Rien à traiter — reconstruction de l'index seulement.")
    else:
        cout = len(restantes) * PRIX_PAR_IMAGE_USD
        print(
            f"Coût Vision estimé : {cout:.2f} $ (les {QUOTA_GRATUIT_MENSUEL} "
            "premières images du mois sont gratuites)."
        )
        if not args.oui:
            reponse = input("Lancer le traitement ? [o/N] ").strip().lower()
            if reponse not in ("o", "oui"):
                print("Annulé.")
                return

    stockage = None
    if not args.sans_upload:
        try:
            stockage = StockageSupabase(
                os.environ.get("SUPABASE_URL", "").strip(),
                os.environ.get("SUPABASE_SERVICE_KEY", "").strip(),
                f"photos-{slug}",
            )
        except ErreurStockage as e:
            erreur(str(e))

    lecteur = None
    if restantes:
        try:
            lecteur = LecteurVision(args.debit)
        except Exception as e:
            erreur(
                f"initialisation du client Google Vision impossible : {e}\n"
                "Vérifie la clé de service et l'activation de l'API (README)."
            )

    verrou_affichage = threading.Lock()
    compteur = {"faites": 0, "echecs": 0, "echecs_consecutifs": 0}
    arret = threading.Event()
    fichier_erreurs = sortie / "erreurs.log"

    def traiter(chemin):
        if arret.is_set():
            return None
        texte = lecteur.lire_texte(chemin)
        dossards = associer(extraire_nombres(texte), participants)

        miniature, web = generer_versions(
            chemin, dossier_miniatures, dossier_web
        )
        if stockage is not None:
            url_miniature = stockage.deposer(miniature, f"thumbs/{miniature.name}")
            url_web = stockage.deposer(web, f"web/{web.name}")
        else:
            url_miniature = f"output/{slug}/thumbs/{miniature.name}"
            url_web = f"output/{slug}/web/{web.name}"

        entree = {
            "fichier": chemin.name,
            "horodatage": horodatage_exif(chemin),
            "dossards": dossards,
            "miniature": url_miniature,
            "web": url_web,
        }
        journal.ajouter(entree)
        return entree

    total = len(restantes)
    if restantes:
        with ThreadPoolExecutor(max_workers=args.workers) as executeur:
            taches = {executeur.submit(traiter, p): p for p in restantes}
            for tache in as_completed(taches):
                chemin = taches[tache]
                try:
                    entree = tache.result()
                except Exception as e:
                    with verrou_affichage:
                        compteur["echecs"] += 1
                        compteur["echecs_consecutifs"] += 1
                        print(f"ÉCHEC {chemin.name} : {e}")
                        with open(fichier_erreurs, "a", encoding="utf-8") as f:
                            f.write(f"{chemin.name}\t{e}\n")
                        if (
                            compteur["echecs_consecutifs"] >= ECHECS_CONSECUTIFS_MAX
                            and compteur["faites"] == 0
                        ):
                            arret.set()
                            print(
                                "\nTout échoue depuis le début : arrêt. Corrige "
                                "le problème ci-dessus puis relance — rien n'est "
                                "perdu."
                            )
                    continue
                if entree is None:
                    continue
                with verrou_affichage:
                    compteur["faites"] += 1
                    compteur["echecs_consecutifs"] = 0
                    numeros = ", ".join(
                        f"{d['numero']} ({d['confiance']})" for d in entree["dossards"]
                    )
                    print(
                        f"[{compteur['faites'] + compteur['echecs']}/{total}] "
                        f"{entree['fichier']} -> {numeros or 'aucun dossard'}"
                    )
        if arret.is_set():
            sys.exit(1)

    # Index reconstruit à partir du journal complet (photos de cette
    # exécution et des précédentes)
    entrees = journal.entrees()
    if not entrees:
        erreur("aucune photo traitée avec succès, pas d'index à générer.")
    index = construire_index(evenement, entrees, participants)
    chemin_index = ecrire_index(index, sortie / "index.json")

    if stockage is not None:
        stockage.deposer(chemin_index, "index.json", content_type="application/json")

    nb_avec_dossard = sum(1 for p in index["photos"] if p["dossards"])
    nb_moyenne = sum(
        1
        for p in index["photos"]
        for d in p["dossards"]
        if d["confiance"] == "moyenne"
    )
    print(f"\nTerminé. {len(index['photos'])} photo(s) dans l'index :")
    print(f"  - {nb_avec_dossard} avec au moins un dossard identifié")
    print(f"  - {nb_moyenne} attribution(s) en confiance moyenne à valider (page admin)")
    if compteur["echecs"]:
        print(
            f"  - {compteur['echecs']} photo(s) en échec (détail dans "
            f"{fichier_erreurs}) — relance la même commande pour les retenter."
        )
    print(f"Index local : {chemin_index}")
    if stockage is not None:
        print(f"Index publié : {stockage.url_publique('index.json')}")


if __name__ == "__main__":
    main()
