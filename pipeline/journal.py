"""Journal de progression : une ligne JSON par photo traitée.

C'est ce qui rend le pipeline reprennable — si le traitement s'arrête à la
photo 1200/3000, on relance la même commande et les 1200 déjà journalisées
sont sautées. L'index.json est reconstruit à partir de ce journal à chaque
exécution.
"""

import json
import threading
from pathlib import Path


class Journal:
    def __init__(self, chemin):
        self.chemin = Path(chemin)
        self.chemin.parent.mkdir(parents=True, exist_ok=True)
        self._verrou = threading.Lock()

    def entrees(self):
        """Retourne {nom_de_fichier: entrée} pour tout ce qui est déjà traité."""
        resultat = {}
        if not self.chemin.is_file():
            return resultat
        with open(self.chemin, encoding="utf-8") as f:
            for numero, ligne in enumerate(f, start=1):
                ligne = ligne.strip()
                if not ligne:
                    continue
                try:
                    entree = json.loads(ligne)
                    resultat[entree["fichier"]] = entree
                except (json.JSONDecodeError, KeyError):
                    # Ligne tronquée (arrêt brutal en pleine écriture) : la
                    # photo sera simplement retraitée.
                    print(f"Ligne {numero} du journal illisible, ignorée.")
        return resultat

    def ajouter(self, entree):
        ligne = json.dumps(entree, ensure_ascii=False)
        with self._verrou:
            with open(self.chemin, "a", encoding="utf-8") as f:
                f.write(ligne + "\n")
                f.flush()
