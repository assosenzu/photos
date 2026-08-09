#!/usr/bin/env python3
"""Mesure le taux de réussite de la détection contre une vérité terrain.

Usage :
    python scripts/evaluer.py output/mon-evenement/index.json verite.json

Le fichier verite.json est exporté par galerie/annoter.html : pour chaque
photo annotée, la liste des dossards réellement lisibles à l'œil.
L'évaluation ne porte que sur les photos annotées.

Deux chiffres en sortent :
- le taux de photos parfaitement classées (le chiffre de présentation) ;
- le rappel au niveau dossard : la part des dossards visibles retrouvés
  (c'est lui qui dit si un participant retrouve toutes ses photos).
"""

import argparse
import json
import sys
from pathlib import Path


def erreur(message):
    print(f"\nERREUR : {message}", file=sys.stderr)
    sys.exit(1)


def charger_json(chemin, description):
    try:
        with open(chemin, encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        erreur(f"{description} introuvable : {chemin}")
    except json.JSONDecodeError as e:
        erreur(f"{description} illisible ({chemin}) : {e}")


def pourcent(part, total):
    return f"{100 * part / total:.0f} %" if total else "n/a"


def main():
    parser = argparse.ArgumentParser(description="Évaluation de la détection")
    parser.add_argument("index", help="index.json produit par le pipeline")
    parser.add_argument("verite", help="verite.json exporté par annoter.html")
    parser.add_argument(
        "--details", action="store_true",
        help="lister aussi les photos parfaitement classées",
    )
    args = parser.parse_args()

    index = charger_json(args.index, "index")
    verite = charger_json(args.verite, "vérité terrain")

    connus = set(index.get("dossards_connus", {}))
    if not connus:
        print(
            "Note : cet index ne contient pas la liste des dossards connus "
            "(ancien format) — les numéros hors liste ne seront pas filtrés."
        )

    par_fichier = {p["fichier"]: p for p in index["photos"]}
    annotations = verite.get("photos", [])
    if not annotations:
        erreur("aucune photo annotée dans la vérité terrain.")

    parfaites = []
    imparfaites = []  # (fichier, manqués, en_trop)
    absentes = []
    total_attendus = total_trouves_justes = total_en_trop = 0
    ignores_hors_liste = set()
    moyennes_justes = moyennes_fausses = 0

    for annotation in annotations:
        fichier = annotation["fichier"]
        photo = par_fichier.get(fichier)
        if photo is None:
            absentes.append(fichier)
            continue

        attendus = set(annotation.get("dossards", []))
        if connus:
            ignores_hors_liste |= attendus - connus
            attendus &= connus
        trouves = {d["numero"] for d in photo["dossards"]}

        for d in photo["dossards"]:
            if d["confiance"] == "moyenne":
                if d["numero"] in attendus:
                    moyennes_justes += 1
                else:
                    moyennes_fausses += 1

        manques = attendus - trouves
        en_trop = trouves - attendus
        total_attendus += len(attendus)
        total_trouves_justes += len(attendus & trouves)
        total_en_trop += len(en_trop)

        if not manques and not en_trop:
            parfaites.append(fichier)
        else:
            imparfaites.append((fichier, sorted(manques), sorted(en_trop)))

    total = len(parfaites) + len(imparfaites)
    if not total:
        erreur("aucune photo annotée ne correspond à l'index — mêmes fichiers ?")

    print(f"\nÉvaluation sur {total} photo(s) annotée(s)")
    print("=" * 44)
    print(
        f"Photos parfaitement classées : {len(parfaites)}/{total} "
        f"({pourcent(len(parfaites), total)})"
    )
    print(
        f"Dossards visibles retrouvés  : {total_trouves_justes}/{total_attendus} "
        f"({pourcent(total_trouves_justes, total_attendus)})"
    )
    if total_en_trop:
        print(f"Attributions en trop         : {total_en_trop}")
    if moyennes_justes or moyennes_fausses:
        print(
            f"Lectures partielles (confiance moyenne) : "
            f"{moyennes_justes} juste(s), {moyennes_fausses} fausse(s)"
        )

    if imparfaites:
        print(f"\nÀ regarder ({len(imparfaites)} photo(s)) :")
        for fichier, manques, en_trop in imparfaites:
            problemes = []
            if manques:
                problemes.append("manqué : " + ", ".join(manques))
            if en_trop:
                problemes.append("en trop : " + ", ".join(en_trop))
            print(f"  {fichier} — {' ; '.join(problemes)}")

    if args.details and parfaites:
        print(f"\nParfaites ({len(parfaites)}) : {', '.join(parfaites)}")

    if ignores_hors_liste:
        print(
            f"\nNuméros annotés hors liste des inscrits, ignorés : "
            f"{', '.join(sorted(ignores_hors_liste))}"
        )
    if absentes:
        print(
            f"\nAttention : {len(absentes)} photo(s) annotée(s) absente(s) de "
            f"l'index : {', '.join(absentes)}"
        )

    print(
        "\nPhrase pour la présentation : « sur un échantillon de "
        f"{total} photos, {pourcent(len(parfaites), total)} sont parfaitement "
        f"classées automatiquement et {pourcent(total_trouves_justes, total_attendus)} "
        "des dossards visibles sont retrouvés ; le reste est vérifié à la main. »"
    )


if __name__ == "__main__":
    main()
