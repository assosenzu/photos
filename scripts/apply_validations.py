#!/usr/bin/env python3
"""Applique les décisions de la page admin au journal, puis régénère l'index.

Usage :
    python scripts/apply_validations.py events/pauleenne-2026/event.yaml validations.json

Le fichier validations.json est celui exporté par galerie/admin.html.
Pour chaque décision :
- "valider" : le dossard passe en confiance haute ;
- "rejeter" : le dossard est retiré de la photo ;
- "ajouter" : dossard saisi à la main au poste de tri (confiance haute),
  refusé s'il n'est pas dans la liste des participants ;
- "ambiance" : photo vérifiée sans dossard lisible — marquée pour ne plus
  réapparaître dans la liste à trier.

Le journal est réécrit (l'ancien est gardé en journal.jsonl.bak), l'index
régénéré, et republié sur Supabase sauf si --sans-upload.
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


def main():
    parser = argparse.ArgumentParser(description="Applique les validations manuelles")
    parser.add_argument("evenement", help="chemin de l'event.yaml")
    parser.add_argument("validations", help="fichier validations.json exporté par la page admin")
    parser.add_argument("--sans-upload", action="store_true", help="ne pas republier l'index")
    args = parser.parse_args()

    load_dotenv()

    try:
        evenement = charger_evenement(args.evenement)
        participants = charger_participants(
            evenement["participants_csv"], evenement["courses"]
        )
    except (ErreurConfig, ErreurParticipants) as e:
        erreur(str(e))

    try:
        with open(args.validations, encoding="utf-8") as f:
            decisions = json.load(f).get("decisions", [])
    except FileNotFoundError:
        erreur(f"fichier introuvable : {args.validations}")
    except json.JSONDecodeError as e:
        erreur(f"fichier de validations illisible : {e}")
    if not decisions:
        erreur(f"aucune décision dans {args.validations}.")

    sortie = Path("output") / evenement["slug"]
    chemin_journal = sortie / "journal.jsonl"
    journal = Journal(chemin_journal)
    entrees = journal.entrees()
    if not entrees:
        erreur(
            f"journal vide ou absent ({chemin_journal}) — l'événement a-t-il "
            "bien été traité sur cette machine ?"
        )

    valides = rejetes = ajouts = ambiances = introuvables = 0
    for decision in decisions:
        fichier = decision.get("fichier")
        numero = decision.get("numero")
        choix = decision.get("decision")
        entree = entrees.get(fichier)
        if entree is None:
            print(f"Ignoré : photo inconnue du journal ({fichier})")
            introuvables += 1
            continue

        if choix == "ambiance":
            entree["verifiee"] = True
            ambiances += 1
            continue

        if choix == "ajouter":
            if numero not in participants:
                print(
                    f"Refusé : {fichier} / dossard {numero} absent de la liste "
                    "des participants"
                )
                introuvables += 1
            elif any(d["numero"] == numero for d in entree["dossards"]):
                print(f"Ignoré : {fichier} / dossard {numero} déjà attribué")
                introuvables += 1
            else:
                entree["dossards"].append(
                    {"numero": numero, "confiance": "haute", "lu": None,
                     "origine": "manuel"}
                )
                entree["verifiee"] = True
                ajouts += 1
            continue

        cible = next(
            (d for d in entree["dossards"]
             if d["numero"] == numero and d["confiance"] == "moyenne"),
            None,
        )
        if cible is None:
            print(f"Ignoré : {fichier} / dossard {numero} (déjà traité ou inconnu)")
            introuvables += 1
        elif choix == "valider":
            cible["confiance"] = "haute"
            valides += 1
        elif choix == "rejeter":
            entree["dossards"].remove(cible)
            rejetes += 1
        else:
            print(f"Ignoré : décision inconnue '{choix}' pour {fichier}/{numero}")
            introuvables += 1

    shutil.copy2(chemin_journal, str(chemin_journal) + ".bak")
    with open(chemin_journal, "w", encoding="utf-8") as f:
        for entree in entrees.values():
            f.write(json.dumps(entree, ensure_ascii=False) + "\n")

    index = construire_index(evenement, entrees, participants)
    chemin_index = ecrire_index(index, sortie / "index.json")

    bilan = [f"{valides} validation(s)", f"{rejetes} rejet(s)"]
    if ajouts:
        bilan.append(f"{ajouts} ajout(s) manuel(s)")
    if ambiances:
        bilan.append(f"{ambiances} photo(s) d'ambiance")
    if introuvables:
        bilan.append(f"{introuvables} ignorée(s)")
    print(f"\n{', '.join(bilan)}. Index régénéré : {chemin_index}")

    if args.sans_upload:
        print("Index non republié (--sans-upload).")
        return
    try:
        stockage = StockageSupabase(
            os.environ.get("SUPABASE_URL", "").strip(),
            os.environ.get("SUPABASE_SERVICE_KEY", "").strip(),
            f"photos-{evenement['slug']}",
        )
        stockage.deposer(chemin_index, "index.json", content_type="application/json")
        print(f"Index republié : {stockage.url_publique('index.json')}")
    except ErreurStockage as e:
        erreur(str(e))


if __name__ == "__main__":
    main()
