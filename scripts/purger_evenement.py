#!/usr/bin/env python3
"""Supprime un événement du stockage en ligne (bucket Supabase entier).

À utiliser quand un événement n'a plus besoin d'être en ligne — fin de la
durée de publication convenue avec l'organisateur, ou place à libérer sur le
plan gratuit Supabase (1 Go). La galerie de cet événement cesse de
fonctionner immédiatement.

Le dossier local output/{slug}/ (journal, index, images générées) est
conservé par défaut — c'est la trace de ce qui a été fait et publié.
--local le supprime aussi.

Usage :
    python scripts/purger_evenement.py events/pauleenne-2026/event.yaml
    python scripts/purger_evenement.py events/pauleenne-2026/event.yaml --local
"""

import argparse
import os
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

from pipeline.config import ErreurConfig, charger_evenement
from pipeline.stockage import ErreurStockage, StockageSupabase


def erreur(message):
    print(f"\nERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Purge le stockage d'un événement")
    parser.add_argument("evenement", help="chemin de l'event.yaml")
    parser.add_argument("--local", action="store_true",
                        help="supprimer aussi output/{slug}/ (journal compris)")
    args = parser.parse_args()

    load_dotenv()

    try:
        evenement = charger_evenement(args.evenement)
    except ErreurConfig as e:
        erreur(str(e))
    slug = evenement["slug"]

    print(
        f"\nCette commande va supprimer DÉFINITIVEMENT le bucket "
        f"'photos-{slug}' et toutes ses photos en ligne."
    )
    if args.local:
        print(f"Elle supprimera aussi le dossier local output/{slug}/ (journal compris).")
    print("La galerie publique de cet événement ne fonctionnera plus.")
    saisie = input(f"Pour confirmer, tape le slug de l'événement ({slug}) : ").strip()
    if saisie != slug:
        print("Saisie différente du slug — rien n'a été supprimé.")
        return

    try:
        stockage = StockageSupabase(
            os.environ.get("SUPABASE_URL", "").strip(),
            os.environ.get("SUPABASE_SERVICE_KEY", "").strip(),
            f"photos-{slug}",
        )
        stockage.detruire_bucket()
    except ErreurStockage as e:
        erreur(str(e))
    except Exception as e:
        erreur(
            f"suppression du bucket impossible : {e}\n"
            "Il peut déjà avoir été supprimé — vérifie dans l'interface "
            "Supabase (Storage)."
        )
    print(f"Bucket photos-{slug} supprimé.")

    if args.local:
        dossier = Path("output") / slug
        if dossier.is_dir():
            shutil.rmtree(dossier)
            print(f"Dossier {dossier} supprimé.")
        else:
            print(f"Pas de dossier {dossier} en local.")
    else:
        print(
            f"Le dossier local output/{slug}/ est conservé (journal et index) — "
            "supprime-le à la main ou relance avec --local si tu n'en as plus besoin."
        )


if __name__ == "__main__":
    main()
