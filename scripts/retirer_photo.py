#!/usr/bin/env python3
"""Retire complètement une photo d'un événement publié.

C'est l'outil du droit à l'image : quand quelqu'un demande le retrait d'une
photo, cette commande la supprime du bucket Supabase (miniature et version
web), du journal, et régénère puis republie l'index. La photo d'origine dans
input/ n'est pas touchée — à toi de l'archiver ou la supprimer selon la
demande.

Usage :
    python scripts/retirer_photo.py events/pauleenne-2026/event.yaml IMG_1234.jpg
    python scripts/retirer_photo.py events/… IMG_1234.jpg IMG_1250.jpg
"""

import argparse
import json
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from pipeline.config import ErreurConfig, charger_evenement
from pipeline.index_builder import construire_index, ecrire_index
from pipeline.journal import Journal
from pipeline.participants import ErreurParticipants, charger_participants
from pipeline.stockage import ErreurStockage, StockageSupabase


def erreur(message):
    print(f"\nERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def nom_distant(url, prefixe):
    """Chemin du fichier dans le bucket à partir de l'URL de l'index."""
    nom = url.rstrip("/").split("/")[-1].split("?")[0]
    return f"{prefixe}/{nom}"


def main():
    parser = argparse.ArgumentParser(description="Retire une photo publiée")
    parser.add_argument("evenement", help="chemin de l'event.yaml")
    parser.add_argument("fichiers", nargs="+", help="nom(s) de fichier tel(s) qu'affiché(s) dans la galerie")
    parser.add_argument("--sans-upload", action="store_true",
                        help="ne toucher qu'au journal et à l'index locaux")
    args = parser.parse_args()

    load_dotenv()

    try:
        evenement = charger_evenement(args.evenement)
        participants = charger_participants(
            evenement["participants_csv"], evenement["courses"]
        )
    except (ErreurConfig, ErreurParticipants) as e:
        erreur(str(e))

    sortie = Path("output") / evenement["slug"]
    chemin_journal = sortie / "journal.jsonl"
    journal = Journal(chemin_journal)
    entrees = journal.entrees()
    if not entrees:
        erreur(f"journal vide ou absent ({chemin_journal}).")

    a_retirer = []
    for fichier in args.fichiers:
        if fichier in entrees:
            a_retirer.append(entrees.pop(fichier))
        else:
            erreur(
                f"'{fichier}' n'est pas dans le journal de cet événement.\n"
                "Le nom attendu est celui affiché dans la galerie ou l'index "
                "(sensible aux majuscules)."
            )

    stockage = None
    if not args.sans_upload:
        try:
            stockage = StockageSupabase(
                os.environ.get("SUPABASE_URL", "").strip(),
                os.environ.get("SUPABASE_SERVICE_KEY", "").strip(),
                f"photos-{evenement['slug']}",
            )
        except ErreurStockage as e:
            erreur(str(e))

    if stockage is not None:
        distants = []
        for entree in a_retirer:
            distants.append(nom_distant(entree.get("miniature", ""), "thumbs"))
            distants.append(nom_distant(entree.get("web", ""), "web"))
        try:
            stockage.supprimer(distants)
        except Exception as e:
            erreur(
                f"suppression dans le bucket impossible : {e}\n"
                "Rien n'a été modifié localement, relance quand c'est réglé."
            )

    shutil.copy2(chemin_journal, str(chemin_journal) + ".bak")
    with open(chemin_journal, "w", encoding="utf-8") as f:
        for entree in entrees.values():
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")

    # Fichiers locaux générés
    for entree in a_retirer:
        for cle, dossier in (("miniature", "thumbs"), ("web", "web")):
            nom = (entree.get(cle) or "").rstrip("/").split("/")[-1].split("?")[0]
            if nom:
                (sortie / dossier / nom).unlink(missing_ok=True)

    index = construire_index(evenement, entrees, participants)
    chemin_index = ecrire_index(index, sortie / "index.json")
    if stockage is not None:
        stockage.deposer(chemin_index, "index.json", content_type="application/json")

    noms = ", ".join(e["fichier"] for e in a_retirer)
    print(f"\nRetiré : {noms}")
    print(f"Index régénéré ({len(index['photos'])} photos restantes)"
          + (" et republié." if stockage is not None else " en local (--sans-upload)."))
    print(
        "La photo d'origine est toujours dans ton dossier de photos sources — "
        "pense à l'écarter si la demande l'exige."
    )


if __name__ == "__main__":
    main()
