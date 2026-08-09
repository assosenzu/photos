"""Appels à Google Cloud Vision (TEXT_DETECTION) avec limite de débit."""

import re
import threading
import time

# Tarif TEXT_DETECTION : 1,50 $ les 1000 images, les 1000 premières de
# chaque mois gratuites.
PRIX_PAR_IMAGE_USD = 1.50 / 1000
QUOTA_GRATUIT_MENSUEL = 1000

# Un dossard fait entre 1 et 5 chiffres. On capture large : le tri entre
# vrais dossards et faux positifs se fait ensuite contre le CSV.
RE_NOMBRE = re.compile(r"\b\d{1,5}\b")


def extraire_nombres(texte):
    """Nombres candidats du texte OCR, sans doublons, ordre d'apparition."""
    vus = []
    for m in RE_NOMBRE.findall(texte):
        if m not in vus:
            vus.append(m)
    return vus


class LecteurVision:
    """Client Vision partagé entre threads, avec un débit maximum global."""

    def __init__(self, requetes_par_seconde=5.0):
        from google.cloud import vision

        self._vision = vision
        self._client = vision.ImageAnnotatorClient()
        self._intervalle = 1.0 / max(requetes_par_seconde, 0.1)
        self._verrou = threading.Lock()
        self._prochain_depart = 0.0

    def _respecter_debit(self):
        with self._verrou:
            maintenant = time.monotonic()
            depart = max(maintenant, self._prochain_depart)
            self._prochain_depart = depart + self._intervalle
        attente = depart - time.monotonic()
        if attente > 0:
            time.sleep(attente)

    def lire_texte(self, chemin):
        """Texte complet détecté sur la photo (chaîne vide si rien)."""
        self._respecter_debit()
        with open(chemin, "rb") as f:
            image = self._vision.Image(content=f.read())
        reponse = self._client.text_detection(image=image)
        if reponse.error.message:
            raise RuntimeError(reponse.error.message)
        if not reponse.text_annotations:
            return ""
        return reponse.text_annotations[0].description
