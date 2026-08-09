"""Association entre nombres lus par l'OCR et dossards du CSV.

Deux niveaux de confiance :
- "haute" : le nombre lu est exactement un dossard du CSV ;
- "moyenne" : lecture partielle — le nombre lu n'est pas un dossard mais il
  est le début ou la fin d'un seul et unique dossard (dossard à moitié caché
  par un bras, une épingle, un pli du tee-shirt). Ces cas sont listés dans la
  page admin pour validation manuelle.
"""

LONGUEUR_MINI_PARTIEL = 2


def associer(candidats, dossards):
    """`candidats` : nombres lus (chaînes). `dossards` : numéros valides.

    Retourne une liste de {"numero", "confiance", "lu"} sans doublons ;
    si un dossard ressort à la fois en lecture exacte et partielle, seule la
    lecture exacte est gardée.
    """
    resultats = {}

    for c in candidats:
        if c in dossards:
            resultats[c] = {"numero": c, "confiance": "haute", "lu": c}

    for c in candidats:
        if c in dossards or len(c) < LONGUEUR_MINI_PARTIEL:
            continue
        compatibles = [d for d in dossards if d.startswith(c) or d.endswith(c)]
        if len(compatibles) == 1 and compatibles[0] not in resultats:
            resultats[compatibles[0]] = {
                "numero": compatibles[0],
                "confiance": "moyenne",
                "lu": c,
            }

    return list(resultats.values())
